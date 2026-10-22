"""High-level pipeline: source -> validated ShaderIR + generated outputs."""
import re
from dataclasses import dataclass, field

from . import convert as C
from . import emit_ffgl


@dataclass
class Result:
    ir: object = None
    ffgl_glsl: list = field(default_factory=list)
    ok: bool = False
    validated: bool = False
    errors: list = field(default_factory=list)   # (line, message); line is in the user's source
    log: str = ""
    demoted: list = field(default_factory=list)  # consts we gave up promoting


def convert_ffgl(code, name="Shader", path=None, extract_params=True, promote_ints=False,
                 validate=True, max_rounds=6, settings=None):
    """Convert to FFGL GLSL, compiling with the GPU when available. If a
    promoted constant breaks compilation, it's put back and we retry.
    `settings` defaults to the shader's <name>.ffmaker.json, if any."""
    from . import settings as S
    if settings is None:
        settings = S.load(path)
    user_excluded = S.excluded_constants(settings)
    exclude = set(user_excluded)
    res = Result()
    for _ in range(max_rounds):
        ir = C.convert(code, name=name, path=path, extract_params=extract_params,
                       promote_ints=promote_ints, exclude=exclude,
                       channels=settings.get("channels"))
        S.apply(ir, settings)
        glsl = [emit_ffgl.program_glsl(ir, p) for p in ir.programs]
        res.ir, res.ffgl_glsl = ir, glsl
        if not validate:
            res.ok = True
            return res
        try:
            from . import validate as V
            results = V.compile_programs(glsl)
        except Exception as e:     # no GPU context available
            res.ok = True
            res.log = f"(not validated: {e})"
            return res
        res.validated = True
        raw = [(k, ln, msg) for k, (ok, es, _) in enumerate(results) if not ok for ln, msg in es]
        res.log = "\n".join(log for ok, _, log in results if not ok)
        if not raw:
            res.ok = True
            res.errors = []
            return res
        res.errors = [_user_error(ir.programs[k], ln, msg) for k, ln, msg in raw]
        blamed = _blame(ir, raw)
        if not blamed:
            return res
        exclude |= blamed
        res.demoted = sorted(exclude - user_excluded)
    return res


def _user_error(prog, ln, msg):
    """Translate a program line number into the user's own section/line."""
    if not prog.label:
        return ln, msg
    if prog.line_offset and ln <= prog.line_offset:
        return ln, f"[Common] {msg}"
    return ln - prog.line_offset, f"[{prog.label}] {msg}"


def _blame(ir, raw):
    """Promoted constants mentioned on error lines."""
    if not ir.promoted:
        return set()
    blamed = set()
    beyond = False
    for k, ln, msg in raw:
        lines = ir.programs[k].code.split("\n")
        text = msg
        if 1 <= ln <= len(lines):
            text += " " + lines[ln - 1]
        else:
            beyond = True
        for nm in ir.promoted:
            if re.search(rf"\b{re.escape(nm)}\b", text):
                blamed.add(nm)
        for ph in ir.phases:        # time * slider was replaced by a phase name
            if re.search(rf"\b{ph.name}\b", text):
                blamed.update(n for n in ph.params if n in ir.promoted)
    if not blamed and beyond:
        # Error in hoisted init code — demote everything promoted to be safe.
        blamed = set(ir.promoted)
    return blamed
