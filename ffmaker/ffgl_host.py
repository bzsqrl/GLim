"""Minimal FFGL 2 host for smoke-testing built plugins without Resolume.

Loads the plugin binary, instantiates it in the validator's GL context,
renders a few frames into an FBO and reads the result back.
"""
import ctypes
import struct
import sys
import time

from . import validate as V

FF_GET_INFO = 0
FF_DEINITIALISE = 2
FF_GET_NUM_PARAMETERS = 4
FF_GET_PARAMETER_NAME = 5
FF_GET_PARAMETER_DEFAULT = 6
FF_GET_PARAMETER_DISPLAY = 7
FF_SET_PARAMETER = 8
FF_GET_PARAMETER = 9
FF_GET_PARAMETER_TYPE = 15
FF_PROCESS_OPENGL = 17
FF_INSTANTIATE_GL = 18
FF_DEINSTANTIATE_GL = 19
FF_INITIALISE_V2 = 34
FF_FAIL = 1


class Viewport(ctypes.Structure):
    _fields_ = [("x", ctypes.c_uint32), ("y", ctypes.c_uint32),
                ("width", ctypes.c_uint32), ("height", ctypes.c_uint32)]


class TextureStruct(ctypes.Structure):
    _fields_ = [("Width", ctypes.c_uint32), ("Height", ctypes.c_uint32),
                ("HardwareWidth", ctypes.c_uint32), ("HardwareHeight", ctypes.c_uint32),
                ("Handle", ctypes.c_uint32)]


class ProcessGL(ctypes.Structure):
    _fields_ = [("numInputTextures", ctypes.c_uint32),
                ("inputTextures", ctypes.POINTER(ctypes.POINTER(TextureStruct))),
                ("HostFBO", ctypes.c_uint32)]


class SetParam(ctypes.Structure):
    _fields_ = [("ParameterNumber", ctypes.c_uint32), ("NewParameterValue", ctypes.c_uint64)]


class PluginInfo(ctypes.Structure):
    _fields_ = [("APIMajorVersion", ctypes.c_uint32), ("APIMinorVersion", ctypes.c_uint32),
                ("PluginUniqueID", ctypes.c_char * 4), ("PluginName", ctypes.c_char * 16),
                ("PluginType", ctypes.c_uint32)]


class Plugin:
    def __init__(self, path):
        self.ctx = V.context()
        loader = ctypes.WinDLL if sys.platform == "win32" else ctypes.CDLL
        self.lib = loader(path)
        self.main = self.lib.plugMain
        self.main.restype = ctypes.c_uint64
        self.main.argtypes = [ctypes.c_uint32, ctypes.c_uint64, ctypes.c_void_p]
        self.instance = None

    def call(self, code, value=0, instance=None):
        return self.main(code, value, instance)

    def info(self):
        p = self.call(FF_GET_INFO)
        pi = ctypes.cast(ctypes.c_void_p(p), ctypes.POINTER(PluginInfo)).contents
        return {"id": pi.PluginUniqueID.decode(errors="replace"),
                "name": pi.PluginName.split(b"\0")[0].decode(errors="replace"),
                "type": pi.PluginType, "api": (pi.APIMajorVersion, pi.APIMinorVersion)}

    def params(self):
        n = self.call(FF_GET_NUM_PARAMETERS) & 0xFFFFFFFF
        out = []
        for i in range(n):
            name = ctypes.cast(ctypes.c_void_p(self.call(FF_GET_PARAMETER_NAME, i)), ctypes.c_char_p).value
            ptype = self.call(FF_GET_PARAMETER_TYPE, i) & 0xFFFFFFFF
            out.append({"index": i, "name": (name or b"").decode(errors="replace"), "type": ptype})
        return out

    def instantiate(self, w, h):
        if self.call(FF_INITIALISE_V2) & 0xFFFFFFFF == FF_FAIL:
            raise RuntimeError("FF_INITIALISE_V2 failed")
        self.vp = Viewport(0, 0, w, h)
        inst = self.call(FF_INSTANTIATE_GL, ctypes.addressof(self.vp))
        if not inst or inst == FF_FAIL:
            raise RuntimeError("FF_INSTANTIATE_GL failed (shader compile error?)")
        self.instance = ctypes.c_void_p(inst)

    def set_param(self, index, value):
        sp = SetParam(index, struct.unpack("<I", struct.pack("<f", value))[0])
        self.call(FF_SET_PARAMETER, ctypes.addressof(sp), self.instance)

    def get_param(self, index):
        v = self.call(FF_GET_PARAMETER, index, self.instance) & 0xFFFFFFFF
        return struct.unpack("<f", struct.pack("<I", v))[0]

    def display(self, index):
        p = self.call(FF_GET_PARAMETER_DISPLAY, index, self.instance)
        return ctypes.cast(ctypes.c_void_p(p), ctypes.c_char_p).value.decode(errors="replace")

    def close(self):
        if self.instance:
            self.call(FF_DEINSTANTIATE_GL, 0, self.instance)
            self.instance = None
        self.call(FF_DEINITIALISE)


def smoke_test(path, num_inputs=0, w=320, h=180, frames=30, frame_dt=1 / 60):
    """Load, run and read back a plugin. Returns dict with info, params, stats."""
    with V.gpu():
        return _smoke_test(path, num_inputs, w, h, frames, frame_dt)


def _smoke_test(path, num_inputs, w, h, frames, frame_dt):
    ctx = V.context()
    gl = ctx.gl
    plug = Plugin(path)
    info = plug.info()
    params = plug.params()
    plug.instantiate(w, h)

    out_tex = ctx._texture(w, h, None)
    fbo = gl.glGenFramebuffers(1)
    gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
    gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, out_tex, 0)
    texs = [TextureStruct(256, 256, 256, 256, int(ctx.test_input[i % 2])) for i in range(num_inputs)]
    ptrs = (ctypes.POINTER(TextureStruct) * max(1, num_inputs))(*[ctypes.pointer(t) for t in texs])
    pgl = ProcessGL(num_inputs, ptrs, int(fbo))

    stats = []
    for f in range(frames):
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
        gl.glViewport(0, 0, w, h)
        gl.glClearColor(0, 0, 0, 0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)
        r = plug.call(FF_PROCESS_OPENGL, ctypes.addressof(pgl), plug.instance) & 0xFFFFFFFF
        if r == FF_FAIL:
            raise RuntimeError("FF_PROCESS_OPENGL failed")
        err = gl.glGetError()
        if err:
            raise RuntimeError(f"GL error 0x{err:x} after ProcessOpenGL")
        if f in (0, frames - 1):
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
            px = gl.glReadPixels(0, 0, w, h, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
            stats.append(V._stats(bytes(px)))
            last = bytes(px)
        time.sleep(frame_dt)
    displays = [plug.display(p["index"]) for p in params]
    plug.close()
    gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
    gl.glDeleteFramebuffers(1, [fbo])
    gl.glDeleteTextures([out_tex])
    return {"info": info, "params": params, "displays": displays, "frames": stats,
            "rgba": last, "size": (w, h)}


if __name__ == "__main__":
    # python -m ffmaker.ffgl_host <plugin> <num_inputs>  -> JSON summary on stdout
    import json
    r = smoke_test(sys.argv[1], num_inputs=int(sys.argv[2]), frames=10)
    print(json.dumps({"info": r["info"], "params": len(r["params"]),
                      "mean": r["frames"][-1]["mean"], "distinct": r["frames"][-1]["distinct"]}))
