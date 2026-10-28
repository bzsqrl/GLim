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
    """GLEW at a path that stays the same between runs, and between the packaged
    app and running from source: CMake caches it. The copy bundled in a packaged
    app unpacks to a new temp folder each launch, so whichever copy is found is
    copied to the cache once (as _stable_sdk_dir does for the SDK)."""
    if sys.platform != "win32":
        return None
    base = os.path.join(paths.cache_dir(), "deps")
    stable = os.path.join(base, "glew-2.2.0")
    if os.path.isdir(stable):
        return stable
    os.makedirs(base, exist_ok=True)
    for d in (paths.app_dir(), paths.bundle_dir()):
        src = os.path.join(d, "deps", "glew-2.2.0")
        if os.path.isdir(src):
            shutil.copytree(src, stable)
            return stable
    log("Downloading GLEW (first build only)…")
    import urllib.request
    import zipfile
    zpath = os.path.join(base, "glew.zip")
    urllib.request.urlretrieve(GLEW_URL, zpath)
    with zipfile.ZipFile(zpath) as zf:
        zf.extractall(base)
    os.remove(zpath)
    return os.path.join(base, "glew-2.2.0")


# What to install, for a computer without the build tools (e.g. a copy of
# GLim.exe on another PC): the compiler can't be bundled with the app.
MSVC_HELP = ("No C++ compiler found. Building plugins needs Microsoft's C++ compiler: install the free "
             "Build Tools for Visual Studio from https://visualstudio.microsoft.com/visual-cpp-build-tools/ "
             "and tick the \"Desktop development with C++\" workload (it includes CMake), "
             "then restart GLim. (Export ISF works without it.)")
CMAKE_HELP = {
    "win32": ("CMake not found. Building plugins needs CMake: install it from https://cmake.org/download/ "
              "(Windows x64 Installer, with \"Add CMake to the PATH\"), or add \"C++ CMake tools for "
              "Windows\" in the Visual Studio Installer, then restart GLim."),
    "darwin": "CMake not found (install it with: brew install cmake).",
}
_vs_found = []                      # Visual Studio installs with the C++ compiler, once found


def _vs_installs():
    """Visual Studio / Build Tools installations that have the C++ compiler
    (Windows), from vswhere, which every Visual Studio 2017+ installs."""
    if _vs_found or sys.platform != "win32":
        return _vs_found
    vswhere = os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                           "Microsoft Visual Studio", "Installer", "vswhere.exe")
    if not os.path.isfile(vswhere):
        return []
    try:
        out = subprocess.run([vswhere, "-products", "*", "-requires",
                              "Microsoft.VisualStudio.Component.VC.Tools.x86.x64", "-property",
                              "installationPath"], capture_output=True, text=True, timeout=15,
                             creationflags=subprocess.CREATE_NO_WINDOW).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    _vs_found.extend(l.strip() for l in out.splitlines() if l.strip())
    return _vs_found


def _tool_path():
    """PATH for build tools. Apps opened from Finder get a minimal PATH
    without Homebrew, where CMake usually lives. On Windows, CMake's default
    install folder and the CMake that ships with Visual Studio work too, when
    they aren't on the PATH."""
    dirs = os.environ.get("PATH", "").split(os.pathsep)
    if sys.platform == "darwin":
        extra = ["/opt/homebrew/bin", "/usr/local/bin", "/Applications/CMake.app/Contents/bin"]
    elif sys.platform == "win32":
        extra = [os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "CMake", "bin")]
        extra += [os.path.join(vs, "Common7", "IDE", "CommonExtensions", "Microsoft", "CMake", "CMake", "bin")
                  for vs in _vs_installs()]
    else:
        extra = []
    dirs += [d for d in extra if d not in dirs and os.path.isdir(d)]
    return os.pathsep.join(d for d in dirs if d)


def check_toolchain():
    """Raise BuildError saying what to install if plugins can't be built here."""
    if sys.platform == "win32" and not _vs_installs():
        raise BuildError(MSVC_HELP)
    if shutil.which("cmake", path=_tool_path()) is None:
        raise BuildError(CMAKE_HELP.get(sys.platform, "CMake not found."))


def _run(cmd, cwd, log, cancel_event=None):
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    path = _tool_path()
    exe = shutil.which(cmd[0], path=path)
    if exe is None:
        raise BuildError(CMAKE_HELP.get(sys.platform, f"{cmd[0]} not found") if cmd[0] == "cmake"
                         else f"{cmd[0]} not found")
    proc = subprocess.Popen([exe] + cmd[1:], cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace", creationflags=flags,
                            env={**os.environ, "PATH": path})
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


def _stable_sdk_dir():
    """The FFGL SDK at a path that stays the same between runs. A packaged app
    unpacks to a new temp folder each launch, which would force CMake to
    reconfigure and rebuild the SDK every session, so copy it to the cache once."""
    src = paths.ffgl_sdk_dir()
    if not getattr(sys, "frozen", False):
        return src
    dst = os.path.join(paths.cache_dir(), "ffgl_sdk")
    stamp = os.path.join(dst, ".glim_stamp")
    marker = str(os.path.getsize(os.path.join(src, "CMakeLists.txt")))
    if not (os.path.isfile(stamp) and open(stamp).read() == marker):
        if os.path.exists(dst):
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        with open(stamp, "w") as f:
            f.write(marker)
    return dst


def workspace_dir():
    return os.path.join(paths.cache_dir(), "ffgl_workspace")


def _cached_glew_root(bdir):
    """The GLEW_ROOT the workspace was configured with, or None."""
    try:
        with open(os.path.join(bdir, "CMakeCache.txt"), encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.startswith("GLEW_ROOT:"):
                    return line.split("=", 1)[1].strip()
    except OSError:
        pass
    return None


def build(ir, glsl_list, plugin_name, out_dir=None, log=print, cancel_event=None):
    """Build the plugin; returns the output path."""
    # Absolute, because later steps run tools from other working directories.
    out_dir = os.path.abspath(out_dir or paths.default_output_dir())
    os.makedirs(out_dir, exist_ok=True)
    with _lock:
        ws = workspace_dir()
        os.makedirs(ws, exist_ok=True)
        tpl = paths.templates_dir()
        sdk = _stable_sdk_dir().replace("\\", "/")
        for fn in sorted(os.listdir(os.path.join(tpl, "ffgl"))):
            if fn == "CMakeLists.txt":
                continue
            with open(os.path.join(tpl, "ffgl", fn), encoding="utf-8") as f:
                _write_if_changed(os.path.join(ws, fn), f.read())
        with open(os.path.join(tpl, "ffgl", "CMakeLists.txt"), encoding="utf-8") as f:
            cm = f.read().replace("@FFGL_SDK_DIR@", sdk)
        cm_changed = _write_if_changed(os.path.join(ws, "CMakeLists.txt"), cm)
        _write_if_changed(os.path.join(ws, "ShaderData.h"),
                          emit_ffgl.shader_data_header(ir, glsl_list, plugin_name))

        bdir = os.path.join(ws, "build")
        glew = _glew_root(log)
        cached = _cached_glew_root(bdir)
        if glew and cached and os.path.normcase(os.path.normpath(cached)) != os.path.normcase(os.path.normpath(glew)):
            # Configured against a GLEW that's gone or moved (e.g. a packaged app's
            # temp folder): CMake keeps the old include path, so start afresh.
            log("GLEW moved: reconfiguring the build workspace…")
            shutil.rmtree(bdir)
        if cm_changed or not os.path.exists(os.path.join(bdir, "CMakeCache.txt")):
            check_toolchain()               # a clear message on a computer without the tools
            log("Configuring build workspace (first build takes a minute)…")
            cmd = ["cmake", "-S", ws, "-B", bdir]
            if glew:
                cmd += [f"-DGLEW_ROOT={glew}", "-A", "x64"]
            if sys.platform == "darwin":
                # Makefiles work with just the Command Line Tools; the Xcode
                # generator would need the full Xcode app.
                cmd += ["-G", "Unix Makefiles", "-DCMAKE_BUILD_TYPE=Release"]
            _run(cmd, ws, log, cancel_event)
        # MSBuild's header tracking misses ShaderData.h changes, so force the
        # plugin translation unit to recompile (the SDK stays cached).
        import glob
        for obj in glob.glob(os.path.join(bdir, "**", "Plugin.obj"), recursive=True) + \
                glob.glob(os.path.join(bdir, "**", "Plugin.cpp.o"), recursive=True):
            os.remove(obj)
        product = os.path.join(bdir, "Release", "GLimPlugin.dll")
        before = os.path.getmtime(product) if os.path.exists(product) else None
        log("Compiling plugin…")
        _run(["cmake", "--build", bdir, "--config", "Release", "--target", "GLimPlugin"], ws, log, cancel_event)
        if sys.platform == "win32" and before is not None and os.path.getmtime(product) == before:
            raise BuildError("Build reported success but the plugin binary was not updated.")

        if sys.platform == "win32":
            src = product
            dst = os.path.join(out_dir, safe_name(plugin_name) + ".dll")
            shutil.copy2(src, dst)
        else:
            src = os.path.join(bdir, "Release", "GLimPlugin.bundle")
            if not os.path.isdir(src):
                src = os.path.join(bdir, "GLimPlugin.bundle")
            dst = os.path.join(out_dir, safe_name(plugin_name) + ".bundle")
            if os.path.exists(dst):
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
            _set_bundle_identity(dst, plugin_name, log, cancel_event)
        return dst


def _set_bundle_identity(bundle, plugin_name, log, cancel_event):
    """Every build copies the same GLimPlugin.bundle, so give each copy its
    own identifier and name (macOS caches bundles by identifier), then re-sign
    ad hoc because editing Info.plist breaks the linker's signature.

    Resolume ignores CFBundleExecutable and opens Contents/MacOS/<bundle name>,
    so the binary is renamed to match the bundle."""
    plist = os.path.join(bundle, "Contents", "Info.plist")
    exe = os.path.splitext(os.path.basename(bundle))[0]
    macos = os.path.join(bundle, "Contents", "MacOS")
    os.rename(os.path.join(macos, "GLimPlugin"), os.path.join(macos, exe))
    ident = "com.busysquirrel.glim.plugin." + safe_name(plugin_name) + "." + emit_ffgl.plugin_id(plugin_name)
    for key, value in (("CFBundleIdentifier", ident), ("CFBundleName", plugin_name[:15]),
                       ("CFBundleExecutable", exe), ("CFBundlePackageType", "BNDL")):
        _run(["plutil", "-replace", key, "-string", value, plist], bundle, log, cancel_event)
    _run(["codesign", "--force", "--sign", "-", bundle], bundle, log, cancel_event)
