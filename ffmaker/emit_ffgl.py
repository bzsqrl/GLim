"""ShaderIR -> FFGL: final GLSL per program + the generated ShaderData.h."""
import colorsys
import hashlib
import re

FFGL_SYMBOLS = {
    "time": "ffm_Time", "timedelta": "ffm_TimeDelta", "frame": "ffm_Frame",
    "date": "ffm_Date", "resolution2": "ffm_Resolution",
    "resolution3": "vec3(ffm_Resolution, 1.0)", "mouse_px": "ffm_Mouse",
    "mouse_norm2": "(ffm_Mouse.xy / ffm_Resolution)", "mouse_px2": "ffm_Mouse.xy",
    "passindex": "ffm_PassIndex", "fragnorm": "ffm_FragNorm",
    "surfacepos": "ffm_SurfacePos",
    "surfacesize": "vec2(ffm_Resolution.x / ffm_Resolution.y, 1.0)",
    "samplerate": "44100.0", "framerate": "60.0",
    "channelres": "ffm_ChannelRes", "channeltime": "ffm_ChannelTime",
    "bpm": "ffm_BPM", "beat": "ffm_Beat", "barphase": "ffm_BarPhase",
}

HOST_BLOCK = """#version 410 core
// ── FFStudio host interface ──
uniform vec2  ffm_Resolution;
uniform float ffm_Time;
uniform float ffm_TimeDelta;
uniform int   ffm_Frame;
uniform vec4  ffm_Date;
uniform vec4  ffm_Mouse;
uniform int   ffm_PassIndex;
uniform float ffm_BPM;       // host tempo (FFGL SetBeatInfo), 120 when the host sends none
uniform float ffm_Beat;      // beats elapsed, in step with the host's bars
uniform float ffm_BarPhase;  // 0..1 through the current bar
out vec4 ffm_FragColor;
vec2  ffm_FragNorm;
vec2  ffm_SurfacePos;
vec3  ffm_ChannelRes[4];
float ffm_ChannelTime[4];
"""

ISF_MACROS = """#define IMG_SIZE(img) vec2(textureSize(img, 0))
#define IMG_NORM_PIXEL(img, c) texture(img, c)
#define IMG_PIXEL(img, c) texture(img, (c) / vec2(textureSize(img, 0)))
#define IMG_THIS_PIXEL(img) texture(img, ffm_FragNorm)
#define IMG_THIS_NORM_PIXEL(img) texture(img, ffm_FragNorm)
#define IMG_NORM_PIXEL_LOD(img, c, l) textureLod(img, c, l)
#define IMG_PIXEL_LOD(img, c, l) textureLod(img, (c) / vec2(textureSize(img, 0)), l)
"""


def program_glsl(ir, prog):
    """Full fragment shader text for one program. User code starts at line 1
    (via #line) so compiler errors point at the user's own line numbers."""
    out = [HOST_BLOCK]
    for p in ir.params:
        if p.name and p.hidden:
            out.append(f"const {p.glsl_type} {p.name} = {glsl_literal(p)};\n")
        elif p.name:
            out.append(f"uniform {p.glsl_type} {p.name};\n")
    for ph in ir.phases:
        out.append(f"uniform float {ph.name};  // running total of time * {' * '.join(ph.params)}\n")
    samplers = sampler_names(ir)
    for s in samplers:
        out.append(f"uniform sampler2D {s};\n")
    for name, sym in sorted(prog.aliases.items()):
        out.append(f"#define {name} {FFGL_SYMBOLS[sym]}\n")
    if ir.dialect == "isf":
        out.append(ISF_MACROS)
    if prog.prelude:
        out.append(prog.prelude.rstrip("\n") + "\n")
    out.append("#line 1\n")
    code = prog.code
    out.append(code)
    if not code.endswith("\n"):
        out.append("\n")
    out.append("// ── FFStudio entry ──\n")
    out.append("void ffm_init() {\n" + "".join(f"    {h}\n" for h in prog.hoisted) + "}\n")
    out.append("void main() {\n")
    out.append("    ffm_FragNorm = gl_FragCoord.xy / ffm_Resolution;\n")
    out.append("    ffm_SurfacePos = (ffm_FragNorm - 0.5) * vec2(ffm_Resolution.x / ffm_Resolution.y, 1.0);\n")
    for i in range(4):
        ch = prog.channels[i] if prog.channels else f"iChannel{i}"
        res = f"vec3(vec2(textureSize({ch}, 0)), 1.0)" if ch and ch in samplers else "vec3(ffm_Resolution, 1.0)"
        out.append(f"    ffm_ChannelRes[{i}] = {res}; ffm_ChannelTime[{i}] = ffm_Time;\n")
    out.append("    ffm_init();\n")
    if prog.prelude:
        out.append("    ffm_vs_main();\n")
    if prog.entry == "mainImage":
        out.append("    vec4 ffm_c = vec4(0.0, 0.0, 0.0, 1.0);\n")
        out.append("    mainImage(ffm_c, gl_FragCoord.xy);\n")
        out.append("    ffm_FragColor = ffm_c;\n")
    else:
        out.append("    ffm_FragColor = vec4(0.0, 0.0, 0.0, 1.0);\n")
        out.append("    ffm_main();\n")
    if prog.force_opaque:
        out.append("    ffm_FragColor.a = 1.0;\n")
    out.append("}\n")
    return "".join(out)


def glsl_literal(p):
    """GLSL constant for a param's current default."""
    def f(x):
        r = repr(float(x))
        return r if ("." in r or "e" in r) else r + ".0"
    v = p.default
    if p.glsl_type == "bool":
        return "true" if v else "false"
    if p.glsl_type == "int":
        return str(int(v))
    if p.glsl_type in ("vec2", "vec3", "vec4"):
        n = int(p.glsl_type[-1])
        vals = (list(v) + [1.0] * 4)[:n]
        if p.pixel_space:
            vals = [vals[0], vals[1]]
        return f"{p.glsl_type}(" + ", ".join(f(x) for x in vals) + ")"
    return f(v)


_FILTERS = {"nearest": 0, "linear": 1, "mipmap": 2}


def _sampler_state(im):
    """'filter, wrap' for a host/target sampler: -1, -1 keeps the texture's own
    (linear, clamp). Host textures have no mipmaps, so mipmap means linear there."""
    if im.source not in ("host", "target") or not (im.filter or im.wrap):
        return "-1, -1"
    f = _FILTERS[im.filter or "linear"]
    if im.source == "host" and f == 2:
        f = 1
    return f"{f}, {int(im.wrap == 'repeat')}"


def sampler_names(ir):
    names = [i.name for i in ir.images]
    for p in ir.passes:
        if p.target and p.target not in names:
            names.append(p.target)
    return names


def plugin_id(name):
    h = hashlib.sha1(name.encode("utf-8")).digest()
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return alphabet[h[0] % 26] + "".join(alphabet[b % 36] for b in h[1:4])


def _cfloat(x):
    r = repr(float(x))
    if "e" not in r and "." not in r:
        r += ".0"
    return r + "f"


def _cstr(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ") + '"'


def _chunks(text, size=8000):
    """Split text into raw-string-safe chunks (MSVC caps literals at ~16 KB)."""
    chunks, cur = [], []
    n = 0
    for line in text.splitlines(keepends=True):
        while len(line) > size:
            chunks.append("".join(cur) + line[:size]) if cur else chunks.append(line[:size])
            cur, n, line = [], 0, line[size:]
        if n + len(line) > size and cur:
            chunks.append("".join(cur))
            cur, n = [], 0
        cur.append(line)
        n += len(line)
    if cur:
        chunks.append("".join(cur))
    return chunks


def _size_expr(expr, fallback):
    """Translate an ISF pass size expression ($WIDTH/2.0) to C++."""
    if expr is None or str(expr).strip() == "":
        return fallback
    e = str(expr)
    funcs = {"floor", "ceil", "max", "min", "pow", "sqrt", "abs", "round"}

    def ident(m):
        word = m.group(0)
        if word in funcs:
            return f"std::{word}"
        return None

    e = re.sub(r"\$WIDTH\b", "W", e)
    e = re.sub(r"\$HEIGHT\b", "H", e)
    e = re.sub(r"\$([A-Za-z_]\w*)", lambda m: f'p.P("{m.group(1)}")', e)
    out = []
    for tok in re.split(r"(\b[A-Za-z_]\w*\b|\"[^\"]*\")", e):
        if re.fullmatch(r"[A-Za-z_]\w*", tok or ""):
            if tok in ("W", "H", "p", "P", "std"):
                out.append(tok)
            elif tok in funcs:
                out.append("std::" + tok)
            else:
                return fallback
        else:
            out.append(tok)
    e = "".join(out).replace("std::std::", "std::")
    e = re.sub(r"(\d+\.\d*|\.\d+)(?![\d.fF])", r"\1f", e)
    return f"(float)({e})"


def shader_data_header(ir, programs_glsl, plugin_name):
    lines = ["#pragma once", "// Generated by FFStudio. Do not edit.", "#include \"FFMakerPlugin.h\"", ""]
    ptype = {"source": "FF_SOURCE", "effect": "FF_EFFECT", "mixer": "FF_MIXER"}[ir.kind]
    ninputs = {"source": 0, "effect": 1, "mixer": 2}[ir.kind]
    lines += [
        f"#define FFM_PLUGIN_ID {_cstr(plugin_id(plugin_name))}",
        f"#define FFM_PLUGIN_NAME {_cstr(plugin_name[:16])}",
        f"#define FFM_PLUGIN_TYPE {ptype}",
        f"#define FFM_NUM_INPUTS {ninputs}",
        f"#define FFM_DESCRIPTION {_cstr((ir.meta.get('description') or plugin_name)[:200])}",
        f"#define FFM_ABOUT {_cstr(('Made with FFStudio. ' + (ir.meta.get('credit') or ''))[:200])}",
        "",
    ]
    for i, src in enumerate(programs_glsl):
        lines.append(f"static const char* const FFM_PROGRAM_{i}[] = {{")
        for ch in _chunks(src):
            lines.append(f'R"FFM({ch})FFM",')
        lines.append("nullptr };")
    lines.append("static const char* const* const FFM_PROGRAMS[] = { "
                 + ", ".join(f"FFM_PROGRAM_{i}" for i in range(len(programs_glsl))) + " };")
    lines.append(f"static const int FFM_NUM_PROGRAMS = {len(programs_glsl)};")
    lines.append("")

    defs = []
    for idx, p in enumerate(ir.params):
        if p.hidden:
            continue
        opt_l, opt_v, nopt = "nullptr", "nullptr", 0
        d = [0.0, 0.0, 0.0, 0.0]
        mn = [0.0, 0.0]
        mx = [1.0, 1.0]
        comps = 1
        pixel = 0
        kind = {"float": "FFM_K_FLOAT", "int": "FFM_K_INT", "bool": "FFM_K_BOOL",
                "event": "FFM_K_EVENT", "long": "FFM_K_OPTION", "color": "FFM_K_COLOR",
                "point2D": "FFM_K_POINT", "speed": "FFM_K_SPEED", "mouse": "FFM_K_MOUSE",
                "mouseclick": "FFM_K_MOUSECLICK", "fft": "FFM_K_FFT"}[p.kind]
        if p.kind in ("float", "int", "speed"):
            d[0] = float(p.default)
            mn[0], mx[0] = float(p.min), float(p.max)
        elif p.kind in ("bool", "mouseclick"):
            d[0] = 1.0 if p.default else 0.0
        elif p.kind == "long":
            nopt = len(p.values)
            lines.append(f"static const char* const FFM_OPT_LABELS_{idx}[] = {{ "
                         + ", ".join(_cstr(l) for l in p.labels) + " };")
            lines.append(f"static const float FFM_OPT_VALUES_{idx}[] = {{ "
                         + ", ".join(_cfloat(v) for v in p.values) + " };")
            opt_l, opt_v = f"FFM_OPT_LABELS_{idx}", f"FFM_OPT_VALUES_{idx}"
            d[0] = float(p.values.index(p.default)) if p.default in p.values else 0.0
        elif p.kind == "color":
            rgba = (list(p.default) + [1.0] * 4)[:4]
            h, s, v = colorsys.rgb_to_hsv(*[min(max(c, 0.0), 1.0) for c in rgba[:3]])
            d = [h, s, v, rgba[3]]
            comps = 3 if p.glsl_type == "vec3" else 4
        elif p.kind in ("point2D", "mouse"):
            mn, mx = [float(x) for x in p.min], [float(x) for x in p.max]
            d = [float(p.default[0]), float(p.default[1]), 0.0, 0.0]
            if p.pixel_space:
                pixel = 1
                d[0] = min(max(d[0] / 1920.0, 0.0), 1.0)
                d[1] = min(max(d[1] / 1080.0, 0.0), 1.0)
            comps = 2
        f = lambda xs: "{ " + ", ".join(_cfloat(x) for x in xs) + " }"
        defs.append(f"    {{ {_cstr(p.name)}, {_cstr(p.display())}, {kind}, {f(d)}, {f(mn)}, {f(mx)}, "
                    f"{comps}, {pixel}, {opt_l}, {opt_v}, {nopt} }},")
    lines.append("static const FFMParamDef FFM_PARAMS[] = {")
    lines += defs or ['    { "", "", FFM_K_FLOAT, { 0 }, { 0 }, { 1 }, 1, 0, nullptr, nullptr, 0 },']
    lines.append("};")
    lines.append(f"static const int FFM_NUM_PARAMS = {len(defs)};")
    lines.append("")

    # Phases: running totals of time * sliders. Hidden params are constants,
    # folded into the scale.
    def_index = {}
    for p in ir.params:
        if not p.hidden:
            def_index[p.name or p.kind] = len(def_index)
    phase_defs = []
    for ph in ir.phases:
        scale, idx = 1.0, []
        for nm in ph.params:
            p = ir.param(nm)
            if p is None or p.hidden:
                scale *= float(p.default) if p else 0.0
            else:
                idx.append(def_index[nm])
        idx += [0] * (4 - len(idx))
        n = sum(1 for nm in ph.params if ir.param(nm) and not ir.param(nm).hidden)
        phase_defs.append(f"    {{ {_cstr(ph.name)}, {_cfloat(scale)}, {n}, {{ {', '.join(map(str, idx))} }} }},")
    lines.append("static const FFMPhaseDef FFM_PHASES[] = {")
    lines += phase_defs or ['    { "", 0.0f, 0, { 0, 0, 0, 0 } },']
    lines.append("};")
    lines.append(f"static const int FFM_NUM_PHASES = {len(phase_defs)};")
    lines.append("")

    targets = []
    for p in ir.passes:
        if p.target and p.target not in [t.target for t in targets]:
            targets.append(p)
    # Buffers read with a mipmap filter get mipmaps rebuilt after they render.
    mip = {i.target for i in ir.images if i.source == "target" and i.filter == "mipmap"}
    lines.append("static const FFMTargetDef FFM_TARGETS[] = {")
    lines += [f"    {{ {_cstr(t.target)}, {int(t.persistent)}, {int(t.float)}, {int(t.target in mip)} }},"
              for t in targets] or ['    { "", 0, 0, 0 },']
    lines.append("};")
    lines.append(f"#define FFM_NUM_TARGETS {len(targets)}")
    tindex = {t.target: i for i, t in enumerate(targets)}

    from . import images as IMG
    imported = [im for im in ir.images if im.source == "imported"]
    img_defs = []
    for k, im in enumerate(imported):
        data = IMG.encoded_bytes(im)
        state = f"{im.noise_size}, {int(im.repeat)}, {_FILTERS[im.filter or 'mipmap']}, {int(im.flip)}"
        if data:
            lines.append(f"static const unsigned char FFM_IMG_{k}[] = {{")
            for off in range(0, len(data), 48):
                lines.append(",".join(str(b) for b in data[off:off + 48]) + ",")
            lines.append("};")
            img_defs.append(f"    {{ {_cstr(im.name)}, FFM_IMG_{k}, {len(data)}u, {state} }},")
        else:
            img_defs.append(f"    {{ {_cstr(im.name)}, nullptr, 0u, {state} }},")
    lines.append("static const FFMImageDef FFM_IMAGES[] = {")
    lines += img_defs or ['    { "", nullptr, 0u, 0, 0, 2, 1 },']
    lines.append("};")
    lines.append(f"static const int FFM_NUM_IMAGES = {len(img_defs)};")

    samplers = []
    for im in ir.images:
        if im.source == "audio":
            samplers.append(f"    {{ {_cstr(im.name)}, FFM_SRC_AUDIO, {im.rows}, -1, -1 }},")
            continue
        if im.source == "imported":
            samplers.append(f"    {{ {_cstr(im.name)}, FFM_SRC_IMAGE, {imported.index(im)}, -1, -1 }},")
            continue
        if im.source == "target":
            samplers.append(f"    {{ {_cstr(im.name)}, FFM_SRC_TARGET, {tindex[im.target]}, {_sampler_state(im)} }},")
            continue
        src = {"host": "FFM_SRC_HOST", "none": "FFM_SRC_NONE"}[im.source]
        samplers.append(f"    {{ {_cstr(im.name)}, {src}, {im.index if im.source == 'host' else 0}, "
                        f"{_sampler_state(im)} }},")
    for t in targets:
        samplers.append(f"    {{ {_cstr(t.target)}, FFM_SRC_TARGET, {tindex[t.target]}, -1, -1 }},")
    lines.append("static const FFMSamplerDef FFM_SAMPLERS[] = {")
    lines += samplers or ['    { "", FFM_SRC_NONE, 0, -1, -1 },']
    lines.append("};")
    lines.append(f"static const int FFM_NUM_SAMPLERS = {len(samplers)};")

    lines.append("static const FFMPassDef FFM_PASSES[] = {")
    for p in ir.passes:
        lines.append(f"    {{ {p.program}, {tindex[p.target] if p.target else -1} }},")
    lines.append("};")
    lines.append(f"static const int FFM_NUM_PASSES = {len(ir.passes)};")
    lines.append("")
    lines.append("static void FFM_PassSize( int pass, float W, float H, const FFMakerPlugin& p, float& w, float& h )")
    lines.append("{")
    lines.append("    (void)p; w = W; h = H;")
    lines.append("    switch( pass )")
    lines.append("    {")
    for i, p in enumerate(ir.passes):
        if p.target and (p.width or p.height):
            lines.append(f"    case {i}: w = {_size_expr(p.width, 'W')}; h = {_size_expr(p.height, 'H')}; break;")
    lines.append("    default: break;")
    lines.append("    }")
    lines.append("}")
    return "\n".join(lines) + "\n"
