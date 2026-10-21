"""ShaderIR -> ISF 2 (.fs) for MadMapper, VDMX, Millumin and other ISF hosts."""
import json
import re

from . import glsl as G

ISF_SYMBOLS = {
    "time": "(TIME * ffmSpeed)", "timedelta": "TIMEDELTA", "frame": "FRAMEINDEX",
    "date": "DATE", "resolution2": "RENDERSIZE", "resolution3": "vec3(RENDERSIZE, 1.0)",
    "mouse_px": "ffm_Mouse", "mouse_norm2": "ffmMouse", "mouse_px2": "(ffmMouse * RENDERSIZE)",
    "passindex": "PASSINDEX", "fragnorm": "isf_FragNormCoord", "surfacepos": "ffm_SurfacePos",
    "surfacesize": "vec2(RENDERSIZE.x / RENDERSIZE.y, 1.0)", "samplerate": "44100.0",
    "framerate": "60.0", "channelres": "ffm_ChannelRes", "channeltime": "ffm_ChannelTime",
}


def emit(ir, source_code=None):
    """Return ISF file text. ISF sources are passed through unchanged."""
    if ir.dialect == "isf":
        if source_code is None:
            raise ValueError("ISF sources are passed through; supply source_code")
        return source_code
    prog = ir.programs[0]
    inputs = []
    defines = []
    has_speed = any(p.kind == "speed" for p in ir.params)

    # Image inputs: the first host image becomes ISF's conventional inputImage.
    # (ISF hosts expand IMG_* macros textually, so the names are renamed in
    # the code itself rather than aliased with #define.)
    host_imgs = [i for i in ir.images if i.source == "host"]
    image_renames = {}
    if host_imgs:
        inputs.append({"NAME": "inputImage", "TYPE": "image"})
        for im in host_imgs:
            if im.name != "inputImage":
                image_renames[im.name] = "inputImage"
    for im in ir.images:
        if im.source != "host":
            inputs.append({"NAME": im.name, "TYPE": "image", "LABEL": im.name})

    for p in ir.params:
        lab = p.display()
        if p.kind == "speed":
            inputs.append({"NAME": "ffmSpeed", "LABEL": "Speed", "TYPE": "float",
                           "DEFAULT": p.default, "MIN": p.min, "MAX": p.max})
        elif p.kind == "mouse":
            inputs.append({"NAME": "ffmMouse", "LABEL": "Mouse", "TYPE": "point2D",
                           "DEFAULT": list(p.default), "MIN": [0.0, 0.0], "MAX": [1.0, 1.0]})
        elif p.kind == "mouseclick":
            inputs.append({"NAME": "ffmMouseClick", "LABEL": "Mouse Click", "TYPE": "bool",
                           "DEFAULT": bool(p.default)})
        elif p.kind == "float":
            inputs.append({"NAME": p.name, "LABEL": lab, "TYPE": "float",
                           "DEFAULT": p.default, "MIN": p.min, "MAX": p.max})
        elif p.kind == "int":
            lo, hi = int(p.min), int(p.max)
            vals = list(range(lo, hi + 1))[:64]
            inputs.append({"NAME": p.name, "LABEL": lab, "TYPE": "long", "DEFAULT": int(p.default),
                           "VALUES": vals, "LABELS": [str(v) for v in vals]})
        elif p.kind in ("bool", "event"):
            inputs.append({"NAME": p.name, "LABEL": lab, "TYPE": p.kind, "DEFAULT": bool(p.default)}
                          if p.kind == "bool" else {"NAME": p.name, "LABEL": lab, "TYPE": "event"})
        elif p.kind == "long":
            inputs.append({"NAME": p.name, "LABEL": lab, "TYPE": "long", "DEFAULT": p.default,
                           "VALUES": p.values, "LABELS": p.labels})
        elif p.kind == "color":
            d = (list(p.default) + [1.0] * 4)[:4]
            if p.glsl_type == "vec3":
                inputs.append({"NAME": p.name + "_rgba", "LABEL": lab, "TYPE": "color", "DEFAULT": d})
                defines.append(f"#define {p.name} ({p.name}_rgba.rgb)")
            else:
                inputs.append({"NAME": p.name, "LABEL": lab, "TYPE": "color", "DEFAULT": d})
        elif p.kind == "point2D":
            inputs.append({"NAME": p.name, "LABEL": lab, "TYPE": "point2D",
                           "DEFAULT": list(p.default), "MIN": list(p.min), "MAX": list(p.max)})

    cats = ["Filter"] if ir.kind == "effect" else ["Generator"]
    header = {
        "ISFVSN": "2",
        "DESCRIPTION": ir.meta.get("description") or ir.name,
        "CREDIT": ir.meta.get("credit") or "Converted with FFMaker",
        "CATEGORIES": cats,
        "INPUTS": inputs,
    }

    for name, sym in sorted(prog.aliases.items()):
        expr = ISF_SYMBOLS[sym]
        if sym == "time" and not has_speed:
            expr = "TIME"
        defines.append(f"#define {name} {expr}")
    defines.append("#define ffm_FragColor gl_FragColor")

    toks = G.tokenize(prog.code)
    G.rename_idents(toks, image_renames)
    image_names = {image_renames.get(i.name, i.name) for i in ir.images}
    code = _portable_textures(G.untokenize(toks), image_names)
    used = set(prog.aliases.values())
    globals_ = []
    setup = []
    if "mouse_px" in used:
        globals_.append("vec4 ffm_Mouse;")
        setup.append("ffm_Mouse = vec4(ffmMouse * RENDERSIZE, (ffmMouseClick ? 1.0 : -1.0) * ffmMouse * RENDERSIZE);")
    if "surfacepos" in used:
        globals_.append("vec2 ffm_SurfacePos;")
        setup.append("ffm_SurfacePos = (isf_FragNormCoord - 0.5) * vec2(RENDERSIZE.x / RENDERSIZE.y, 1.0);")
    if "channelres" in used:
        globals_.append("vec3 ffm_ChannelRes[4];")
        for i in range(4):
            setup.append(f"ffm_ChannelRes[{i}] = vec3(" + ("IMG_SIZE(inputImage)" if host_imgs else "RENDERSIZE") + ", 1.0);")
    if "channeltime" in used:
        globals_.append("float ffm_ChannelTime[4];")
        for i in range(4):
            setup.append(f"ffm_ChannelTime[{i}] = TIME;")

    out = ["/*" + json.dumps(header, indent=4) + "*/", ""]
    out += ["// ── FFMaker compatibility layer ──"] + defines + globals_ + [""]
    out.append(code.rstrip("\n"))
    out.append("")
    out.append("// ── FFMaker entry ──")
    out.append("void ffm_init() {")
    for h in prog.hoisted:
        ht = G.tokenize(h)
        G.rename_idents(ht, image_renames)
        out.append("    " + G.untokenize(ht))
    out.append("}")
    out.append("void main() {")
    out += [f"    {s}" for s in setup]
    out.append("    ffm_init();")
    if prog.entry == "mainImage":
        out.append("    vec4 ffm_c = vec4(0.0, 0.0, 0.0, 1.0);")
        out.append("    mainImage(ffm_c, gl_FragCoord.xy);")
        out.append("    gl_FragColor = ffm_c;")
    else:
        out.append("    gl_FragColor = vec4(0.0, 0.0, 0.0, 1.0);")
        out.append("    ffm_main();")
    if prog.force_opaque:
        out.append("    gl_FragColor.a = 1.0;")
    out.append("}")
    return "\n".join(out) + "\n"


def _portable_textures(code, image_names):
    """texture(img, uv) -> IMG_NORM_PIXEL(img, uv) for ISF image inputs so the
    file works in hosts that compile ISF with old GLSL versions."""
    toks = G.tokenize(code)
    sig = G.significant(toks)
    for pos, k in enumerate(sig[:-2]):
        t = toks[k]
        if t.kind == "ident" and t.text == "texture" and toks[sig[pos + 1]].text == "(":
            arg = toks[sig[pos + 2]]
            if arg.kind == "ident" and arg.text in image_names:
                close = G.match_close(toks, sig[pos + 1])
                commas = _top_level_commas(toks, sig[pos + 1], close)
                if len(commas) == 1:          # no bias argument
                    t.text = "IMG_NORM_PIXEL"
    return G.untokenize(toks)


def _top_level_commas(toks, open_i, close_i):
    depth = 0
    out = []
    for k in range(open_i + 1, close_i):
        tx = toks[k].text
        if toks[k].kind == "punct":
            if tx in ("(", "[", "{"):
                depth += 1
            elif tx in (")", "]", "}"):
                depth -= 1
            elif tx == "," and depth == 0:
                out.append(k)
    return out
