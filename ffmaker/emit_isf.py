"""ShaderIR -> ISF 2 (.fs) for MadMapper, VDMX, Millumin and other ISF hosts."""
import json
import os
import re
import shutil

from . import glsl as G

ISF_SYMBOLS = {
    "time": "(TIME * ffmSpeed)", "timedelta": "TIMEDELTA", "frame": "FRAMEINDEX",
    "date": "DATE", "resolution2": "RENDERSIZE", "resolution3": "vec3(RENDERSIZE, 1.0)",
    "mouse_px": "ffm_Mouse", "mouse_norm2": "ffmMouse", "mouse_px2": "(ffmMouse * RENDERSIZE)",
    "passindex": "PASSINDEX", "fragnorm": "isf_FragNormCoord", "surfacepos": "ffm_SurfacePos",
    "surfacesize": "vec2(RENDERSIZE.x / RENDERSIZE.y, 1.0)", "samplerate": "44100.0",
    "framerate": "60.0", "channelres": "ffm_ChannelRes", "channeltime": "ffm_ChannelTime",
}


ISF_RESERVED = {"TIME", "TIMEDELTA", "RENDERSIZE", "PASSINDEX", "FRAMEINDEX", "DATE",
                "isf_FragNormCoord", "vv_FragNormCoord", "inputImage"}


def asset_name(ir, im):
    """File name for an embedded image written next to the .fs."""
    ext = os.path.splitext(im.path)[1].lower() if im.path and os.path.isfile(im.path) else ".png"
    return f"{ir.name}_{im.name}{ext}"


def write(ir, out_dir, source_code=None):
    """Write <name>.fs plus any texture files it imports. Returns the .fs path."""
    from . import images as IMG
    os.makedirs(out_dir, exist_ok=True)
    fs_path = os.path.join(out_dir, ir.name + ".fs")
    with open(fs_path, "w", encoding="utf-8") as f:
        f.write(emit(ir, source_code))
    if ir.dialect != "isf":
        for k, im in enumerate([i for i in ir.images if i.source == "imported"]):
            dst = os.path.join(out_dir, asset_name(ir, im))
            if IMG.available(im):
                shutil.copy2(im.path, dst)
            else:
                from PIL import Image as PILImage
                w, h, px = IMG.noise_rgba(k, im.noise_size)
                PILImage.frombytes("RGBA", (w, h), px).save(dst)
    return fs_path


def emit(ir, source_code=None):
    """Return ISF file text. ISF sources are passed through unchanged."""
    if ir.dialect == "isf":
        if source_code is None:
            raise ValueError("ISF sources are passed through; supply source_code")
        return source_code
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
    imported = {}
    for im in ir.images:
        if im.source == "audio":
            inputs.append({"NAME": im.name, "TYPE": im.isf_type or "audioFFT", "LABEL": "Audio"})
        elif im.source == "imported":
            imported[im.name] = {"PATH": asset_name(ir, im)}
        elif im.source != "host":
            inputs.append({"NAME": im.name, "TYPE": "image", "LABEL": im.name})

    for p in ir.params:
        lab = p.display()
        if p.kind == "speed":
            inputs.append({"NAME": "ffmSpeed", "LABEL": "Speed", "TYPE": "float",
                           "DEFAULT": p.default, "MIN": p.min, "MAX": p.max})
        elif p.kind == "mouse":
            inputs.append({"NAME": "ffmMouse", "LABEL": "Mouse", "TYPE": "point2D",
                           "DEFAULT": list(p.default), "MIN": [0.0, 0.0], "MAX": [1.0, 1.0]})
        elif p.kind == "fft":
            pass                      # ISF hosts supply audio through the audio input itself
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
    if imported:
        header["IMPORTED"] = imported

    aliases = {}
    for pr in ir.programs:
        aliases.update(pr.aliases)
    for name, sym in sorted(aliases.items()):
        expr = ISF_SYMBOLS[sym]
        if sym == "time" and not has_speed:
            expr = "TIME"
        defines.append(f"#define {name} {expr}")

    targets = [ps.target for ps in ir.passes if ps.target]
    if targets:
        header["PASSES"] = [{"TARGET": ps.target, "PERSISTENT": bool(ps.persistent), "FLOAT": bool(ps.float)}
                            if ps.target else {} for ps in ir.passes]

    # One ISF shader runs every pass, so each pass's own functions/globals get a
    # unique suffix; shared (Common) code appears once.
    body, entries = _merge_programs(ir.programs)
    image_names = {image_renames.get(i.name, i.name) for i in ir.images} | set(targets)
    repeat_names = {image_renames.get(i.name, i.name) for i in ir.images
                    if i.source == "imported" and i.repeat}
    toks = G.tokenize(body)
    # User code must not redefine names the ISF host provides.
    clash = {n: "user_" + n for n in G.declared_names(toks) if n in ISF_RESERVED or n.startswith("IMG_")}
    G.rename_everywhere(toks, clash)
    G.rename_idents(toks, {**image_renames, "ffm_FragColor": "gl_FragColor"})
    code = _portable_textures(G.untokenize(toks), image_names, repeat_names)

    used = set(aliases.values())
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
    if "channeltime" in used:
        globals_.append("float ffm_ChannelTime[4];")
        for i in range(4):
            setup.append(f"ffm_ChannelTime[{i}] = TIME;")

    def channel_res(prog):
        lines = []
        for i in range(4):
            ch = prog.channels[i] if prog.channels else ("inputImage" if host_imgs else None)
            ch = image_renames.get(ch, ch)
            lines.append(f"ffm_ChannelRes[{i}] = vec3(" + (f"IMG_SIZE({ch})" if ch else "RENDERSIZE") + ", 1.0);")
        return lines

    hoisted = []
    for k, pr in enumerate(ir.programs):
        for h in pr.hoisted:
            ht = G.tokenize(h)
            G.rename_idents(ht, {**entries[k]["renames"], **image_renames})
            line = G.untokenize(ht)
            if line not in hoisted:
                hoisted.append(line)

    out = ["/*" + json.dumps(header, indent=4) + "*/", ""]
    out += ["// ── FFMaker compatibility layer ──"] + defines + globals_ + [""]
    out.append(code.rstrip("\n"))
    out.append("")
    out.append("// ── FFMaker entry ──")
    out.append("void ffm_init() {")
    out += [f"    {h}" for h in hoisted]
    out.append("}")
    out.append("void main() {")
    out += [f"    {x}" for x in setup]
    out.append("    ffm_init();")
    multi = len(ir.passes) > 1
    for i, ps in enumerate(ir.passes):
        prog = ir.programs[ps.program]
        ind = "        " if multi else "    "
        if multi:
            out.append(f"    {'if' if i == 0 else 'else if'} (PASSINDEX == {i}) {{")
        if "channelres" in used:
            out += [ind + x for x in channel_res(prog)]
        entry = entries[ps.program]["entry"]
        if prog.entry == "mainImage":
            out.append(f"{ind}vec4 ffm_c = vec4(0.0, 0.0, 0.0, 1.0);")
            out.append(f"{ind}{entry}(ffm_c, gl_FragCoord.xy);")
            out.append(f"{ind}gl_FragColor = ffm_c;")
        else:
            out.append(f"{ind}gl_FragColor = vec4(0.0, 0.0, 0.0, 1.0);")
            out.append(f"{ind}{entry}();")
        if prog.force_opaque:
            out.append(f"{ind}gl_FragColor.a = 1.0;")
        if multi:
            out.append("    }")
    out.append("}")
    return "\n".join(out) + "\n"


def _merge_programs(programs):
    """Combine programs into one source. Returns (code, [{entry, renames}])."""
    if len(programs) == 1:
        pr = programs[0]
        return pr.code, [{"entry": "mainImage" if pr.entry == "mainImage" else "ffm_main", "renames": {}}]
    offset = programs[0].line_offset
    common = "\n".join(programs[0].code.split("\n")[:offset])
    parts = [common]
    entries = []
    for k, pr in enumerate(programs):
        part = "\n".join(pr.code.split("\n")[offset:])
        toks = G.tokenize(part)
        renames = {}
        for it in G.analyze(toks):
            if it.kind in ("func", "proto"):
                renames[it.name] = f"{it.name}_p{k}"
            elif it.kind == "decl":
                for d in it.decls:
                    renames[d.name] = f"{d.name}_p{k}"
        G.rename_idents(toks, renames)
        parts.append(f"// ── {pr.label or 'pass ' + str(k)} ──\n" + G.untokenize(toks))
        entry = "mainImage" if pr.entry == "mainImage" else "ffm_main"
        entries.append({"entry": renames.get(entry, entry), "renames": renames})
    return "\n".join(parts), entries


def _portable_textures(code, image_names, repeat_names=()):
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
                    if arg.text in repeat_names:  # ISF hosts clamp; emulate GL_REPEAT
                        toks[commas[0]].text = ", fract("
                        toks[close].text = "))"
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
