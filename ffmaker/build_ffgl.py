"""Compile a ShaderIR into an FFGL plugin (.dll on Windows, .bundle on macOS).

Uses one persistent CMake workspace in the user cache: the FFGL SDK is
compiled once, and each plugin build only recompiles Plugin.cpp against a new
ShaderData.h. The binary is then copied to the output folder under the
plugin's own name.
"""
import os
import re
import shutil
import subprocess
import sys
import threading

from . import emit_ffgl, paths

GLEW_URL = "https://github.com/nigels-com/glew/releases/download/glew-2.2.0/glew-2.2.0-win32.zip"
_lock = threading.Lock()


class BuildError(Exception):
    pass


def safe_name(name):
    s = re.sub(r"[^A-Za-z0-9_\-]", "_", name).strip("_")
    return s or "Shader"


def unique_plugin_name(name, taken):
    """FFGL shows only 16 characters of a plugin name. Make the visible part
    unique within `taken` (a set that is updated)."""
    short = name[:16]
    n = 2
    while short.lower() in taken:
        suffix = f"~{n}"
        short = name[:16 - len(suffix)] + suffix
        n += 1
    taken.add(short.lower())
    return name if short == name[:16] else short


def _write_if_changed(path, text):
    try:
        with open(path, encoding="utf-8") as f:
            if f.read() == text:
                return False
    except FileNotFoundError:
        pass
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return True


def _glew_root(log):
    if sys.platform != "win32":
        return None
    for base in (os.path.join(paths.app_dir(), "deps"), os.path.join(paths.cache_dir(), "deps")):
        d = os.path.join(base, "glew-2.2.0")
        if os.path.isdir(d):
            return d
    base = os.path.join(paths.cache_dir(), "deps")
    os.makedirs(base, exist_ok=True)
    log("Downloading GLEW (first build only)…")
    import urllib.request
    import zipfile
    zpath = os.path.join(base, "glew.zip")
    urllib.request.urlretrieve(GLEW_URL, zpath)
    with zipfile.ZipFile(zpath) as zf:
        zf.extractall(base)
    os.remove(zpath)
    return os.path.join(base, "glew-2.2.0")


def _run(cmd, cwd, log, cancel_event=None):
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    proc = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace", creationflags=flags)
    lines = []
    for line in proc.stdout:
        lines.append(line)
        if cancel_event is not None and cancel_event.is_set():
            proc.terminate()
            raise BuildError("cancelled")
    proc.wait()
    out = "".join(lines)
    if proc.returncode != 0:
        # Surface only the useful compiler lines.
        errs = [l.strip() for l in lines if re.search(r"\berror\b|CMake Error", l)]
        log("\n".join(errs[:20]) or out[-3000:])
        raise BuildError(f"{os.path.basename(cmd[0])} failed (exit {proc.returncode})")
    return out


def workspace_dir():
    return os.path.join(paths.cache_dir(), "ffgl_workspace")


def build(ir, glsl_list, plugin_name, out_dir=None, log=print, cancel_event=None):
    """Build the plugin; returns the output path."""
    out_dir = out_dir or paths.default_output_dir()
    os.makedirs(out_dir, exist_ok=True)
    with _lock:
        ws = workspace_dir()
        os.makedirs(ws, exist_ok=True)
        tpl = paths.templates_dir()
        sdk = paths.ffgl_sdk_dir().replace("\\", "/")
        for fn in ("Plugin.cpp", "FFMakerPlugin.h", "Plugin.def"):
            with open(os.path.join(tpl, "ffgl", fn), encoding="utf-8") as f:
                _write_if_changed(os.path.join(ws, fn), f.read())
        with open(os.path.join(tpl, "ffgl", "CMakeLists.txt"), encoding="utf-8") as f:
            cm = f.read().replace("@FFGL_SDK_DIR@", sdk)
        cm_changed = _write_if_changed(os.path.join(ws, "CMakeLists.txt"), cm)
        _write_if_changed(os.path.join(ws, "ShaderData.h"),
                          emit_ffgl.shader_data_header(ir, glsl_list, plugin_name))

        bdir = os.path.join(ws, "build")
        if cm_changed or not os.path.exists(os.path.join(bdir, "CMakeCache.txt")):
            log("Configuring build workspace (first build takes a minute)…")
            cmd = ["cmake", "-S", ws, "-B", bdir]
            glew = _glew_root(log)
            if glew:
                cmd += [f"-DGLEW_ROOT={glew}", "-A", "x64"]
            if sys.platform == "darwin":
                cmd += ["-G", "Xcode"] if shutil.which("xcodebuild") else []
            _run(cmd, ws, log, cancel_event)
        # MSBuild's header tracking misses ShaderData.h changes, so force the
        # plugin translation unit to recompile (the SDK stays cached).
        import glob
        for obj in glob.glob(os.path.join(bdir, "**", "Plugin.obj"), recursive=True) + \
                glob.glob(os.path.join(bdir, "**", "Plugin.cpp.o"), recursive=True):
            os.remove(obj)
        product = os.path.join(bdir, "Release", "FFMakerPlugin.dll")
        before = os.path.getmtime(product) if os.path.exists(product) else None
        log("Compiling plugin…")
        _run(["cmake", "--build", bdir, "--config", "Release", "--target", "FFMakerPlugin"], ws, log, cancel_event)
        if sys.platform == "win32" and before is not None and os.path.getmtime(product) == before:
            raise BuildError("Build reported success but the plugin binary was not updated.")

        if sys.platform == "win32":
            src = product
            dst = os.path.join(out_dir, safe_name(plugin_name) + ".dll")
            shutil.copy2(src, dst)
        else:
            src = os.path.join(bdir, "Release", "FFMakerPlugin.bundle")
            if not os.path.isdir(src):
                src = os.path.join(bdir, "FFMakerPlugin.bundle")
            dst = os.path.join(out_dir, safe_name(plugin_name) + ".bundle")
            if os.path.exists(dst):
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
        return dst
