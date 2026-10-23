"""Offline GPU validation: compile generated shaders with the real driver and
render test frames, mirroring the FFGL runtime (passes, buffers, inputs)."""
import ctypes
import math
import re
import struct
import sys
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


@contextmanager
def window_lock():
    """For OutputView window work on the main thread (poll, toggle) while the
    output thread draws. On macOS that mustn't overlap a frame (it aborts in
    Metal), so it takes gpu()'s lock, without making the context current (no GL
    calls; switching costs ~0.3 ms each way). Elsewhere it needs nothing: GLFW
    allows events on the main thread while another thread draws and swaps, and
    waiting there would stall the UI for up to a frame (the swap waits for vsync)."""
    if sys.platform == "darwin":
        with _lock:
            yield
    else:
        yield


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
        pv = Previewer(ir, glsl_list, width, height)
        try:
            dt = 1.0 / 60.0
            results, pixels = [], None
            for t_sample in times:
                steps = max(1, frames_between)
                sim_time = max(0.0, t_sample - steps * dt)
                for _ in range(steps):
                    sim_time += dt
                    pv.render_frame(sim_time, dt)
                pixels = pv.read()
                results.append(_stats(pixels))
            return {"frames": results, "rgba": pixels, "size": (width, height)}
        finally:
            pv.close()


class Previewer:
    """Runs a converted shader the way the FFGL runtime does (passes, feedback
    buffers, embedded images, audio, params). Create/use inside gpu()."""

    def __init__(self, ir, glsl_list, width=320, height=180):
        self.ctx = ctx = context()
        gl = self.gl = ctx.gl
        self.ir = ir
        self.width, self.height = width, height
        self.frame = 0
        self.values = {}            # param index -> live value (defaults otherwise)
        self.phases = None          # ir.phases running totals, as the plugin keeps them
        self._phase_time = 0.0
        self.input_tex = list(ctx.test_input)
        self._own_input = []
        self.progs = []
        for src in glsl_list:
            prog, errs, log = ctx.program(src)
            if not prog:
                self.close()
                raise RuntimeError(f"compile failed: {errs[:1]}")
            self.progs.append(prog)
        self.out_tex = ctx._texture(width, height, None)
        self.out_fbo = gl.glGenFramebuffers(1)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self.out_fbo)
        gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, self.out_tex, 0)
        gl.glClearColor(0, 0, 0, 1)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)

        self.targets = {}
        for ps in ir.passes:
            if ps.target and ps.target not in self.targets:
                self.targets[ps.target] = {"pass": ps, "tex": [None, None], "fbo": [None, None],
                                           "front": 0, "size": None}

        from . import images as IMG
        self.img_tex = {}
        for k, im in enumerate([i for i in ir.images if i.source == "imported"]):
            w_, h_, px = IMG.rgba(im, k)
            tex = ctx._texture(w_, h_, px)
            gl.glBindTexture(gl.GL_TEXTURE_2D, tex)
            gl.glGenerateMipmap(gl.GL_TEXTURE_2D)
            f = im.filter or "mipmap"
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, _MIN_FILTER[f](gl))
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER,
                               gl.GL_NEAREST if f == "nearest" else gl.GL_LINEAR)
            wrap = gl.GL_REPEAT if im.repeat else gl.GL_CLAMP_TO_EDGE
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, wrap)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, wrap)
            gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
            self.img_tex[im.name] = tex
        for im in ir.images:
            if im.source == "audio":
                self.img_tex[im.name] = self._audio_texture(im.rows)
        # Per-channel sampler overrides for the clip and buffers, as in the plugin.
        self.samplers = {}
        for im in ir.images:
            if im.source in ("host", "target") and (im.filter or im.wrap):
                f = im.filter or "linear"
                if im.source == "host" and f == "mipmap":
                    f = "linear"
                so = gl.glGenSamplers(1)
                gl.glSamplerParameteri(so, gl.GL_TEXTURE_MIN_FILTER, _MIN_FILTER[f](gl))
                gl.glSamplerParameteri(so, gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST if f == "nearest" else gl.GL_LINEAR)
                w = gl.GL_REPEAT if im.wrap == "repeat" else gl.GL_CLAMP_TO_EDGE
                gl.glSamplerParameteri(so, gl.GL_TEXTURE_WRAP_S, w)
                gl.glSamplerParameteri(so, gl.GL_TEXTURE_WRAP_T, w)
                self.samplers[im.name] = so
        self.mip_targets = {i.target for i in ir.images if i.source == "target" and i.filter == "mipmap"}

    def _audio_texture(self, rows):
        gl = self.gl
        # Synthetic spectrum: strong bass falling off, like real music.
        spec = [math.exp(-i / 80.0) * (0.7 + 0.3 * math.sin(i * 0.37)) for i in range(512)]
        data = struct.pack(f"{512 * rows}f", *(spec * rows))
        tex = gl.glGenTextures(1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, tex)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_R32F, 512, rows, 0, gl.GL_RED, gl.GL_FLOAT, data)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
        gl.glTexParameteriv(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_SWIZZLE_RGBA,
                            [gl.GL_RED, gl.GL_RED, gl.GL_RED, gl.GL_ONE])
        gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
        return tex

    def set_input_image(self, w, h, rgba_bottom_up, index=0):
        """Replace the test pattern fed to host image inputs."""
        tex = self.ctx._texture(w, h, rgba_bottom_up)
        self._own_input.append(tex)
        while len(self.input_tex) <= index:
            self.input_tex.append(self.input_tex[0])
        self.input_tex[index] = tex

    def value(self, i, p):
        return self.values.get(i, p.default)

    def _ensure_target(self, t, w, h):
        gl = self.gl
        if t["size"] == (w, h):
            return
        if t["tex"][0]:
            gl.glDeleteTextures(t["tex"])
            gl.glDeleteFramebuffers(2, t["fbo"])
        fmt = gl.GL_RGBA32F if t["pass"].float else gl.GL_RGBA8
        for i in range(2):
            t["tex"][i] = self.ctx._texture(w, h, None, fmt)
            t["fbo"][i] = gl.glGenFramebuffers(1)
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, t["fbo"][i])
            gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, t["tex"][i], 0)
            gl.glClearColor(0, 0, 0, 0)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT)
        t["size"] = (w, h)

    def render_frame(self, sim_time, dt):
        gl, ctx, ir = self.gl, self.ctx, self.ir
        width, height = self.width, self.height
        named = {p.name: _Live(p, self.value(i, p)) for i, p in enumerate(ir.params) if p.name}
        mouse = next(((i, p) for i, p in enumerate(ir.params) if p.kind == "mouse"), None)
        click = next(((i, p) for i, p in enumerate(ir.params) if p.kind == "mouseclick"), None)
        # Phases advance with the clock (which can jump, e.g. preview restart), at
        # the sliders' current values.
        rates = []
        for ph in ir.phases:
            r = 1.0
            for nm in ph.params:
                i, p = next((i, p) for i, p in enumerate(ir.params) if p.name == nm)
                r *= float(self.value(i, p))
            rates.append(r)
        if self.phases is None:
            self.phases = [r * sim_time for r in rates]
        else:
            self.phases = [ph + r * (sim_time - self._phase_time) for ph, r in zip(self.phases, rates)]
        self._phase_time = sim_time
        for pi, ps in enumerate(ir.passes):
            w, h = width, height
            if ps.target:
                t = self.targets[ps.target]
                w, h = _pass_size(ps, width, height, named)
                self._ensure_target(t, w, h)
                gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, t["fbo"][1 - t["front"]])
            else:
                gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self.out_fbo)
            gl.glViewport(0, 0, w, h)
            prog = self.progs[ps.program]
            gl.glUseProgram(prog)
            _u(gl, prog, "ffm_Resolution", 2, (w, h))
            _u(gl, prog, "ffm_Time", 1, (sim_time,))
            _u(gl, prog, "ffm_TimeDelta", 1, (dt,))
            for ph, v in zip(ir.phases, self.phases):
                _u(gl, prog, ph.name, 1, (v,))
            _ui(gl, prog, "ffm_Frame", self.frame)
            _ui(gl, prog, "ffm_PassIndex", pi)
            beat = sim_time * 120.0 / 60.0     # the plugin's tempo when the host sends none
            _u(gl, prog, "ffm_BPM", 1, (120.0,))
            _u(gl, prog, "ffm_Beat", 1, (beat,))
            _u(gl, prog, "ffm_BarPhase", 1, (beat / 4.0 - math.floor(beat / 4.0),))
            _u(gl, prog, "ffm_Date", 4, (2026.0, 9.0, 20.0, 43200.0 + sim_time))
            mx, my = (0.0, 0.0)
            if mouse:
                mv = self.value(*mouse)
                mx, my = mv[0] * w, mv[1] * h
            down = bool(click and self.value(*click))
            _u(gl, prog, "ffm_Mouse", 4, (mx, my, mx if down else -mx, my if down else -my))
            for live in named.values():
                _set_param(gl, prog, live, w, h)
            unit = 0
            for im in ir.images:
                tex = ctx.black
                if im.source == "host":
                    tex = self.input_tex[min(im.index, len(self.input_tex) - 1)]
                elif im.source in ("imported", "audio"):
                    tex = self.img_tex[im.name]
                elif im.source == "target":
                    t = self.targets[im.target]
                    tex = t["tex"][t["front"]] if t["tex"][0] else ctx.black
                before = unit
                unit = _bind(gl, prog, im.name, tex, unit)
                if unit > before and im.name in self.samplers and tex != ctx.black:
                    gl.glBindSampler(before, self.samplers[im.name])
            for name, t in self.targets.items():
                tex = t["tex"][t["front"]] if t["tex"][0] else ctx.black
                unit = _bind(gl, prog, name, tex, unit)
            gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
            for u in range(unit):
                gl.glBindSampler(u, 0)
            if ps.target:
                t = self.targets[ps.target]
                t["front"] ^= 1
                if ps.target in self.mip_targets:
                    gl.glBindTexture(gl.GL_TEXTURE_2D, t["tex"][t["front"]])
                    gl.glGenerateMipmap(gl.GL_TEXTURE_2D)
                    gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
        if ir.passes[-1].target:
            t = self.targets[ir.passes[-1].target]
            gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, t["fbo"][t["front"]])
            gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, self.out_fbo)
            gl.glBlitFramebuffer(0, 0, t["size"][0], t["size"][1], 0, 0, width, height,
                                 gl.GL_COLOR_BUFFER_BIT, gl.GL_LINEAR)
        self.frame += 1
        # Events are one-frame pulses, as in the plugin.
        for i, p in enumerate(ir.params):
            if p.kind == "event":
                self.values[i] = False

    def resize(self, width, height):
        """Render at a new size from the next frame on (buffers re-allocate
        themselves; feedback buffers start over)."""
        if (width, height) == (self.width, self.height):
            return
        gl = self.gl
        gl.glDeleteFramebuffers(1, [self.out_fbo])
        gl.glDeleteTextures([self.out_tex])
        self.width, self.height = width, height
        self.out_tex = self.ctx._texture(width, height, None)
        self.out_fbo = gl.glGenFramebuffers(1)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self.out_fbo)
        gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, self.out_tex, 0)
        gl.glClearColor(0, 0, 0, 1)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)

    def read(self):
        gl = self.gl
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self.out_fbo)
        gl.glFinish()
        px = gl.glReadPixels(0, 0, self.width, self.height, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
        return px if isinstance(px, (bytes, bytearray)) else bytes(px)

    def close(self):
        gl = self.gl
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
        gl.glUseProgram(0)
        for p in self.progs:
            gl.glDeleteProgram(p)
        self.progs = []
        if getattr(self, "out_fbo", None):
            gl.glDeleteFramebuffers(1, [self.out_fbo])
            gl.glDeleteTextures([self.out_tex])
            self.out_fbo = None
        if getattr(self, "img_tex", None):
            gl.glDeleteTextures(list(self.img_tex.values()))
            self.img_tex = {}
        for t in getattr(self, "targets", {}).values():
            if t["tex"][0]:
                gl.glDeleteTextures(t["tex"])
                gl.glDeleteFramebuffers(2, t["fbo"])
                t["tex"] = [None, None]
        if self._own_input:
            gl.glDeleteTextures(self._own_input)
            self._own_input = []
        if getattr(self, "samplers", None):
            gl.glDeleteSamplers(len(self.samplers), list(self.samplers.values()))
            self.samplers = {}


def _double_click_time():
    """The system's double-click interval in seconds (Windows setting; 0.5 s elsewhere)."""
    if sys.platform == "win32":
        try:
            return ctypes.windll.user32.GetDoubleClickTime() / 1000.0
        except Exception:
            pass
    return 0.5


def _cocoa_set_level(nswindow, level):
    """[nswindow setLevel:level] through the Objective-C runtime (no PyObjC)."""
    objc = ctypes.cdll.LoadLibrary("/usr/lib/libobjc.A.dylib")
    objc.sel_registerName.restype = ctypes.c_void_p
    objc.sel_registerName.argtypes = [ctypes.c_char_p]
    send = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long)(
        ("objc_msgSend", objc))
    send(nswindow, objc.sel_registerName(b"setLevel:"), level)


class OutputView:
    """A window that shows a Previewer's output. It shares textures with the
    validation context, so frames go to the screen without a CPU copy.

    windowed=False: fullscreen on the monitor nearest `near` (FFMaker's), closed
    by Esc, Ctrl+F (⌘F) or a double-click.
    windowed=True: a normal window ("output window"), on another monitor when
    there is one, that can be moved and resized. Double-click or Ctrl+F toggles
    fullscreen on the monitor it's on; Esc goes back to the window; its close
    button closes it.
    Left / Right set `nav` (playlist). Create, use and close inside gpu(), on
    the main thread."""

    TITLE = "FFMaker output  (double-click or Ctrl+F: fullscreen, ←/→: queue)"

    def __init__(self, near=None, windowed=False, max_width=1920):
        import glfw
        self.glfw = glfw
        self.ctx = ctx = context()
        self.gl = gl = ctx.gl
        self.max_width = max_width
        self.windowed = windowed                   # opened as a window (Esc returns to it)
        self.fullscreen = False
        self._saved = None                         # window pos/size while fullscreen
        home = _monitor_at(glfw, near) if near else glfw.get_primary_monitor()
        glfw.default_window_hints()
        for hint, value in ((glfw.CONTEXT_VERSION_MAJOR, 4), (glfw.CONTEXT_VERSION_MINOR, 1),
                            (glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE),
                            (glfw.OPENGL_FORWARD_COMPAT, True), (glfw.AUTO_ICONIFY, False)):
            glfw.window_hint(hint, value)
        if windowed:
            # On another monitor when there is one, else next to FFMaker.
            # Compare by address: each GLFW call returns new ctypes pointer objects.
            addr = lambda m: ctypes.cast(m, ctypes.c_void_p).value
            others = [m for m in glfw.get_monitors() if addr(m) != addr(home)]
            mon = others[0] if others else home
            mx, my, mw, mh = glfw.get_monitor_workarea(mon)
            w, h = min(960, mw * 2 // 3), min(540, mh * 2 // 3)
            glfw.window_hint(glfw.VISIBLE, False)
            self.win = glfw.create_window(w, h, self.TITLE, None, ctx.win)
            if self.win:
                glfw.set_window_pos(self.win, mx + (mw - w) // 2, my + (mh - h) // 2)
                glfw.show_window(self.win)
        else:
            vm = glfw.get_video_mode(home)
            for hint, value in ((glfw.RED_BITS, vm.bits.red), (glfw.GREEN_BITS, vm.bits.green),
                                (glfw.BLUE_BITS, vm.bits.blue), (glfw.REFRESH_RATE, vm.refresh_rate)):
                glfw.window_hint(hint, value)
            # A borderless window covering the monitor (see _cover), not a GLFW
            # monitor-fullscreen window.
            glfw.window_hint(glfw.DECORATED, False)
            glfw.window_hint(glfw.RESIZABLE, False)
            self.win = glfw.create_window(vm.size.width, vm.size.height, self.TITLE, None, ctx.win)
            if self.win:
                self._cover(home)
            self.fullscreen = True
        glfw.default_window_hints()
        if not self.win:
            glfw.make_context_current(ctx.win)
            raise RuntimeError("could not open the output window")
        _set_window_icon(glfw, self.win)
        self.closed = False
        self.nav = 0                               # -1 / +1: Left / Right pressed (playlist)
        self._toggle = self._escape = False
        self._last_click = None
        glfw.set_key_callback(self.win, self._key)
        glfw.set_mouse_button_callback(self.win, self._mouse)
        if self.fullscreen:
            glfw.set_input_mode(self.win, glfw.CURSOR, glfw.CURSOR_HIDDEN)
        glfw.focus_window(self.win)
        glfw.make_context_current(self.win)
        glfw.swap_interval(1)                      # vsync: paced by the display, no tearing
        self.fbo = gl.glGenFramebuffers(1)        # framebuffers aren't shared between contexts
        self._tex = None
        glfw.make_context_current(ctx.win)
        # Window pixels, refreshed by poll(): GLFW only allows window queries on
        # the main thread, and frames may be drawn on another one.
        self.fb_size = glfw.get_framebuffer_size(self.win)
        # Refresh rate of the window's monitor (e.g. 120 Hz on a MacBook Pro), refreshed
        # by poll(): the frame-rate cap for drawing loops.
        self.refresh = 60
        self._update_refresh()

    def _update_refresh(self):
        glfw = self.glfw
        x, y = glfw.get_window_pos(self.win)
        w, h = glfw.get_window_size(self.win)
        self.refresh = max(30, glfw.get_video_mode(_monitor_at(glfw, (x + w // 2, y + h // 2))).refresh_rate or 60)

    # ── Fullscreen on/off ──
    def _cover(self, mon):
        """Fullscreen as a borderless window covering the monitor, kept on top,
        rather than GLFW's monitor fullscreen:
        - macOS reports video modes in points, so monitor fullscreen switches a
          Retina display to a low-resolution mode. Raised above the menu bar.
        - Windows gives a window that exactly covers a monitor "fullscreen"
          presentation, and switches in and out of it (a visible flash) whenever
          focus moves to or from it. One pixel taller than the monitor avoids that;
          the extra row is off-screen."""
        glfw = self.glfw
        vm = glfw.get_video_mode(mon)
        w, h = vm.size.width, vm.size.height
        if sys.platform == "darwin":
            # Raise the level first: macOS keeps windows below it out from under the
            # menu bar, so moving the window to the top would leave it pushed down.
            _cocoa_set_level(glfw.get_cocoa_window(self.win), 25)    # NSMainMenuWindowLevel + 1
            glfw.set_window_pos(self.win, *glfw.get_monitor_pos(mon))
            glfw.set_window_size(self.win, w, h)
        else:
            glfw.set_window_attrib(self.win, glfw.FLOATING, True)    # above the taskbar
            glfw.set_window_pos(self.win, *glfw.get_monitor_pos(mon))
            glfw.set_window_size(self.win, w, h + 1)
        # No focus change here: going fullscreen from FFMaker (Ctrl+F there) leaves
        # the keyboard with FFMaker. A newly opened view takes focus in __init__.

    def set_fullscreen(self, on):
        """Output window only: fullscreen on the monitor it's on, or back to the window."""
        glfw = self.glfw
        if on == self.fullscreen or not self.windowed:
            return
        if on:
            x, y = glfw.get_window_pos(self.win)
            w, h = glfw.get_window_size(self.win)
            self._saved = (x, y, w, h)
            mon = _monitor_at(self.glfw, (x + w // 2, y + h // 2))
            glfw.set_window_attrib(self.win, glfw.DECORATED, False)
            self._cover(mon)
            glfw.set_input_mode(self.win, glfw.CURSOR, glfw.CURSOR_HIDDEN)
        else:
            x, y, w, h = self._saved
            if sys.platform == "darwin":
                _cocoa_set_level(glfw.get_cocoa_window(self.win), 0)   # NSNormalWindowLevel
            else:
                glfw.set_window_attrib(self.win, glfw.FLOATING, False)
            glfw.set_window_attrib(self.win, glfw.DECORATED, True)
            glfw.set_window_size(self.win, w, h)
            glfw.set_window_pos(self.win, x, y)
            glfw.set_input_mode(self.win, glfw.CURSOR, glfw.CURSOR_NORMAL)
        self.fullscreen = on

    def toggle(self):
        """Ctrl+F / double-click / ⛶: the output window toggles fullscreen; the
        plain fullscreen view closes."""
        if self.windowed:
            self.set_fullscreen(not self.fullscreen)
        else:
            self.closed = True

    def escape(self):
        """Esc: the output window leaves fullscreen; the plain fullscreen view closes."""
        if self.windowed:
            self.set_fullscreen(False)
        else:
            self.closed = True

    # ── Input ──
    def _key(self, win, key, scancode, action, mods):
        glfw = self.glfw
        if action != glfw.PRESS:
            return
        mod = glfw.MOD_SUPER if sys.platform == "darwin" else glfw.MOD_CONTROL
        if key == glfw.KEY_ESCAPE:
            self._escape = True
        elif key == glfw.KEY_F and mods & mod:
            self._toggle = True
        elif key in (glfw.KEY_LEFT, glfw.KEY_RIGHT):
            self.nav = -1 if key == glfw.KEY_LEFT else 1

    def _mouse(self, win, button, action, mods):
        if button != self.glfw.MOUSE_BUTTON_LEFT or action != self.glfw.PRESS:
            return
        import time
        now = time.perf_counter()
        if self._last_click is not None and now - self._last_click <= _double_click_time():
            self._toggle = True
            now = None                             # a third click starts a new double-click
        self._last_click = now

    def poll(self):
        """Process window events and act on them (main thread). False once the
        view should close."""
        self.glfw.poll_events()
        # Act outside the callbacks: changing the window from inside them isn't safe.
        if self._toggle:
            self._toggle = False
            self.toggle()
        if self._escape:
            self._escape = False
            self.escape()
        if self.glfw.window_should_close(self.win):
            self.closed = True
        self.fb_size = self.glfw.get_framebuffer_size(self.win)
        self._update_refresh()
        return not self.closed

    # ── Drawing (any thread, inside gpu()) ──
    def render_size(self):
        """The size to render at: the window's pixels, at most max_width wide."""
        fw, fh = self.fb_size
        if fw <= 0 or fh <= 0:                     # minimised
            return None
        scale = min(1.0, self.max_width / fw)
        return max(1, int(fw * scale)), max(1, int(fh * scale))

    def reattach(self):
        """Call when switching Previewers: re-attach the texture on the next show
        (a new texture can reuse a deleted one's id)."""
        self._tex = None

    def show(self, pv):
        """Put pv's last rendered frame in the window, scaled to fit (letterboxed
        if the shapes differ, e.g. mid-resize)."""
        gl, glfw = self.gl, self.glfw
        fw, fh = self.fb_size
        if fw <= 0 or fh <= 0:
            return
        gl.glFlush()                               # finish the frame before the other context reads it
        glfw.make_context_current(self.win)
        try:
            gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, self.fbo)
            if self._tex != pv.out_tex:
                gl.glFramebufferTexture2D(gl.GL_READ_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0,
                                          gl.GL_TEXTURE_2D, pv.out_tex, 0)
                self._tex = pv.out_tex
            gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, 0)
            gl.glViewport(0, 0, fw, fh)
            gl.glClearColor(0, 0, 0, 1)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT)
            s = min(fw / pv.width, fh / pv.height)
            w, h = int(pv.width * s), int(pv.height * s)
            x, y = (fw - w) // 2, (fh - h) // 2
            gl.glBlitFramebuffer(0, 0, pv.width, pv.height, x, y, x + w, y + h,
                                 gl.GL_COLOR_BUFFER_BIT, gl.GL_LINEAR)
            glfw.swap_buffers(self.win)
        finally:
            glfw.make_context_current(self.ctx.win)

    def close(self):
        gl, glfw = self.gl, self.glfw
        if not self.win:
            return
        glfw.make_context_current(self.win)
        gl.glDeleteFramebuffers(1, [self.fbo])
        glfw.make_context_current(self.ctx.win)
        # Show the cursor before destroying the window: on macOS the hidden cursor
        # otherwise stays hidden over FFMaker afterwards.
        glfw.set_input_mode(self.win, glfw.CURSOR, glfw.CURSOR_NORMAL)
        glfw.poll_events()
        glfw.destroy_window(self.win)
        self.win = None


def _set_window_icon(glfw, win):
    """FFMaker's icon on the output window (title bar, taskbar). macOS windows
    have no icons; the app's Dock icon is used there."""
    if sys.platform == "darwin":
        return
    try:
        import os
        from PIL import Image
        from . import paths
        d = os.path.join(paths.icon_dir(), "png")
        glfw.set_window_icon(win, 3, [Image.open(os.path.join(d, f"ffmaker_{s}.png")).convert("RGBA")
                                      for s in (16, 32, 48)])
    except Exception:
        pass                                       # cosmetic


def _monitor_at(glfw, point):
    """The monitor containing a screen point (primary if none does)."""
    for m in glfw.get_monitors():
        mx, my = glfw.get_monitor_pos(m)
        vm = glfw.get_video_mode(m)
        if mx <= point[0] < mx + vm.size.width and my <= point[1] < my + vm.size.height:
            return m
    return glfw.get_primary_monitor()


class _Live:
    """A param with a live value, shaped like ir.Param for _set_param/_pass_size."""
    def __init__(self, p, value):
        self.name, self.kind, self.glsl_type = p.name, p.kind, p.glsl_type
        self.pixel_space, self.values = p.pixel_space, p.values
        self.default = value


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


_MIN_FILTER = {"nearest": lambda gl: gl.GL_NEAREST, "linear": lambda gl: gl.GL_LINEAR,
               "mipmap": lambda gl: gl.GL_LINEAR_MIPMAP_LINEAR}


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
