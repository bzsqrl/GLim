"""Emulates how ISF hosts (VVISF: MadMapper, VDMX...) prepare an ISF fragment
shader, so exported .fs files can be compile-checked offline.

Like VVISF, IMG_* macros are expanded textually by image name before the GLSL
compiler sees the code, and gl_FragColor is rewritten for GL3+ contexts.
"""
import json
import re

from . import convert as C
from . import validate as V


def _expand_img_macros(code, images):
    out = []
    i = 0
    pat = re.compile(r"\b(IMG_NORM_PIXEL|IMG_PIXEL|IMG_THIS_PIXEL|IMG_THIS_NORM_PIXEL|IMG_SIZE)\s*\(")
    while True:
        m = pat.search(code, i)
        if not m:
            out.append(code[i:])
            break
        out.append(code[i:m.start()])
        # find matching paren
        depth, k = 1, m.end()
        while k < len(code) and depth:
            if code[k] == "(":
                depth += 1
            elif code[k] == ")":
                depth -= 1
            k += 1
        args = _split_args(code[m.end():k - 1])
        name = args[0].strip() if args else ""
        if name not in images:
            raise ValueError(f"{m.group(1)} used with '{name}', which is not an image input")
        mac = m.group(1)
        if mac == "IMG_SIZE":
            out.append(f"_{name}_imgSize")
        elif mac in ("IMG_THIS_PIXEL", "IMG_THIS_NORM_PIXEL"):
            out.append(f"texture({name}, isf_FragNormCoord)")
        elif mac == "IMG_NORM_PIXEL":
            out.append(f"texture({name}, {_expand_img_macros(args[1], images)})")
        else:
            out.append(f"texture({name}, ({_expand_img_macros(args[1], images)}) / _{name}_imgSize)")
        i = k
    return "".join(out)


def _split_args(s):
    args, depth, cur = [], 0, []
    for ch in s:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        if ch == "," and depth == 0:
            args.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    args.append("".join(cur))
    return args


def prepare(isf_text):
    hdr = C.find_isf_header(isf_text)
    if not hdr:
        raise ValueError("no ISF header")
    header = json.loads(C.sanitize_json(hdr[0]))
    body = isf_text[hdr[2]:]
    decl = []
    images = set()
    for inp in header.get("INPUTS", []):
        t = str(inp.get("TYPE", "")).lower()
        n = inp.get("NAME")
        glt = {"float": "float", "bool": "bool", "event": "bool", "long": "int", "color": "vec4",
               "point2d": "vec2", "image": "sampler2D", "audio": "sampler2D", "audiofft": "sampler2D"}.get(t)
        if glt:
            decl.append(f"uniform {glt} {n};")
            if glt == "sampler2D":
                images.add(n)
    for p in header.get("PASSES", []) or []:
        if p.get("TARGET"):
            images.add(p["TARGET"])
            decl.append(f"uniform sampler2D {p['TARGET']};")
    imported = header.get("IMPORTED", {})
    names = list(imported.keys()) if isinstance(imported, dict) else [x.get("NAME") for x in imported]
    for n in names:
        if n:
            images.add(n)
            decl.append(f"uniform sampler2D {n};")
    for n in images:
        decl.append(f"uniform vec2 _{n}_imgSize;")
    body = _expand_img_macros(body, images)
    body = re.sub(r"\bgl_FragColor\b", "isf_FragColor", body)
    pre = ("#version 330\n"
           "uniform int PASSINDEX; uniform vec2 RENDERSIZE; uniform float TIME; uniform float TIMEDELTA;\n"
           "uniform int FRAMEINDEX; uniform vec4 DATE;\n"
           "in vec2 ffm_uv;  // validator's vertex shader output, bottom-left origin like ISF\n"
           "#define isf_FragNormCoord ffm_uv\n"
           "out vec4 isf_FragColor;\n" + "\n".join(decl) + "\n")
    return pre + body


def compile_isf(isf_text):
    try:
        src = prepare(isf_text)
    except Exception as e:
        return False, [(0, f"ISF host rejected file: {e}")]
    ok, errs, _ = V.compile_programs([src])[0]
    return ok, errs
