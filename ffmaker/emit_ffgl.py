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
}

HOST_BLOCK = """#version 410 core
// ── FFMaker host interface ──
uniform vec2  ffm_Resolution;
uniform float ffm_Time;
uniform float ffm_TimeDelta;
uniform int   ffm_Frame;
uniform vec4  ffm_Date;
uniform vec4  ffm_Mouse;
uniform int   ffm_PassIndex;
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
        if p.name:
            out.append(f"uniform {p.glsl_type} {p.name};\n")
    samplers = sampler_names(ir)
    for s in samplers:
        out.append(f"uniform sampler2D {s};\n")
    for name, sym in sorted(prog.aliases.items()):
        out.append(f"#define {name} {FFGL_SYMBOLS[sym]}\n")
    if ir.dialect == "isf":
        out.append(ISF_MACROS)
    out.append("#line 1\n")
    code = prog.code
    out.append(code)
    if not code.endswith("\n"):
        out.append("\n")
    out.append("// ── FFMaker entry ──\n")
    out.append("void ffm_init() {\n" + "".join(f"    {h}\n" for h in prog.hoisted) + "}\n")
    out.append("void main() {\n")
    out.append("    ffm_FragNorm = gl_FragCoord.xy / ffm_Resolution;\n")
    out.append("    ffm_SurfacePos = (ffm_FragNorm - 0.5) * vec2(ffm_Resolution.x / ffm_Resolution.y, 1.0);\n")
    for i in range(4):
        ch = f"iChannel{i}"
        res = f"vec3(vec2(textureSize({ch}, 0)), 1.0)" if ch in samplers else "vec3(ffm_Resolution, 1.0)"
        out.append(f"    ffm_ChannelRes[{i}] = {res}; ffm_ChannelTime[{i}] = ffm_Time;\n")
    out.append("    ffm_init();\n")
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
    lines = ["#pragma once", "// Generated by FFMaker. Do not edit.", "#include \"FFMakerPlugin.h\"", ""]
    ptype = {"source": "FF_SOURCE", "effect": "FF_EFFECT", "mixer": "FF_MIXER"}[ir.kind]
    ninputs = {"source": 0, "effect": 1, "mixer": 2}[ir.kind]
    lines += [
        f"#define FFM_PLUGIN_ID {_cstr(plugin_id(plugin_name))}",
        f"#define FFM_PLUGIN_NAME {_cstr(plugin_name[:16])}",
        f"#define FFM_PLUGIN_TYPE {ptype}",
        f"#define FFM_NUM_INPUTS {ninputs}",
        f"#define FFM_DESCRIPTION {_cstr((ir.meta.get('description') or plugin_name)[:200])}",
        f"#define FFM_ABOUT {_cstr(('Made with FFMaker. ' + (ir.meta.get('credit') or ''))[:200])}",
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
        opt_l, opt_v, nopt = "nullptr", "nullptr", 0
        d = [0.0, 0.0, 0.0, 0.0]
        mn = [0.0, 0.0]
        mx = [1.0, 1.0]
        comps = 1
        pixel = 0
        kind = {"float": "FFM_K_FLOAT", "int": "FFM_K_INT", "bool": "FFM_K_BOOL",
                "event": "FFM_K_EVENT", "long": "FFM_K_OPTION", "color": "FFM_K_COLOR",
                "point2D": "FFM_K_POINT", "speed": "FFM_K_SPEED", "mouse": "FFM_K_MOUSE",
                "mouseclick": "FFM_K_MOUSECLICK"}[p.kind]
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

    targets = []
    for p in ir.passes:
        if p.target and p.target not in [t.target for t in targets]:
            targets.append(p)
    lines.append("static const FFMTargetDef FFM_TARGETS[] = {")
    lines += [f"    {{ {_cstr(t.target)}, {int(t.persistent)}, {int(t.float)} }}," for t in targets] \
        or ['    { "", 0, 0 },']
    lines.append("};")
    lines.append(f"#define FFM_NUM_TARGETS {len(targets)}")
    tindex = {t.target: i for i, t in enumerate(targets)}

    samplers = []
    for im in ir.images:
        src = {"host": "FFM_SRC_HOST", "imported": "FFM_SRC_NONE", "none": "FFM_SRC_NONE"}[im.source]
        samplers.append(f"    {{ {_cstr(im.name)}, {src}, {im.index if im.source == 'host' else 0} }},")
    for t in targets:
        samplers.append(f"    {{ {_cstr(t.target)}, FFM_SRC_TARGET, {tindex[t.target]} }},")
    lines.append("static const FFMSamplerDef FFM_SAMPLERS[] = {")
    lines += samplers or ['    { "", FFM_SRC_NONE, 0 },']
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
