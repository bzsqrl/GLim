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
           "in vec2 glim_uv;  // validator's vertex shader output, bottom-left origin like ISF\n"
           "#define isf_FragNormCoord glim_uv\n"
           "out vec4 isf_FragColor;\n" + "\n".join(decl) + "\n")
    return pre + body


def compile_isf(isf_text):
    try:
        src = prepare(isf_text)
    except Exception as e:
        return False, [(0, f"ISF host rejected file: {e}")]
    ok, errs, _ = V.compile_programs([src])[0]
    return ok, errs


def render_isf(isf_text, upper_left=False, width=64, height=36, time=1.0):
    """Render one frame of a single-pass ISF file the way an ISF host would:
    isf_FragNormCoord comes from the vertex shader, inputs sit at their
    defaults and image inputs get a test pattern. upper_left=True redeclares
    gl_FragCoord with a top-left origin, as some hosts (MadMapper on macOS)
    effectively have, so output that depends on gl_FragCoord's origin shows up.
    Returns RGBA bytes (bottom-up), or None for multi-pass files."""
    hdr = C.find_isf_header(isf_text)
    header = json.loads(C.sanitize_json(hdr[0])) if hdr else {}
    if len(header.get("PASSES", []) or []) > 1:
        return None
    src = prepare(isf_text)
    if upper_left:
        src = src.replace("\n", "\nlayout(origin_upper_left) in vec4 gl_FragCoord;\n", 1)
    with V.gpu() as ctx:
        gl = ctx.gl
        prog, errs, _ = ctx.program(src)
        if prog is None:
            raise RuntimeError(f"ISF compile failed: {errs[:1]}")
        tex = ctx._texture(width, height, None)
        fbo = gl.glGenFramebuffers(1)
        try:
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
            gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, tex, 0)
            gl.glViewport(0, 0, width, height)
            gl.glUseProgram(prog)
            V._u(gl, prog, "RENDERSIZE", 2, (width, height))
            V._u(gl, prog, "TIME", 1, (time,))
            V._u(gl, prog, "TIMEDELTA", 1, (1.0 / 60.0,))
            V._u(gl, prog, "DATE", 4, (2026.0, 9.0, 20.0, 43200.0 + time))
            imported = header.get("IMPORTED", {})
            images = list(imported.keys()) if isinstance(imported, dict) else [x.get("NAME") for x in imported]
            for inp in header.get("INPUTS", []):
                t, n, d = str(inp.get("TYPE", "")).lower(), inp.get("NAME"), inp.get("DEFAULT")
                loc = gl.glGetUniformLocation(prog, n)
                if t in ("image", "audio", "audiofft"):
                    images.append(n)
                elif loc < 0 or d is None:
                    continue
                elif t == "float":
                    gl.glUniform1f(loc, float(d))
                elif t in ("bool", "event", "long"):
                    gl.glUniform1i(loc, int(d))
                elif t == "color":
                    gl.glUniform4f(loc, *(list(d) + [1.0] * 4)[:4])
                elif t == "point2d":
                    gl.glUniform2f(loc, *d[:2])
            for unit, n in enumerate(images):
                V._bind(gl, prog, n, ctx.test_input[0], unit)
                V._u(gl, prog, f"_{n}_imgSize", 2, (256.0, 256.0))
            gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
            gl.glFinish()
            px = gl.glReadPixels(0, 0, width, height, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
        finally:
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
            gl.glDeleteFramebuffers(1, [fbo])
            gl.glDeleteTextures([tex])
            gl.glDeleteProgram(prog)
    return px if isinstance(px, (bytes, bytearray)) else bytes(px)


def origin_independent(isf_text, tolerance=3):
    """True if the file renders the same whichever way up gl_FragCoord runs,
    compared per cell of a 4x4 grid. None when it can't be judged: multi-pass
    files, or output that differs between two identical renders (e.g. a
    shader reading uninitialized variables)."""
    w, h = 64, 36
    a = render_isf(isf_text, False, w, h)
    if a is None:
        return None

    def grid(px):
        cells = []
        for gy in range(4):
            for gx in range(4):
                s = [0, 0, 0, 0]
                n = 0
                for y in range(gy * h // 4, (gy + 1) * h // 4):
                    for x in range(gx * w // 4, (gx + 1) * w // 4):
                        i = 4 * (y * w + x)
                        for c in range(4):
                            s[c] += px[i + c]
                        n += 1
                cells.append([v / n for v in s])
        return cells

    def same(p, q):
        return all(abs(x - y) < tolerance for cp, cq in zip(grid(p), grid(q)) for x, y in zip(cp, cq))
    if not same(a, render_isf(isf_text, False, w, h)):
        return None
    return same(a, render_isf(isf_text, True, w, h))
