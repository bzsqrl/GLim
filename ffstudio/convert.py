"""Front-ends and source transformations: shader text -> ShaderIR.

Strategy: leave the user's code as intact as possible and *emulate the host*
it was written for. Built-in names (TIME, iResolution, time...) are mapped to
host symbols by the emitters via #define aliases; only things that cannot be
aliased are rewritten, using the scope-aware tokenizer in glsl.py.
"""
import json
import os
import re

from . import glsl as G
from .ir import ShaderIR, Param, Image, Pass, Program, humanize

# ── Host symbols ─────────────────────────────────────────────────────────────
# Keys are abstract host features; emitters decide how to express each one.

SHADERTOY_NAMES = {
    "iTime": "time", "iGlobalTime": "time", "iTimeDelta": "timedelta",
    "iFrame": "frame", "iDate": "date", "iResolution": "resolution3",
    "iMouse": "mouse_px", "iSampleRate": "samplerate", "iFrameRate": "framerate",
    "iChannelResolution": "channelres", "iChannelTime": "channeltime",
}
ISF_NAMES = {
    "TIME": "time", "TIMEDELTA": "timedelta", "FRAMEINDEX": "frame",
    "DATE": "date", "RENDERSIZE": "resolution2", "PASSINDEX": "passindex",
    "isf_FragNormCoord": "fragnorm", "vv_FragNormCoord": "fragnorm",
}
# Names only recognised when the shader declares them as uniforms/varyings.
GLSL_UNIFORM_NAMES = {
    "time": "time", "u_time": "time", "iTime": "time", "iGlobalTime": "time",
    "uTime": "time", "resolution": "resolution", "u_resolution": "resolution",
    "iResolution": "resolution", "uResolution": "resolution",
    "mouse": "mouse_norm2", "u_mouse": "mouse_px2", "iMouse": "mouse_px",
    "surfacePosition": "surfacepos", "surfaceSize": "surfacesize",
    "iFrame": "frame", "frame": "frame", "iTimeDelta": "timedelta",
    "iDate": "date", "date": "date",
}
# Tempo from the host (FFGL SetBeatInfo), recognised in every dialect.
BEAT_NAMES = {"iBPM": "bpm", "iBeat": "beat", "iBarPhase": "barphase"}
SHADERTOY_CHANNELS = ["iChannel0", "iChannel1", "iChannel2", "iChannel3"]
SAMPLER_FILTERS = ("nearest", "linear", "mipmap")
SAMPLER_WRAPS = ("clamp", "repeat")
TIME_SYMBOLS = {"time", "timedelta", "date"}
MOUSE_SYMBOLS = {"mouse_px", "mouse_norm2", "mouse_px2"}

MAX_PROMOTED = 24

_MATH_NAME_RE = re.compile(
    r"^(m_)?(pi|tau|two_?pi|half_?pi|pi_?2|pi2|inv_?pi|e|phi|golden.*|sqrt\d|"
    r"deg2rad|rad2deg|inf|infinity|eps.*|.*epsilon.*|.*_eps|precis.*|ln2|log2e)$",
    re.I)
_MATH_VALUES = [3.14159, 6.28318, 1.5707, 0.31830, 0.15915, 1.61803, 0.61803,
                2.71828, 1.41421, 0.70710, 1.73205, 0.01745, 57.2957, 12.5663]


class ConvertError(Exception):
    pass


# ── Detection ────────────────────────────────────────────────────────────────

def find_isf_header(code):
    """Return (json_text, start, end) of the leading /*{...}*/ block or None."""
    m = re.search(r"/\*", code)
    if not m:
        return None
    end = code.find("*/", m.end())
    if end < 0:
        return None
    inner = code[m.end():end].strip()
    if not inner.startswith("{"):
        return None
    return inner, m.start(), end + 2


def detect_dialect(code):
    if find_isf_header(code):
        return "isf"
    if re.search(r"\bvoid\s+mainImage\s*\(", code):
        return "shadertoy"
    if re.search(r"\bvoid\s+main\s*\(", code):
        return "glsl"
    raise ConvertError("Unrecognised shader: no ISF header, no mainImage() and no main().")


def sanitize_json(text):
    """Lenient ISF JSON: strip // comments and trailing commas outside strings."""
    out = []
    pattern = r'("(?:\\.|[^"\\])*")|(//[^\n]*)|(,\s*(?=[\]}]))'
    for m in re.finditer(pattern + r"|([^\"/,]+|.)", text, re.S):
        if m.group(1):
            out.append(m.group(1))
        elif m.group(2) or m.group(3):
            out.append("")
        else:
            out.append(m.group(0))
    return "".join(out)


# ── Public entry point ───────────────────────────────────────────────────────

def convert(code, name="Shader", path=None, extract_params=True, promote_ints=False,
            exclude=(), dialect=None, channels=None):
    """Parse + transform shader source into a ShaderIR."""
    code = code.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    if dialect is None:
        from . import shadertoy_project
        if shadertoy_project.is_project(code):
            return _convert_project(code, name, path, extract_params, promote_ints, exclude)
    dialect = dialect or detect_dialect(code)
    ir = ShaderIR(name=name, dialect=dialect)
    header = None
    if dialect == "isf":
        hdr = find_isf_header(code)
        try:
            header = json.loads(sanitize_json(hdr[0]))
        except json.JSONDecodeError as e:
            raise ConvertError(f"ISF JSON header is invalid: {e}")
        # Blank the header but keep its newlines so line numbers still match the file.
        code = code[:hdr[1]] + "\n" * code[hdr[1]:hdr[2]].count("\n") + code[hdr[2]:]
        _isf_header_to_ir(header, ir, path)

    vertex = None
    if dialect == "isf" and path:
        vs_path = os.path.splitext(path)[0] + ".vs"
        if os.path.isfile(vs_path):
            with open(vs_path, encoding="utf-8", errors="replace") as f:
                vertex = _vertex_prelude(f.read(), ir)
    prog = _build_program(code, ir, path, extract_params, exclude, promote_ints,
                          directives={**channel_directives(code), **(channels or {})}
                          if dialect == "shadertoy" else None,
                          vertex=vertex)
    prog.force_opaque = dialect != "isf"
    ir.programs.append(prog)
    if not ir.passes:
        ir.passes.append(Pass())
    _finish(ir, header)
    return ir


def _build_program(code, ir, path, extract_params, exclude, promote_ints, directives=None,
                   label="", line_offset=0, channels=None, vertex=None):
    """Run the token pipeline on one program's source and return a Program."""
    # Each phase gets a fresh token list so it sees earlier rewrites.
    retok = lambda t: G.tokenize(G.untokenize(t))
    toks = G.tokenize(code)
    _normalize(toks, ir)
    aliases = {}
    toks = retok(toks)
    _map_uniform_decls(toks, ir, aliases)
    toks = retok(toks)
    _map_varyings(toks, ir, skip=vertex["varyings"] if vertex else ())
    toks = retok(toks)
    _map_distinctive_names(toks, ir, aliases)
    if ir.dialect == "shadertoy" and directives is not None:
        _shadertoy_images(toks, ir, directives, path)

    if extract_params and ir.dialect != "isf":
        _promote_constants(toks, ir, set(exclude), promote_ints)
        toks = retok(toks)
    _rate_phases(toks, ir, aliases)
    toks = retok(toks)

    _zero_init(toks)
    toks = retok(toks)

    dynamic = set(aliases) | {p.name for p in ir.params if p.name} | {i.name for i in ir.images}
    dynamic |= {ph.name for ph in ir.phases}
    dynamic |= {p.target for p in ir.passes if p.target}
    hoisted = _hoist_globals(toks, dynamic)
    toks = retok(toks)
    _strip_local_consts(toks, dynamic)
    toks = retok(toks)
    entry = _entry_point(toks, ir)
    _rename_frag_outputs(toks)
    prelude = ""
    if vertex:
        prelude = vertex["code"]
        for k, v in vertex["aliases"].items():
            aliases.setdefault(k, v)
    return Program(code=G.untokenize(toks), entry=entry, aliases=aliases, hoisted=hoisted,
                   label=label, line_offset=line_offset, channels=channels, prelude=prelude)


def _vertex_prelude(vs_code, ir):
    """Turn an ISF .vs vertex shader into code run per pixel: its varyings
    become globals and main() becomes ffm_vs_main()."""
    vs_code = vs_code.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    toks = G.tokenize(vs_code)
    _normalize(toks, ir)
    toks = G.tokenize(G.untokenize(toks))
    sig = G.significant(toks)
    for pos, k in enumerate(sig):
        t = toks[k]
        if t.kind == "ident" and t.text in ("isf_vertShaderInit", "vv_vertShaderInit"):
            j = pos
            while j < len(sig) and toks[sig[j]].text != ";":
                toks[sig[j]].text = ""
                j += 1
            if j < len(sig):
                toks[sig[j]].text = ""
        elif t.kind == "ident" and t.text == "gl_Position":
            t.text = "ffm_vsPosition"
    varyings = set()
    for it in G.analyze(toks):
        if it.kind == "decl":
            q = [x for x in it.qualifiers if x in ("varying", "out")]
            for x in q:
                G.blank(toks, it.qual_idx[x], it.qual_idx[x])
                varyings.update(d.name for d in it.decls)
            if "uniform" in it.qualifiers:
                _replace_range(toks, it.start, it.end, "")
        elif it.kind == "func" and it.name == "main":
            toks[it.name_idx].text = "ffm_vs_main"
    aliases = {}
    _map_distinctive_names(G.tokenize(G.untokenize(toks)), ir, aliases)
    code = "vec4 ffm_vsPosition;\n// ── from ISF vertex shader (.vs) ──\n" + G.untokenize(toks)
    return {"code": code, "aliases": aliases, "varyings": varyings}


def _finish(ir, header):
    used = set()
    for prog in ir.programs:
        used |= set(prog.aliases.values())
    if used & TIME_SYMBOLS or "time" in used:
        if not any(p.kind == "speed" for p in ir.params):
            ir.params.insert(0, Param("", "speed", "Speed", 1.0, 0.0, 4.0, origin="synthetic"))
    if used & MOUSE_SYMBOLS:
        default = [0.5, 0.5] if "mouse_norm2" in used else [0.0, 0.0]
        ir.params.append(Param("", "mouse", "Mouse", default, [0.0, 0.0], [1.0, 1.0],
                               glsl_type="vec2", origin="synthetic"))
        ir.params.append(Param("", "mouseclick", "Mouse Click", False, glsl_type="bool",
                               origin="synthetic"))
    if any(i.source == "audio" for i in ir.images):
        ir.params.append(Param("", "fft", "Audio Spectrum", 0.0, origin="synthetic"))
    _decide_kind(ir, header)
    _dedupe_labels(ir)


# ── Multi-pass Shadertoy projects ────────────────────────────────────────────

def _convert_project(code, name, path, extract_params, promote_ints, exclude):
    from . import shadertoy_project as SP
    passes = SP.parse(code, path)
    common = next((p for p in passes if p.name == "Common"), None)
    image = next((p for p in passes if p.name == "Image"), None)
    if image is None:
        raise ConvertError("Shadertoy project has no Image pass.")
    ir = ShaderIR(name=name, dialect="shadertoy")
    info = getattr(image, "info", {}) or {}
    credit = ""
    if info.get("author"):
        credit = f"{info['author']} - https://www.shadertoy.com/view/{info.get('id', '')}"
    ir.meta = {"description": info.get("name") or name, "credit": credit}
    buffers = [p for p in passes if p.name.startswith("Buffer")]
    # Targets first so every program knows the buffer sampler names.
    for p in buffers:
        ir.passes.append(Pass(target="ffm_buf" + p.name[-1], persistent=True, float=True))

    def sampler_for(spec, pass_name, ch, opts):
        kind = spec[0]
        suffix = sampler_suffix(opts, kind)
        if kind == "buffer":
            if not any(b.name == "Buffer " + spec[1] for b in buffers):
                ir.warnings.append(f"{pass_name} iChannel{ch} reads Buffer {spec[1]}, which doesn't exist.")
                return _add_image(ir, Image("ffm_none", "none"))
            if not suffix:
                return "ffm_buf" + spec[1]
            return _add_image(ir, _apply_sampler(Image(f"ffm_buf{spec[1]}{suffix}", "target",
                                                       target="ffm_buf" + spec[1]), opts))
        if kind == "input":
            return _add_image(ir, _apply_sampler(Image("ffm_input" + suffix, "host", 0), opts))
        if kind == "audio":
            return _add_image(ir, Image("ffm_audio", "audio", rows=2, isf_type="audioFFT"))
        if kind == "noise":
            return _add_image(ir, _apply_sampler(Image("ffm_noise" + suffix, "imported", repeat=True), opts))
        if kind == "file":
            # One base name per file; each sampler setting adds its own suffix.
            if spec[1] not in tex_names:
                if not os.path.isfile(spec[1]):
                    ir.warnings.append(f"{pass_name} iChannel{ch} image '{spec[1]}' not found; using noise.")
                tex_names[spec[1]] = f"ffm_tex{len(tex_names)}"
            return _add_image(ir, _apply_sampler(Image(tex_names[spec[1]] + suffix, "imported", path=spec[1],
                                                       repeat=True), opts))
        return _add_image(ir, Image("ffm_none", "none"))

    tex_names = {}
    prefix = (common.code + "\n") if common else ""
    offset = prefix.count("\n")
    for p in buffers + [image]:
        src = prefix + p.code
        toks = G.tokenize(src)
        used = G.used_names(toks)
        mapping, chans = {}, [None] * 4
        for ch in range(4):
            nm = f"iChannel{ch}"
            if nm in used:
                spec = p.channels.get(ch) or (("input",) if p.name == "Image" and ch == 0 else ("none",))
                mapping[nm] = chans[ch] = sampler_for(spec, p.name, ch, p.samplers.get(ch, {}))
        G.rename_everywhere(toks, mapping)
        prog = _build_program(G.untokenize(toks), ir, path, extract_params, exclude, promote_ints,
                              label=p.name, line_offset=offset, channels=chans)
        prog.force_opaque = p.name == "Image"
        ir.programs.append(prog)
        if p.name == "Image":
            ir.passes.append(Pass(program=len(ir.programs) - 1))
        else:
            next(x for x in ir.passes if x.target == "ffm_buf" + p.name[-1]).program = len(ir.programs) - 1
    _finish(ir, None)
    return ir


def _add_image(ir, image):
    if not any(i.name == image.name for i in ir.images):
        ir.images.append(image)
    return image.name


# ── ISF header ───────────────────────────────────────────────────────────────

def _isf_header_to_ir(h, ir, path):
    ir.meta = {
        "description": h.get("DESCRIPTION", ""),
        "credit": h.get("CREDIT", ""),
        "categories": h.get("CATEGORIES", []),
        "isfvsn": h.get("ISFVSN", ""),
    }
    host_index = 0
    for inp in h.get("INPUTS", []):
        name = str(inp.get("NAME", "")).strip()
        t = str(inp.get("TYPE", "float")).strip().lower()
        if not name:
            continue
        label = inp.get("LABEL", "") or humanize(name)
        if t == "float":
            d = _f(inp.get("DEFAULT"), 0.5)
            mn = _f(inp.get("MIN"), 0.0)
            mx = _f(inp.get("MAX"), 1.0)
            mn, mx = min(mn, mx, d), max(mn, mx, d)
            if mn == mx:
                mx = mn + 1.0
            ir.params.append(Param(name, "float", label, d, mn, mx))
        elif t in ("bool", "boolean"):
            ir.params.append(Param(name, "bool", label, bool(inp.get("DEFAULT", False)), glsl_type="bool"))
        elif t == "event":
            ir.params.append(Param(name, "event", label, False, glsl_type="bool"))
        elif t == "long":
            values = inp.get("VALUES")
            labels = inp.get("LABELS")
            if not values:
                if labels:
                    values = list(range(len(labels)))
                else:
                    lo, hi = int(_f(inp.get("MIN"), 0)), int(_f(inp.get("MAX"), 1))
                    values = list(range(lo, hi + 1))
            values = [int(_f(v, 0)) for v in values]
            labels = [str(l) for l in (labels or values)]
            labels = (labels + [str(v) for v in values[len(labels):]])[:len(values)]
            d = int(_f(inp.get("DEFAULT"), values[0]))
            ir.params.append(Param(name, "long", label, d, glsl_type="int", labels=labels, values=values))
        elif t == "color":
            d = inp.get("DEFAULT", [1.0, 1.0, 1.0, 1.0])
            d = [_f(c, 1.0) for c in (list(d) if isinstance(d, (list, tuple)) else [])] + [1.0] * 4
            ir.params.append(Param(name, "color", label, d[:4], glsl_type="vec4"))
        elif t == "point2d":
            d = inp.get("DEFAULT", [0.0, 0.0])
            d = [_f(c, 0.0) for c in (list(d) if isinstance(d, (list, tuple)) else [0, 0])][:2] + [0.0, 0.0]
            mn, mx = inp.get("MIN"), inp.get("MAX")
            if isinstance(mn, (list, tuple)) and isinstance(mx, (list, tuple)) and len(mn) >= 2 and len(mx) >= 2:
                p = Param(name, "point2D", label, d[:2], [_f(mn[0], 0), _f(mn[1], 0)],
                          [_f(mx[0], 1), _f(mx[1], 1)], glsl_type="vec2")
            else:
                p = Param(name, "point2D", label, d[:2], [0.0, 0.0], [1.0, 1.0], glsl_type="vec2",
                          pixel_space=True)
            ir.params.append(p)
        elif t == "image":
            ir.images.append(Image(name, "host", host_index))
            host_index += 1
        elif t in ("audio", "audiofft"):
            ir.images.append(Image(name, "audio", rows=1, isf_type=inp.get("TYPE")))
            if t == "audio":
                ir.warnings.append(f"'{name}' asks for an audio waveform; FFGL hosts only provide the "
                                   f"spectrum (FFT), so it receives that instead.")
        else:
            ir.warnings.append(f"Input '{name}' has unsupported type '{t}' and was skipped.")

    imported = h.get("IMPORTED", {})
    if isinstance(imported, dict):
        imported = [dict(v, NAME=k) for k, v in imported.items() if isinstance(v, dict)]
    for imp in imported or []:
        nm = imp.get("NAME")
        if not nm:
            continue
        p = imp.get("PATH", "")
        if path and p:
            p = os.path.join(os.path.dirname(path), p)
        ir.images.append(Image(nm, "imported", path=p, repeat=False))
        if not (p and os.path.isfile(p)):
            ir.warnings.append(f"Imported image '{nm}' ({imp.get('PATH', '')}) was not found; "
                               f"a noise texture is used instead.")

    for i, p in enumerate(h.get("PASSES", []) or []):
        ir.passes.append(Pass(
            target=p.get("TARGET") or None,
            persistent=bool(p.get("PERSISTENT", False)),
            float=bool(p.get("FLOAT", False)),
            width=str(p["WIDTH"]) if "WIDTH" in p else None,
            height=str(p["HEIGHT"]) if "HEIGHT" in p else None,
        ))
    if ir.passes and ir.passes[-1].target and not any(p.target is None for p in ir.passes):
        # Every pass renders to a buffer: ISF shows the last one.
        ir.warnings.append("All passes have targets; the last pass is also drawn to the output.")


def _f(v, default):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float(default)


# ── Normalization passes ─────────────────────────────────────────────────────

def _normalize(toks, ir):
    """Strip directives desktop GL rejects, map legacy functions, rename
    identifiers that are reserved in GLSL 4.10."""
    for t in toks:
        if t.kind == "preproc":
            m = re.match(r"\s*#\s*(version|extension)\b", t.text)
            if m:
                t.text = "\n" * t.text.count("\n")
                t.kind = "nl" if t.text else "ws"

    declared = G.declared_names(toks)
    renames = {}
    # FFStudio reserves the ffm_ prefix for its host layer (e.g. re-imported exports).
    for nm in declared:
        if nm.startswith("ffm_"):
            renames[nm] = "user_" + nm
    # A user variable called 'texture' collides with the texture() builtin we map to.
    if "texture" in declared:
        renames["texture"] = "texture_"
    for old, new in G.LEGACY_RENAMES.items():
        if old not in declared:
            renames[old] = new
    for w in G.RESERVED_IN_410:
        renames.setdefault(w, w + "_")
    # Polyfills of built-ins that GLSL ES 1.00 lacked (round, tanh, inverse...)
    # are redefinitions in 4.10. Other same-named user functions are legal overloads.
    user_funcs = {it.name for it in G.analyze(toks) if it.kind in ("func", "proto")}
    for f in user_funcs & G.ES1_MISSING_BUILTINS:
        renames[f] = f + "_u"
        ir.warnings.append(f"Renamed user function '{f}' (it clashes with a GLSL 4.1 built-in).")
    # Never rename qualifiers that are used *as qualifiers* (e.g. 'flat in').
    _rename_outside_qualifier_use(toks, renames)


def _rename_outside_qualifier_use(toks, renames):
    sig = G.significant(toks)
    for pos, k in enumerate(sig):
        t = toks[k]
        if t.kind != "ident" or t.text not in renames:
            continue
        if pos > 0 and toks[sig[pos - 1]].text == ".":
            continue
        nxt = toks[sig[pos + 1]] if pos + 1 < len(sig) else None
        if t.text in G.QUALIFIERS and nxt is not None and nxt.kind == "ident" and (
                nxt.text in G.TYPES or nxt.text in G.QUALIFIERS):
            continue          # genuine qualifier usage
        if t.text == "texture" and nxt is not None and nxt.text == "(":
            continue          # builtin call, keep
        t.text = renames[t.text]
    # Preprocessor lines (#define X texture2D(...)) need the same legacy mapping.
    legacy = {k: v for k, v in renames.items() if k in G.LEGACY_RENAMES}
    for t in toks:
        if t.kind == "preproc" and legacy:
            t.text = re.sub(r"\b(" + "|".join(legacy) + r")\b", lambda m: legacy[m.group(1)], t.text)


def _replace_range(toks, i, j, text):
    """Replace tokens i..j with text, keeping total newline count."""
    old_nl = sum(toks[k].text.count("\n") for k in range(i, j + 1))
    G.blank(toks, i, j)
    pad = old_nl - text.count("\n")
    toks[i].text = text + "\n" * max(pad, 0)
    toks[i].kind = "raw"


def _map_uniform_decls(toks, ir, aliases):
    """Turn user `uniform` declarations into host aliases, images or params."""
    for it in G.analyze(toks):
        if it.kind != "decl" or "uniform" not in it.qualifiers:
            continue
        for d in it.decls:
            nm, ty = d.name, it.type
            if nm in SHADERTOY_CHANNELS or ty.startswith("sampler") or ty.startswith("isampler"):
                if not any(i.name == nm for i in ir.images):
                    ir.images.append(Image(nm, "host", len([i for i in ir.images if i.source == "host"])))
                continue
            sym = GLSL_UNIFORM_NAMES.get(nm) or SHADERTOY_NAMES.get(nm) or ISF_NAMES.get(nm) \
                or BEAT_NAMES.get(nm)
            if sym == "resolution":
                sym = "resolution3" if ty == "vec3" else "resolution2"
            if sym:
                if sym == "time" and ty != "float":
                    sym = None
            if sym:
                aliases[nm] = sym
            elif ir.param(nm) is None:
                ir.params.append(_param_for_uniform(nm, ty))
        _replace_range(toks, it.start, it.end, "")


def _param_for_uniform(nm, ty):
    if ty == "float":
        return Param(nm, "float", humanize(nm), 0.5, 0.0, 1.0, origin="uniform")
    if ty == "int":
        return Param(nm, "int", humanize(nm), 1, 0, 10, glsl_type="int", origin="uniform")
    if ty == "bool":
        return Param(nm, "bool", humanize(nm), False, glsl_type="bool", origin="uniform")
    if ty in ("vec3", "vec4"):
        return Param(nm, "color", humanize(nm), [1.0, 1.0, 1.0, 1.0], glsl_type=ty, origin="uniform")
    if ty == "vec2":
        return Param(nm, "point2D", humanize(nm), [0.5, 0.5], [0.0, 0.0], [1.0, 1.0],
                     glsl_type="vec2", origin="uniform")
    return Param(nm, "float", humanize(nm), 0.5, 0.0, 1.0, origin="uniform")


def _map_varyings(toks, ir, skip=()):
    """`varying`/`in` globals in fragment code (ISF .vs companions, sandbox
    surfacePosition) become plain globals or host aliases."""
    for it in G.analyze(toks):
        if it.kind != "decl":
            continue
        q = [x for x in it.qualifiers if x in ("varying", "in")]
        if not q:
            continue
        names = [d.name for d in it.decls]
        if names and all(n in skip for n in names):   # declared by the .vs prelude
            _replace_range(toks, it.start, it.end, "")
            continue
        if names == ["surfacePosition"]:
            _replace_range(toks, it.start, it.end, "")
            continue
        for x in q:
            G.blank(toks, it.qual_idx[x], it.qual_idx[x])
        ir.warnings.append(
            f"Varying(s) {', '.join(names)} came from a vertex shader that FFStudio cannot run; "
            f"they will be zero.")


def _map_distinctive_names(toks, ir, aliases):
    """Alias Shadertoy/ISF built-ins that are used but never declared."""
    declared = G.declared_names(toks)
    used = set()
    for t in toks:
        if t.kind == "ident":
            used.add(t.text)
        elif t.kind == "preproc":
            used.update(re.findall(r"[A-Za-z_]\w*", t.text))
    table = dict(SHADERTOY_NAMES)
    table.update(ISF_NAMES)
    table.update(BEAT_NAMES)
    table["surfacePosition"] = "surfacepos"
    for nm, sym in table.items():
        if nm in used and nm not in declared and nm not in aliases:
            aliases[nm] = sym


# `ffstudio:`, or `ffmaker:` (FFStudio's former name; still accepted in existing shaders).
_CHANNEL_DIRECTIVE = re.compile(r"//\s*@?ff(?:maker|studio)\s*:?\s*(iChannel[0-3])\s*=\s*(.+?)\s*$", re.I | re.M)


def channel_directives(code):
    """`// ffstudio: iChannel1 = rock.jpg` lines -> {channel: value}."""
    return {m.group(1): m.group(2) for m in _CHANNEL_DIRECTIVE.finditer(code)}


def split_channel_options(value):
    """'rock.jpg filter=nearest wrap=repeat vflip=false' -> ('rock.jpg', options).
    Options mirror Shadertoy's per-channel sampler settings."""
    words = value.split()
    opts = {}
    while len(words) > 1 and "=" in words[-1]:
        key, _, v = words.pop().partition("=")
        opts.update(sampler_options({key.lower(): v}))
    return " ".join(words).strip().strip("\"'"), opts


def sampler_options(sampler):
    """Shadertoy sampler dict ({"filter": "nearest", "wrap": "repeat", "vflip": "false"})
    -> the subset FFStudio supports, normalised."""
    out = {}
    f = str(sampler.get("filter", "")).lower().strip("\"'")
    w = str(sampler.get("wrap", "")).lower().strip("\"'")
    v = str(sampler.get("vflip", "")).lower().strip("\"'")
    if f in SAMPLER_FILTERS:
        out["filter"] = f
    if w in SAMPLER_WRAPS:
        out["wrap"] = w
    if v in ("true", "false"):
        out["vflip"] = v == "true"
    return out


def _apply_sampler(im, opts):
    """Set an Image's sampler fields from channel options; returns im."""
    if im.source == "imported":
        if "wrap" in opts:
            im.repeat = opts["wrap"] == "repeat"
        im.flip = opts.get("vflip", True)
    elif "wrap" in opts:
        im.wrap = opts["wrap"]
    if im.source != "audio":
        im.filter = opts.get("filter", "")
    return im


def sampler_suffix(opts, kind):
    """Name suffix for a channel whose sampler differs from the source's
    defaults (Shadertoy: textures mipmap/repeat/vflip, everything else
    linear/clamp), so each setting gets its own sampler uniform."""
    if kind == "file" or kind == "noise":
        defaults = {"filter": "mipmap", "wrap": "repeat", "vflip": True}
    else:
        defaults = {"filter": "linear", "wrap": "clamp"}
        opts = {k: v for k, v in opts.items() if k != "vflip"}
    diff = {k: v for k, v in opts.items() if defaults.get(k) != v}
    if not diff:
        return ""
    return "_" + "".join({"nearest": "n", "linear": "l", "mipmap": "m", "clamp": "c", "repeat": "r",
                          True: "v", False: "f"}[diff[k]] for k in ("filter", "wrap", "vflip") if k in diff)


def _shadertoy_images(toks, ir, directives=None, path=None):
    used = G.used_names(toks)
    directives = directives or {}
    for ch in SHADERTOY_CHANNELS:
        if ch not in used or any(i.name == ch for i in ir.images):
            continue
        val, opts = split_channel_options(directives.get(ch, "input").strip())
        if val.lower() in ("input", "clip", "host"):
            im = Image(ch, "host", 0)
        elif val.lower() in ("audio", "sound", "fft", "music"):
            im = Image(ch, "audio", rows=2, isf_type="audioFFT")
        elif val.lower() == "noise":
            im = Image(ch, "imported", repeat=True)
        else:
            p = val
            if path and not os.path.isabs(p):
                p = os.path.join(os.path.dirname(path), p)
            im = Image(ch, "imported", path=p, repeat=True)
            if not os.path.isfile(p):
                ir.warnings.append(f"{ch} image '{val}' was not found; a noise texture is used instead.")
        ir.images.append(_apply_sampler(im, opts))
    ir.images.sort(key=lambda i: i.name)


# ── Constant promotion ───────────────────────────────────────────────────────

def _const_statements(toks):
    """All `const TYPE NAME = init` declarations (global and local):
    list of (name, type, init_span, global_item_or_None, decl)."""
    out = []
    for it in G.analyze(toks):
        if it.kind == "decl" and "const" in it.qualifiers:
            for d in it.decls:
                out.append((d.name, it.type, d.init_span, it, d))
        elif it.kind == "func":
            for local in _local_decls(toks, it.body[0] + 1, it.body[1]):
                if "const" in local.qualifiers:
                    for d in local.decls:
                        out.append((d.name, local.type, d.init_span, None, d))
    return out


def _local_decls(toks, start, end):
    """Declarations inside a function body (statement-level only)."""
    res = []
    i = start
    stmt_start = start
    while i < end:
        t = toks[i]
        if t.kind == "punct" and t.text in (";", "{", "}"):
            stmt_start = i + 1
        elif t.kind == "punct" and t.text == "(":
            i = G.match_close(toks, i)
        elif t.kind == "ident" and t.text == "const" and _is_stmt_start(toks, i, stmt_start):
            j = i
            depth = 0
            while j < end:
                tj = toks[j]
                if tj.kind == "punct":
                    if tj.text in ("(", "[", "{"):
                        depth += 1
                    elif tj.text in (")", "]", "}"):
                        depth -= 1
                    elif tj.text == ";" and depth == 0:
                        break
                j += 1
            item = G._classify(toks, i, j)
            if item.kind == "decl":
                res.append(item)
            i = j
            stmt_start = j + 1
        i += 1
    return res


def _is_stmt_start(toks, i, stmt_start):
    return all(toks[k].kind in G.TRIVIA for k in range(stmt_start, i))


def _required_const_names(toks, struct_names):
    """Identifiers that appear where GLSL demands a constant expression."""
    req = set()
    sig = G.significant(toks)
    for pos, k in enumerate(sig):
        t = toks[k]
        if t.text == "[" and t.kind == "punct" and pos > 0:
            p = toks[sig[pos - 1]]
            pp = toks[sig[pos - 2]] if pos > 1 else None
            is_size = p.text in G.TYPES or p.text in struct_names or (
                p.kind == "ident" and pp is not None and (pp.text in G.TYPES or pp.text in struct_names))
            if is_size:
                close = G.match_close(toks, k)
                req.update(G.idents_in(toks, k, close))
        elif t.kind == "ident" and t.text == "case":
            j = pos + 1
            while j < len(sig) and toks[sig[j]].text != ":":
                if toks[sig[j]].kind == "ident":
                    req.add(toks[sig[j]].text)
                j += 1
        elif t.kind == "ident" and t.text == "layout":
            if pos + 1 < len(sig) and toks[sig[pos + 1]].text == "(":
                req.update(G.idents_in(toks, sig[pos + 1], G.match_close(toks, sig[pos + 1])))
    for t in toks:
        if t.kind == "preproc":
            body = re.sub(r"^\s*#\s*define\s+\w+(\([^)]*\))?", "", t.text)
            if re.match(r"\s*#\s*(if|elif|ifdef|ifndef)", t.text):
                req.update(re.findall(r"[A-Za-z_]\w*", t.text))
            elif re.match(r"\s*#\s*define", t.text):
                # A macro body is pasted wherever it's used; treat as required
                # only if it sizes an array, which we can't see — be conservative
                # for macros used inside other #if lines handled above.
                pass
    return req


def _promote_constants(toks, ir, exclude, promote_ints):
    items = G.analyze(toks)
    struct_names = set()
    for it in items:
        if it.kind == "struct":
            m = re.search(r"\bstruct\s+(\w+)", G.untokenize(toks[it.start:it.end + 1]))
            if m:
                struct_names.add(m.group(1))

    consts = _const_statements(toks)
    deps = {}
    for nm, ty, span, gitem, d in consts:
        deps.setdefault(nm, set()).update(G.idents_in(toks, *span) if span else [])

    # Candidates: global consts with literal initialisers + float #defines.
    candidates = []       # (name, kind, glsl_type, values, where)
    for nm, ty, span, gitem, d in consts:
        if gitem is None or not span or d.array_span:
            continue
        vals = G.parse_literal_vector(G.untokenize(toks[span[0]:span[1] + 1]))
        if ty == "bool":
            txt = G.untokenize(toks[span[0]:span[1] + 1]).strip()
            if txt in ("true", "false"):
                candidates.append((nm, "bool", "bool", [txt == "true"], ("decl", gitem, d)))
            continue
        if vals is None:
            continue
        if ty == "float" or (ty == "int" and promote_ints):
            candidates.append((nm, "float" if ty == "float" else "int", ty, vals, ("decl", gitem, d)))
        elif ty in ("vec3", "vec4") and all(0.0 <= v <= 1.0 for v in vals):
            candidates.append((nm, "color", ty, vals, ("decl", gitem, d)))
    define_re = re.compile(r"^\s*#\s*define\s+([A-Za-z_]\w*)\s+\(?\s*([-+]?(?:\d+\.\d*|\.\d+)(?:[eE][-+]?\d+)?)[fF]?\s*\)?\s*(?://.*)?$")
    preproc_text = [t.text for t in toks if t.kind == "preproc"]
    for idx, t in enumerate(toks):
        if t.kind == "preproc":
            m = define_re.match(t.text.rstrip())
            if m:
                nm = m.group(1)
                others = [p for p in preproc_text if p is not t.text and re.search(rf"\b{nm}\b", p)]
                if not others:
                    candidates.append((nm, "float", "float", [float(m.group(2))], ("define", idx)))

    required = _required_const_names(toks, struct_names)
    # Closure: anything a required constant depends on is required too.
    stack = list(required)
    while stack:
        nm = stack.pop()
        for dep in deps.get(nm, ()):
            if dep not in required:
                required.add(dep)
                stack.append(dep)

    chosen = []
    for c in candidates:
        nm, kind, ty, vals, where = c
        if nm in exclude or nm in required or _looks_mathematical(nm, vals):
            continue
        prior = ir.param(nm)
        if (prior and prior.origin not in ("const", "define")) or nm in SHADERTOY_NAMES or nm in ISF_NAMES \
                or nm in BEAT_NAMES:
            continue
        chosen.append(c)
        if len(chosen) >= MAX_PROMOTED:
            break

    by_item = {}
    for nm, kind, ty, vals, where in chosen:
        if kind == "float":
            v = vals[0]
            mn, mx = (0.0, 2.0 * v) if v > 0 else ((2.0 * v, -2.0 * v) if v < 0 else (-1.0, 1.0))
            p = Param(nm, "float", humanize(nm), v, mn, mx, origin="const")
        elif kind == "int":
            v = int(vals[0])
            p = Param(nm, "int", humanize(nm), v, 0 if v >= 0 else 2 * v, max(2 * v, 1) if v >= 0 else 0,
                      glsl_type="int", origin="const")
        elif kind == "bool":
            p = Param(nm, "bool", humanize(nm), vals[0], glsl_type="bool", origin="const")
        else:
            p = Param(nm, "color", humanize(nm), (vals + [1.0])[:4], glsl_type=ty, origin="const")
        prior = ir.param(nm)
        if where[0] == "define":
            p.origin = "define"
            t = toks[where[1]]
            t.text = "\n" * t.text.count("\n")
            t.kind = "nl" if t.text else "ws"
        else:
            by_item.setdefault(id(where[1]), (where[1], set()))[1].add(nm)
        if prior is None:
            ir.params.append(p)
            ir.promoted.append(nm)

    for item, names in by_item.values():
        keep = [d for d in item.decls if d.name not in names]
        if not keep:
            _replace_range(toks, item.start, item.end, "")
        else:
            prefix = G.untokenize(toks[item.start:item.decls[0].name_idx])
            parts = [G.untokenize(toks[d.name_idx:(d.init_span[1] if d.init_span else d.name_idx) + 1]) for d in keep]
            _replace_range(toks, item.start, item.end, prefix + ", ".join(parts) + ";")


def _looks_mathematical(name, vals):
    if _MATH_NAME_RE.match(name):
        return True
    if len(vals) == 1:
        v = abs(vals[0])
        if 0 < v < 1e-3 or v > 1e4:
            return True
        if any(abs(v - m) < 1e-3 for m in _MATH_VALUES):
            return True
    return False


# ── Rate params: time * slider becomes a running total ──────────────────────
# `iTime * speed` jumps the animation when the slider moves, because it scales
# the whole elapsed time. The host instead keeps phase += speed * frame time
# (an ir.Phase) and the shader reads that, so the slider changes the rate only.

_MAX_PHASE_PARAMS = 4
_VEC_CTORS = {"vec2": 2, "vec3": 3, "vec4": 4}


def _rate_phases(toks, ir, aliases):
    times = {n for n, s in aliases.items() if s == "time"}
    rates = {p.name for p in ir.params if p.name and p.kind == "float" and p.glsl_type == "float"}
    if not times or not rates:
        return
    _rewrite_rate_products(toks, ir, times, rates, scoped=True)
    # Products inside #define bodies too (`#define T (iTime * speed)`).
    for t in toks:
        if t.kind != "preproc":
            continue
        m = re.match(r"(\s*#\s*define\s+\w+(?:\([^)]*\))?)(.*)$", t.text, re.S)
        if m and any(re.search(rf"\b{re.escape(n)}\b", m.group(2)) for n in times):
            body = G.tokenize(m.group(2))
            _rewrite_rate_products(body, ir, times, rates, scoped=False)
            t.text = m.group(1) + G.untokenize(body)


def _local_names(toks):
    """(start, end, names) per function: names declared as its parameters or
    locals (`TYPE name`), which shadow params of the same name."""
    out = []
    for it in G.analyze(toks):
        if it.kind != "func" or not it.params or not it.body:
            continue
        names, prev = set(), None
        for k in range(it.params[0], it.body[1] + 1):
            t = toks[k]
            if t.kind in G.TRIVIA:
                continue
            if t.kind == "ident" and prev is not None and prev.text in G.TYPES:
                names.add(t.text)
            prev = t
        out.append((it.params[0], it.body[1], names))
    return out


def _rewrite_rate_products(toks, ir, times, rates, scoped):
    n = 0
    for _ in range(10000):
        sig = G.significant(toks)
        occ = [j for j, k in enumerate(sig) if toks[k].kind == "ident" and toks[k].text in times
               and not (j > 0 and toks[sig[j - 1]].text == ".")]
        if n >= len(occ):
            return
        shadowed = set()
        if scoped:
            k = sig[occ[n]]
            for a, b, names in _local_names(toks):
                if a <= k <= b:
                    shadowed = names
        if not _rewrite_one(toks, sig, occ[n], ir, times, rates - shadowed):
            n += 1


def _rewrite_one(toks, sig, j, ir, times, rates):
    """Rewrite the product containing the time name at sig[j]. False if it
    doesn't multiply time by sliders in a form that can be integrated."""
    txt = lambda jj: toks[sig[jj]].text if 0 <= jj < len(sig) else ""

    kind = lambda jj: toks[sig[jj]].kind if 0 <= jj < len(sig) else ""

    def match_open(e):
        depth = 0
        for s in range(e, -1, -1):
            if txt(s) in (")", "]"):
                depth += 1
            elif txt(s) in ("(", "["):
                depth -= 1
                if depth == 0:
                    return s
        return None

    def back(e):
        """Start of the postfix expression ending at e (ident, number, f(..), (..), x.y, a[i])."""
        while True:
            if txt(e) == "]":                 # a[i]: continue with the base expression
                s = match_open(e)
                if s is None:
                    return None
                e = s - 1
                continue
            if txt(e) == ")":
                s = match_open(e)
                if s is None:
                    return None
                start = s - 1 if kind(s - 1) == "ident" else s     # call or parentheses
            elif kind(e) in ("ident", "number"):
                start = e
            else:
                return None
            if txt(start - 1) == ".":         # x.y: continue with x
                e = start - 2
                continue
            return start

    def fwd(s):
        """End of the postfix expression starting at s."""
        if txt(s) == "(":
            e = sig.index(G.match_close(toks, sig[s]), s)
        elif kind(s) in ("ident", "number"):
            e = s
            if txt(s + 1) == "(":
                e = sig.index(G.match_close(toks, sig[s + 1]), s)
        else:
            return None
        while txt(e + 1) in ("[", "."):
            if txt(e + 1) == "[":
                e = sig.index(G.match_close(toks, sig[e + 1]), e)
            elif kind(e + 2) == "ident":
                e += 2
            else:
                return None
        return e

    # Factors joined by '*' around the time name; a factor after '/' is a divisor.
    factors = [(j, j)]
    s = j
    while txt(s - 1) == "*":
        b = back(s - 2)
        if b is None or txt(b - 1) == "/":
            break
        factors.insert(0, (b, s - 2))
        s = b
    e = j
    while txt(e + 1) == "*":
        f = fwd(e + 2)
        if f is None:
            break
        factors.append((e + 2, f))
        e = f

    def single(f, names):
        return f[0] == f[1] and toks[sig[f[0]]].kind == "ident" and toks[sig[f[0]]].text in names

    if sum(single(f, times) for f in factors) != 1:
        return False
    params = [f for f in factors if single(f, rates)]
    ctor = None
    for f in factors:
        if txt(f[0]) in _VEC_CTORS and txt(f[0] + 1) == "(" and txt(f[1]) == ")":
            args, cur = [], []
            for jj in range(f[0] + 2, f[1]):
                if txt(jj) == ",":
                    args.append(cur)
                    cur = []
                else:
                    cur.append(jj)
            args.append(cur)
            simple = all(len(a) == 1 and toks[sig[a[0]]].kind in ("ident", "number") for a in args)
            if simple and len(args) == _VEC_CTORS[txt(f[0])] and \
                    any(toks[sig[a[0]]].text in rates for a in args):
                ctor = (f, args)
                break
    names = [txt(f[0]) for f in params]
    if (not names and not ctor) or len(names) + 1 > _MAX_PHASE_PARAMS:
        return False

    time_f = next(f for f in factors if single(f, times))

    def drop(f):
        i = factors.index(f)
        if i > 0:
            a = factors[i - 1][1] + 1         # the '*' before it
            G.blank(toks, sig[a], sig[f[1]])
        else:
            G.blank(toks, sig[f[0]], sig[factors[1][0] - 1])   # it and the '*' after it

    if ctor:
        f, args = ctor
        for a in args:
            t = toks[sig[a[0]]]
            if t.text in rates:
                t.text = ir.phase(names + [t.text])
            elif names:
                t.text = f"{t.text} * {ir.phase(names)}"
            else:
                t.text = f"{t.text} * {toks[sig[j]].text}"
        drop_list = params + [time_f]
    else:
        toks[sig[j]].text = ir.phase(names)
        drop_list = params
    # Drop right-to-left so earlier '*' positions stay valid.
    for f in sorted(drop_list, key=lambda f: -f[0]):
        drop(f)
        factors.remove(f)
    return True


# ── Zero-initialisation (WebGL/ANGLE semantics) ─────────────────────────────

_ZERO_TYPES = {t for t in G.TYPES if not t.startswith(("sampler", "isampler", "usampler", "void"))}


def _zero_init(toks):
    """Browsers (ANGLE) zero-initialise every variable, and plenty of Shadertoy
    code relies on it (`float a; a += ...`). Native drivers leave them
    undefined, so give uninitialised scalars/vectors/matrices an explicit 0."""
    for it in G.analyze(toks):
        if it.kind == "decl" and not set(it.qualifiers) & {"uniform", "in", "out", "varying",
                                                             "attribute", "const", "buffer", "shared"}:
            _zero_declarators(toks, it)
        elif it.kind == "func":
            for local in _all_local_decls(toks, it.body[0] + 1, it.body[1]):
                if not set(local.qualifiers) & {"const"}:
                    _zero_declarators(toks, local)


def _zero_declarators(toks, item):
    if item.type not in _ZERO_TYPES:
        return
    for d in item.decls:
        if d.init_span is None and d.array_span is None:
            # Only plain declarators: the token after the name must be ',' or ';'.
            nxt = G.next_sig(toks, d.name_idx)
            if nxt is not None and toks[nxt].text in (",", ";"):
                toks[d.name_idx].text = f"{d.name} = {item.type}(0)"


def _all_local_decls(toks, start, end):
    """Every declaration statement inside a function body, including
    `for (TYPE x; ...)` initialisers."""
    res = []
    i = start
    stmt_start = start
    while i < end:
        t = toks[i]
        if t.kind == "punct" and t.text in (";", "{", "}"):
            stmt_start = i + 1
        elif t.kind == "punct" and t.text == "(":
            prev = G.prev_sig(toks, i)
            if prev is not None and toks[prev].text == "for":
                stmt_start = i + 1          # for-init clause behaves like a statement
            else:
                i = G.match_close(toks, i)
        elif t.kind == "ident" and _is_stmt_start(toks, i, stmt_start) and \
                (t.text in _ZERO_TYPES or t.text in ("highp", "mediump", "lowp", "precise")):
            j = i
            depth = 0
            while j < end:
                tj = toks[j]
                if tj.kind == "punct":
                    if tj.text in ("(", "[", "{"):
                        depth += 1
                    elif tj.text in (")", "]", "}"):
                        depth -= 1
                        if depth < 0:
                            break
                    elif tj.text == ";" and depth == 0:
                        break
                j += 1
            item = G._classify(toks, i, j)
            if item.kind == "decl":
                res.append(item)
            i = j
            stmt_start = j + 1
            continue
        i += 1
    return res


# ── Global initializer hoisting & const relaxation ──────────────────────────

def _hoist_globals(toks, dynamic):
    """Globals whose initialisers aren't constant expressions are split:
    the declaration stays, the assignment moves into ffm_init()."""
    hoisted = []
    items = G.analyze(toks)
    global_consts = set()
    funcs = {it.name for it in items if it.kind in ("func", "proto")}
    for it in items:
        if it.kind != "decl" or any(q in it.qualifiers for q in ("uniform", "in", "out", "varying", "attribute")):
            continue
        is_const = "const" in it.qualifiers
        move = []
        for d in it.decls:
            if not d.init_span:
                continue
            ids = set(G.idents_in(toks, *d.init_span))
            unknown = {x for x in ids if x not in G.BUILTIN_FUNCS and x not in G.TYPES
                       and x not in global_consts and x not in ("true", "false")}
            # Struct constructors are fine; anything dynamic or a user function is not.
            if unknown & (dynamic | funcs) or (not is_const and unknown):
                move.append(d)
        if not move:
            if is_const:
                global_consts.update(d.name for d in it.decls)
            continue
        for d in it.decls:
            dynamic.add(d.name)
        prefix_end = it.decls[0].name_idx
        qual = [q for q in it.qualifiers if q not in ("const",)]
        type_txt = G.untokenize(toks[it.type_idx:prefix_end]).strip()
        parts = []
        for d in it.decls:
            arr = G.untokenize(toks[d.array_span[0]:d.array_span[1] + 1]) if d.array_span else ""
            if d in move:
                parts.append(d.name + arr)
                hoisted.append(f"{d.name} = {G.untokenize(toks[d.init_span[0]:d.init_span[1] + 1]).strip()};")
            else:
                parts.append(G.untokenize(toks[d.name_idx:d.init_span[1] + 1]) if d.init_span else d.name + arr)
        text = (" ".join(qual) + " " if qual else "") + type_txt + " " + ", ".join(parts) + ";"
        _replace_range(toks, it.start, it.end, text)
    return hoisted


def _strip_local_consts(toks, dynamic):
    """Drop `const` from local declarations initialised from dynamic values."""
    names = set(dynamic)
    changed = True
    while changed:
        changed = False
        for it in G.analyze(toks):
            if it.kind != "func":
                continue
            for local in _local_decls(toks, it.body[0] + 1, it.body[1]):
                if "const" not in local.qualifiers:
                    continue
                for d in local.decls:
                    if d.init_span and set(G.idents_in(toks, *d.init_span)) & names:
                        k = local.qual_idx["const"]
                        toks[k].text = ""
                        toks[k].kind = "ws"
                        names.update(x.name for x in local.decls)
                        changed = True
                        break


# ── Entry point / outputs ───────────────────────────────────────────────────

def _entry_point(toks, ir):
    items = G.analyze(toks)
    funcs = {it.name: it for it in items if it.kind == "func"}
    if "main" in funcs and ir.dialect != "shadertoy":
        # ISF/GLSL: main() is the entry; any mainImage() is just a helper it calls.
        toks[funcs["main"].name_idx].text = "ffm_main"
        return "main"
    if "mainImage" in funcs:
        entry = "mainImage"
        if "main" in funcs:
            toks[funcs["main"].name_idx].text = "ffm_unused_main"
    elif "main" in funcs:
        entry = "main"
        toks[funcs["main"].name_idx].text = "ffm_main"
    else:
        raise ConvertError("No main() or mainImage() function found.")
    if entry == "main" and ir.dialect == "shadertoy":
        ir.dialect = "glsl"
    return entry


def _rename_frag_outputs(toks):
    for t in toks:
        if t.kind == "preproc":
            t.text = re.sub(r"\bgl_FragColor\b", "ffm_FragColor", t.text)
            t.text = re.sub(r"\bgl_FragData\s*\[\s*0\s*\]", "ffm_FragColor", t.text)
    sig = G.significant(toks)
    for pos, k in enumerate(sig):
        t = toks[k]
        if t.kind != "ident":
            continue
        if t.text == "gl_FragColor":
            t.text = "ffm_FragColor"
        elif t.text == "gl_FragData" and pos + 3 < len(sig) and toks[sig[pos + 1]].text == "[" \
                and toks[sig[pos + 2]].text == "0" and toks[sig[pos + 3]].text == "]":
            t.text = "ffm_FragColor"
            for j in (1, 2, 3):
                toks[sig[pos + j]].text = ""
    # Fragment outputs declared by the user (`out vec4 fragColor;`) in main-style code.
    for it in G.analyze(toks):
        if it.kind == "decl" and "out" in it.qualifiers and it.type == "vec4" and len(it.decls) == 1:
            nm = it.decls[0].name
            _replace_range(toks, it.start, it.end, "")
            G.rename_idents(toks, {nm: "ffm_FragColor"})


# ── Plugin kind / labels ─────────────────────────────────────────────────────

def _decide_kind(ir, header):
    host = [i for i in ir.images if i.source == "host"]
    if ir.dialect == "shadertoy":
        # Every iChannel reads the host input; flag if more than iChannel0.
        if host:
            ir.kind = "effect"
            if len(host) > 1:
                ir.warnings.append(
                    f"{', '.join(i.name for i in host)} all receive the clip input "
                    f"(Shadertoy textures/buffers are not available).")
            for i in host:
                i.index = 0
        return
    cats = [c.lower() for c in (header or {}).get("CATEGORIES", [])] if header else []
    if len(host) >= 2 and ("transition" in cats or ir.param("progress")):
        ir.kind = "mixer"
        for i in host[2:]:
            i.source = "none"
            ir.warnings.append(f"Image input '{i.name}' has no source in a 2-input mixer; it will read black.")
        # Resolume drives a mixer's first parameter with the crossfader.
        prog = ir.param("progress")
        if prog:
            ir.params.remove(prog)
            ir.params.insert(0, prog)
    elif host:
        ir.kind = "effect"
        for i in host[1:]:
            i.source = "host"
            i.index = 0
            ir.warnings.append(f"Extra image input '{i.name}' receives the same clip input as '{host[0].name}'.")


def _dedupe_labels(ir):
    # If the shader has its own "speed" control, call ours something else.
    if any(p.kind != "speed" and p.display().lower() == "speed" for p in ir.params):
        for p in ir.params:
            if p.kind == "speed":
                p.label = "Time Scale"
    seen = {}
    for p in ir.params:
        lab = p.display()
        if lab.lower() in seen:
            seen[lab.lower()] += 1
            p.label = f"{lab} {seen[lab.lower()]}"
        else:
            seen[lab.lower()] = 1
            p.label = lab
