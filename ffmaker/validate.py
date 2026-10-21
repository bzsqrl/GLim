"""Offline GPU validation: compile generated shaders with the real driver and
render test frames, mirroring the FFGL runtime (passes, buffers, inputs)."""
import ctypes
import math
import re
import struct
import threading
from contextlib import contextmanager

_ctx = None
_lock = threading.RLock()

VERTEX = """#version 410 core
layout( location = 0 ) in vec4 vPosition;
layout( location = 1 ) in vec2 vUV;
out vec2 ffm_uv;
void main() { gl_Position = vPosition; ffm_uv = vUV; }
"""

_ERR_RES = [
    re.compile(r"^\s*\d+\((\d+)\)\s*:\s*(?:error|fatal)\s*\w*:?\s*(.*)$", re.I),   # NVIDIA
    re.compile(r"^\s*ERROR:\s*\d+:(\d+):\s*(.*)$", re.I),                         # AMD/Intel/Mesa/Apple
]


class ValidatorUnavailable(Exception):
    pass


class _Context:
    def __init__(self):
        try:
            import logging
            logging.getLogger("OpenGL").setLevel(logging.ERROR)
            import glfw
            import OpenGL
            OpenGL.ERROR_CHECKING = True
            import OpenGL.GL as gl
        except Exception as e:
            raise ValidatorUnavailable(f"PyOpenGL/glfw not available: {e}")
        if not glfw.init():
            raise ValidatorUnavailable("glfw.init() failed")
        glfw.window_hint(glfw.VISIBLE, glfw.FALSE)
        glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 4)
        glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 1)
        glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
        glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, True)
        self.win = glfw.create_window(64, 64, "ffmaker-validate", None, None)
        if not self.win:
            raise ValidatorUnavailable("Could not create an OpenGL 4.1 core context")
        glfw.make_context_current(self.win)
        self.gl = gl
        self.renderer = gl.glGetString(gl.GL_RENDERER).decode() + " / " + gl.glGetString(gl.GL_VERSION).decode()
        # Fullscreen quad
        self.vao = gl.glGenVertexArrays(1)
        gl.glBindVertexArray(self.vao)
        vbo = gl.glGenBuffers(1)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, vbo)
        data = struct.pack("24f", -1, -1, 0, 1, 0, 0, 1, -1, 0, 1, 1, 0, -1, 1, 0, 1, 0, 1, 1, 1, 0, 1, 1, 1)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, len(data), data, gl.GL_STATIC_DRAW)
        gl.glEnableVertexAttribArray(0)
        gl.glVertexAttribPointer(0, 4, gl.GL_FLOAT, False, 24, ctypes.c_void_p(0))
        gl.glEnableVertexAttribArray(1)
        gl.glVertexAttribPointer(1, 2, gl.GL_FLOAT, False, 24, ctypes.c_void_p(16))
        self.vs = self._shader(gl.GL_VERTEX_SHADER, VERTEX)[0]
        self.black = self._texture(1, 1, bytes(4))
        self.test_input = [self._test_pattern(256, 256, 0), self._test_pattern(256, 256, 1)]

    def _shader(self, kind, src):
        gl = self.gl
        sh = gl.glCreateShader(kind)
        gl.glShaderSource(sh, src)
        gl.glCompileShader(sh)
        ok = gl.glGetShaderiv(sh, gl.GL_COMPILE_STATUS) == gl.GL_TRUE
        log = gl.glGetShaderInfoLog(sh)
        log = log.decode(errors="replace") if isinstance(log, bytes) else str(log or "")
        return sh, ok, log.strip()

    def _texture(self, w, h, data, fmt=None, filt=None):
        gl = self.gl
        tex = gl.glGenTextures(1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, tex)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, fmt or gl.GL_RGBA8, w, h, 0, gl.GL_RGBA,
                        gl.GL_UNSIGNED_BYTE if fmt in (None, gl.GL_RGBA8) else gl.GL_FLOAT, data)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, filt or gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, filt or gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)
        gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
        return tex

    def _test_pattern(self, w, h, variant):
        px = bytearray()
        for y in range(h):
            for x in range(w):
                c = ((x // 32) + (y // 32)) % 2
                if variant == 0:
                    px += bytes((int(255 * x / w), int(255 * y / h), 160 if c else 60, 255))
                else:
                    px += bytes((200 if c else 30, 90, int(255 * (1 - x / w)), 255))
        return self._texture(w, h, bytes(px))

    def program(self, frag_src):
        """Compile + link. Returns (program or None, errors[list of (line, msg)], raw_log)."""
        gl = self.gl
        fs, ok, log = self._shader(gl.GL_FRAGMENT_SHADER, frag_src)
        if not ok:
            gl.glDeleteShader(fs)
            return None, parse_errors(log), log
        prog = gl.glCreateProgram()
        gl.glAttachShader(prog, self.vs)
        gl.glAttachShader(prog, fs)
        gl.glLinkProgram(prog)
        gl.glDeleteShader(fs)
        if gl.glGetProgramiv(prog, gl.GL_LINK_STATUS) != gl.GL_TRUE:
            log = gl.glGetProgramInfoLog(prog)
            log = log.decode(errors="replace") if isinstance(log, bytes) else str(log)
            gl.glDeleteProgram(prog)
            return None, [(0, "link: " + log.strip())], log
        return prog, [], log


def context():
    """The shared validation context, made current on the calling thread.
    Callers that issue GL calls should hold gpu() for the duration."""
    global _ctx
    with _lock:
        if _ctx is None:
            _ctx = _Context()
        import glfw
        glfw.make_context_current(_ctx.win)
        return _ctx


@contextmanager
def gpu():
    """Exclusive use of the validation GL context on this thread."""
    with _lock:
        ctx = context()
        try:
            yield ctx
        finally:
            import glfw
            glfw.make_context_current(None)


def parse_errors(log):
    errs = []
    for line in (log or "").splitlines():
        for rx in _ERR_RES:
            m = rx.match(line)
            if m:
                errs.append((int(m.group(1)), m.group(2).strip()))
                break
    if not errs and log and "error" in log.lower():
        errs.append((0, log.strip().splitlines()[0]))
    return errs


def compile_programs(glsl_list):
    """Returns list of (ok, errors, log) per program."""
    with gpu() as ctx:
        out = []
        for src in glsl_list:
            prog, errs, log = ctx.program(src)
            if prog:
                ctx.gl.glDeleteProgram(prog)
            out.append((prog is not None, errs, log))
        return out


def render(ir, glsl_list, width=320, height=180, times=(0.5, 2.0), frames_between=3):
    """Render the plugin offline. Returns dict with stats per sampled time and
    the RGBA bytes of the last frame."""
    with gpu():
        return _render(ir, glsl_list, width, height, times, frames_between)


def _render(ir, glsl_list, width, height, times, frames_between):
    ctx = context()
    gl = ctx.gl
    progs = []
    for src in glsl_list:
        p, errs, log = ctx.program(src)
        if not p:
            raise RuntimeError(f"compile failed: {errs[:1]}")
        progs.append(p)
    out_tex = ctx._texture(width, height, None)
    out_fbo = gl.glGenFramebuffers(1)
    gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, out_fbo)
    gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, out_tex, 0)

    targets = {}
    for p in ir.passes:
        if p.target and p.target not in targets:
            targets[p.target] = {"pass": p, "tex": [None, None], "fbo": [None, None], "front": 0, "size": None}

    def ensure_target(t, w, h):
        if t["size"] == (w, h):
            return
        fmt = gl.GL_RGBA32F if t["pass"].float else gl.GL_RGBA8
        for i in range(2):
            t["tex"][i] = ctx._texture(w, h, None, fmt)
            t["fbo"][i] = gl.glGenFramebuffers(1)
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, t["fbo"][i])
            gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, t["tex"][i], 0)
            gl.glClearColor(0, 0, 0, 0)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT)
        t["size"] = (w, h)

    from . import images as IMG
    img_tex = {}
    for k, im in enumerate([i for i in ir.images if i.source == "imported"]):
        w_, h_, px = IMG.rgba(im, k)
        tex = ctx._texture(w_, h_, px)
        gl.glBindTexture(gl.GL_TEXTURE_2D, tex)
        gl.glGenerateMipmap(gl.GL_TEXTURE_2D)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR_MIPMAP_LINEAR)
        wrap = gl.GL_REPEAT if im.repeat else gl.GL_CLAMP_TO_EDGE
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, wrap)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, wrap)
        gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
        img_tex[im.name] = tex

    for im in ir.images:
        if im.source == "audio":
            # Synthetic spectrum: strong bass falling off, like real music.
            spec = [math.exp(-i / 80.0) * (0.7 + 0.3 * math.sin(i * 0.37)) for i in range(512)]
            data = struct.pack(f"{512 * im.rows}f", *(spec * im.rows))
            tex = gl.glGenTextures(1)
            gl.glBindTexture(gl.GL_TEXTURE_2D, tex)
            gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_R32F, 512, im.rows, 0, gl.GL_RED, gl.GL_FLOAT, data)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
            gl.glTexParameteriv(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_SWIZZLE_RGBA,
                                [gl.GL_RED, gl.GL_RED, gl.GL_RED, gl.GL_ONE])
            gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
            img_tex[im.name] = tex

    values = {p.name: p for p in ir.params if p.name}
    results = []
    frame = 0
    sim_time = 0.0
    dt = 1.0 / 60.0
    pixels = None
    for t_sample in times:
        steps = max(1, frames_between)
        start_t = max(0.0, t_sample - steps * dt)
        sim_time = start_t
        for _ in range(steps):
            sim_time += dt
            for pi, ps in enumerate(ir.passes):
                w, h = width, height
                if ps.target:
                    t = targets[ps.target]
                    w, h = _pass_size(ps, width, height, values)
                    ensure_target(t, w, h)
                    gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, t["fbo"][1 - t["front"]])
                else:
                    gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, out_fbo)
                gl.glViewport(0, 0, w, h)
                prog = progs[ps.program]
                gl.glUseProgram(prog)
                _u(gl, prog, "ffm_Resolution", 2, (w, h))
                _u(gl, prog, "ffm_Time", 1, (sim_time,))
                _u(gl, prog, "ffm_TimeDelta", 1, (dt,))
                _ui(gl, prog, "ffm_Frame", frame)
                _ui(gl, prog, "ffm_PassIndex", pi)
                _u(gl, prog, "ffm_Date", 4, (2026.0, 9.0, 20.0, 43200.0 + sim_time))
                mp = next((p for p in ir.params if p.kind == "mouse"), None)
                mc = next((p for p in ir.params if p.kind == "mouseclick"), None)
                mx, my = (mp.default[0] * w, mp.default[1] * h) if mp else (0.0, 0.0)
                down = bool(mc and mc.default)
                _u(gl, prog, "ffm_Mouse", 4, (mx, my, mx if down else -mx, my if down else -my))
                for p in ir.params:
                    if p.name:
                        _set_param(gl, prog, p, w, h)
                unit = 0
                for im in ir.images:
                    tex = ctx.black
                    if im.source == "host":
                        tex = ctx.test_input[min(im.index, 1)]
                    elif im.source in ("imported", "audio"):
                        tex = img_tex[im.name]
                    unit = _bind(gl, prog, im.name, tex, unit)
                for name, t in targets.items():
                    tex = t["tex"][t["front"]] if t["tex"][0] else ctx.black
                    unit = _bind(gl, prog, name, tex, unit)
                gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
                if ps.target:
                    targets[ps.target]["front"] ^= 1
            if ir.passes[-1].target:
                t = targets[ir.passes[-1].target]
                gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, t["fbo"][t["front"]])
                gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, out_fbo)
                gl.glBlitFramebuffer(0, 0, t["size"][0], t["size"][1], 0, 0, width, height,
                                     gl.GL_COLOR_BUFFER_BIT, gl.GL_LINEAR)
            frame += 1
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, out_fbo)
        gl.glFinish()
        pixels = gl.glReadPixels(0, 0, width, height, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
        if not isinstance(pixels, (bytes, bytearray)):
            pixels = bytes(pixels)
        results.append(_stats(pixels))

    # cleanup
    gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
    gl.glUseProgram(0)
    for p in progs:
        gl.glDeleteProgram(p)
    gl.glDeleteFramebuffers(1, [out_fbo])
    gl.glDeleteTextures([out_tex])
    if img_tex:
        gl.glDeleteTextures(list(img_tex.values()))
    for t in targets.values():
        if t["tex"][0]:
            gl.glDeleteTextures(t["tex"])
            gl.glDeleteFramebuffers(2, t["fbo"])
    return {"frames": results, "rgba": pixels, "size": (width, height)}


def _pass_size(ps, W, H, values):
    def ev(expr, default):
        if not expr:
            return default
        e = str(expr).replace("$WIDTH", str(W)).replace("$HEIGHT", str(H))
        e = re.sub(r"\$(\w+)", lambda m: str(float(values[m.group(1)].default)) if m.group(1) in values else "0", e)
        try:
            return max(1, int(eval(e, {"__builtins__": {}}, {"floor": math.floor, "ceil": math.ceil,
                                                             "max": max, "min": min, "pow": pow,
                                                             "sqrt": math.sqrt, "abs": abs, "round": round})))
        except Exception:
            return default
    return ev(ps.width, W), ev(ps.height, H)


def _u(gl, prog, name, n, vals):
    loc = gl.glGetUniformLocation(prog, name)
    if loc >= 0:
        getattr(gl, f"glUniform{n}f")(loc, *vals)


def _ui(gl, prog, name, v):
    loc = gl.glGetUniformLocation(prog, name)
    if loc >= 0:
        gl.glUniform1i(loc, int(v))


def _bind(gl, prog, name, tex, unit):
    loc = gl.glGetUniformLocation(prog, name)
    if loc < 0:
        return unit
    gl.glActiveTexture(gl.GL_TEXTURE0 + unit)
    gl.glBindTexture(gl.GL_TEXTURE_2D, tex)
    gl.glUniform1i(loc, unit)
    gl.glActiveTexture(gl.GL_TEXTURE0)
    return unit + 1


def _set_param(gl, prog, p, w, h):
    loc = gl.glGetUniformLocation(prog, p.name)
    if loc < 0:
        return
    if p.kind == "float":
        gl.glUniform1f(loc, float(p.default))
    elif p.kind == "int":
        gl.glUniform1i(loc, int(p.default))
    elif p.kind in ("bool", "event"):
        gl.glUniform1i(loc, 1 if p.default else 0)
    elif p.kind == "long":
        gl.glUniform1i(loc, int(p.default))
    elif p.kind == "color":
        c = (list(p.default) + [1.0] * 4)[:4]
        if p.glsl_type == "vec3":
            gl.glUniform3f(loc, *c[:3])
        else:
            gl.glUniform4f(loc, *c)
    elif p.kind == "point2D":
        x, y = p.default
        if p.pixel_space:
            x, y = min(max(x / 1920.0, 0), 1) * w, min(max(y / 1080.0, 0), 1) * h
        gl.glUniform2f(loc, x, y)


def _stats(px):
    n = len(px) // 4
    step = max(1, n // 4000)
    total = [0, 0, 0, 0]
    mx = 0
    samples = 0
    distinct = set()
    for i in range(0, n, step):
        r, g, b, a = px[4 * i:4 * i + 4]
        total[0] += r; total[1] += g; total[2] += b; total[3] += a
        mx = max(mx, r, g, b)
        distinct.add((r >> 4, g >> 4, b >> 4))
        samples += 1
    mean = [t / samples for t in total]
    return {"mean": mean, "max": mx, "distinct": len(distinct)}


def save_png(rgba, size, path):
    from PIL import Image
    img = Image.frombytes("RGBA", size, rgba).transpose(Image.FLIP_TOP_BOTTOM)
    img.save(path)
