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
    errors: list = field(default_factory=list)   # (line, message)
    log: str = ""
    demoted: list = field(default_factory=list)  # consts we gave up promoting


def convert_ffgl(code, name="Shader", path=None, extract_params=True, promote_ints=False,
                 validate=True, max_rounds=6):
    """Convert to FFGL GLSL, compiling with the GPU when available. If a
    promoted constant breaks compilation, it's put back and we retry."""
    exclude = set()
    res = Result()
    for _ in range(max_rounds):
        ir = C.convert(code, name=name, path=path, extract_params=extract_params,
                       promote_ints=promote_ints, exclude=exclude)
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
        errs = [e for ok, es, _ in results if not ok for e in es]
        res.log = "\n".join(log for ok, _, log in results if not ok)
        if not errs:
            res.ok = True
            res.errors = []
            return res
        res.errors = errs
        blamed = _blame(ir, errs)
        if not blamed:
            return res
        exclude |= blamed
        res.demoted = sorted(exclude)
    return res


def _blame(ir, errs):
    """Promoted constants mentioned on error lines."""
    if not ir.promoted:
        return set()
    lines = ir.programs[0].code.split("\n")
    blamed = set()
    for ln, msg in errs:
        text = msg
        if 1 <= ln <= len(lines):
            text += " " + lines[ln - 1]
        for nm in ir.promoted:
            if re.search(rf"\b{re.escape(nm)}\b", text):
                blamed.add(nm)
    if not blamed and any(ln > len(lines) for ln, _ in errs):
        # Error in hoisted init code — demote everything promoted to be safe.
        blamed = set(ir.promoted)
    return blamed
