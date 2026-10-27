"""Write THIRD_PARTY_NOTICES.txt: the terms NDI's licence asks users to agree
to, and the licences of the third-party software that FFStudio's packaged app
(FFStudio.exe or FFStudio.app) contains, as their licences require when the
app is distributed.

Usage: venv\\Scripts\\python tools\\make_notices.py [OUT_DIR]   (default: dist)
compile.py runs it after each build. It covers what this platform's build
bundles: a package is listed when PyInstaller's record of the last build
(build/FFStudio/PYZ-00.toc) contains it, so run it after compile.py.

Licence texts come from the installed packages, from Python's own LICENSE.txt
and Tcl's license.terms, from the repository (FFGL SDK, GLEW) and, for parts
whose packages don't carry their licence, from tools/licenses (copied from
each project's repository; the URLs are below)."""
import fnmatch
import glob
import os
import sys
import tkinter
from importlib import metadata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from ffstudio import __version__                                     # noqa: E402

LICENSES = os.path.join(ROOT, "tools", "licenses")
WIN, MAC = sys.platform == "win32", sys.platform == "darwin"

# (title, what it's used for, distribution or None, module to look for in the
# build, files: "dist:<pattern>" in the package's installed files, "lic:<name>"
# in tools/licenses, "repo:<path>"; the platforms it's on)
COMPONENTS = [
    ("customtkinter", "user interface", "customtkinter", "customtkinter", ["dist:LICENSE"], "all"),
    ("darkdetect", "user interface (used by customtkinter)", "darkdetect", "darkdetect", ["dist:LICENSE"], "all"),
    ("tkinterdnd2", "drag and drop", "tkinterdnd2", "tkinterdnd2", ["dist:LICENSE"], "all"),
    ("tkdnd", "drag and drop (inside tkinterdnd2)", None, "tkinterdnd2", ["lic:tkdnd.txt"], "all"),
    ("Pillow", "images", "pillow", "PIL", ["dist:LICENSE"], "all"),
    ("PyOpenGL", "OpenGL", "PyOpenGL", "OpenGL", ["lic:pyopengl.txt"], "all"),
    ("pyGLFW", "windows for the preview and the output", "glfw", "glfw", ["dist:LICENSE.txt"], "all"),
    ("GLFW", "windows for the preview and the output (inside pyGLFW)", None, "glfw", ["lic:glfw.txt"], "all"),
    ("NumPy", "frame buffers for NDI", "numpy", "numpy", ["dist:LICENSE.txt"], "all"),
    ("cyndilib", "NDI output", "cyndilib", "cyndilib", ["dist:LICENSE"], "all"),
    ("NDI® runtime", "NDI output (inside cyndilib)", "cyndilib", "cyndilib", ["dist:*icenses*.txt"], "all"),
    ("pugixml-cython", "NDI metadata (used by cyndilib)", "pugixml-cython", "pugixml_cython",
     ["dist:LICENSE", "dist:LICENSE-pugixml"], "all"),
    ("python-osc", "OSC remote control", "python-osc", "pythonosc", ["lic:python-osc.txt"], "all"),
    ("packaging", "used by the libraries above", "packaging", "packaging",
     ["dist:LICENSE", "dist:LICENSE.APACHE", "dist:LICENSE.BSD"], "all"),
    ("typing_extensions", "used by the libraries above", "typing_extensions", "typing_extensions",
     ["dist:LICENSE"], "all"),
    ("SpoutGL", "Spout output", "SpoutGL", "SpoutGL", ["dist:LICENSE"], "win"),
    ("Spout", "Spout output (inside SpoutGL)", None, "SpoutGL", ["lic:spout.txt"], "win"),
    ("syphon-python", "Syphon output", "syphon-python", "syphon", ["dist:LICENSE*"], "mac"),
    ("Syphon framework", "Syphon output (inside syphon-python)", None, "syphon", ["lic:syphon.txt"], "mac"),
    ("FFGL SDK", "the plugins FFStudio builds", None, None, ["repo:boilerplates/ffgl/LICENSE.md"], "all"),
    ("GLEW", "the plugins FFStudio builds (Windows)", None, None, ["repo:deps/glew-2.2.0/LICENSE.txt"], "win"),
]

# Where tools/licenses came from (each project's repository).
SOURCES = {
    "tkdnd.txt": "https://github.com/petasis/tkdnd/blob/master/license.terms",
    "pyopengl.txt": "https://github.com/mcfletch/pyopengl/blob/master/license.txt",
    "glfw.txt": "https://github.com/glfw/glfw/blob/master/LICENSE.md",
    "python-osc.txt": "https://github.com/attwad/python-osc/blob/main/LICENSE.txt",
    "spout.txt": "https://github.com/leadedge/Spout2/blob/master/LICENSE",
    "syphon.txt": "https://github.com/Syphon/Syphon-Framework/blob/master/License.txt",
}

# The terms the NDI SDK licence (paragraph 3d) requires users to agree to when
# a product that includes NDI is distributed.
NDI_TERMS = """\
NDI
---

FFStudio includes the NDI® runtime, which belongs to Vizrt NDI AB. NDI's
licence asks everyone who gets it to agree to the following. These terms
apply to the NDI software inside FFStudio only:

  - Don't modify the NDI software.
  - Don't reverse engineer, disassemble or recompile it, or the protocols it
    uses, and don't try to.
  - Don't get around any of its technical limits.
  - Don't remove or change any of its copyright or other notices.
  - NDI and its licensors give no warranty, and as far as the law allows,
    they aren't liable for any damage from using FFStudio.
  - Follow United States export law: don't export FFStudio, or any part of
    it, in a way that breaks it.
  - If you use FFStudio to make your own products that use NDI, follow the
    NDI SDK licence: keep them fully NDI-compatible, and include these NDI
    terms in your own licence.

The NDI runtime is copyright (c) 2023-2026 Vizrt NDI AB. All rights reserved.
NDI® is a registered trademark of Vizrt NDI AB. FFStudio isn't made or
endorsed by Vizrt NDI AB. More about NDI: https://ndi.video/

The NDI SDK licence: https://ndi.link/ndisdk_license""".split("\n")


def read(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read().replace("\r\n", "\n").strip("\n")


def in_build(module):
    """Whether the last build bundles `module` (True when there's no record)."""
    toc = os.path.join(ROOT, "build", "FFStudio", "PYZ-00.toc")
    if module is None or not os.path.isfile(toc):
        return True
    with open(toc, encoding="utf-8", errors="replace") as f:
        text = f.read()
    return f"('{module}'" in text or f"('{module}." in text


def in_installed(dist):
    try:
        metadata.distribution(dist)
        return True
    except metadata.PackageNotFoundError:
        return False


def dist_files(dist, pattern):
    d = metadata.distribution(dist)
    return sorted(str(f.locate()) for f in (d.files or [])
                  if fnmatch.fnmatch(os.path.basename(str(f)), pattern))


def texts(files, dist):
    out = []
    for spec in files:
        kind, _, name = spec.partition(":")
        if kind == "dist":
            paths = dist_files(dist, name)
        elif kind == "lic":
            paths = [os.path.join(LICENSES, name)]
        else:
            paths = [os.path.join(ROOT, name)]
        paths = [p for p in paths if os.path.isfile(p)]
        if not paths:
            raise SystemExit(f"make_notices: no licence file for {spec} ({dist or ''})")
        out += [t for t in map(read, paths) if t not in out]      # e.g. one file in two places
    return out


def python_and_tcl():
    """Python's licence (on Windows it also covers the OpenSSL, libffi, bzip2,
    xz, zlib and Tcl/Tk builds that come with it) and Tcl/Tk's."""
    out = []
    for p in (os.path.join(sys.base_prefix, "LICENSE.txt"),
              os.path.join(sys.base_prefix, "lib", f"python{sys.version_info[0]}.{sys.version_info[1]}",
                           "LICENSE.txt")):
        if os.path.isfile(p):
            out.append((f"Python {sys.version.split()[0]}", "the app's runtime", [read(p)]))
            break
    else:
        raise SystemExit("make_notices: Python's LICENSE.txt not found")
    # Tcl/Tk's own terms, where its installation has them (Homebrew's does;
    # python.org's Windows build has them only inside its LICENSE.txt, above).
    tcl_lib = tkinter.Tcl().eval("info library")
    terms = []
    for d in [tcl_lib] + sorted(glob.glob(os.path.join(os.path.dirname(tcl_lib), "tk*"))):
        p = os.path.join(d, "license.terms")
        if os.path.isfile(p) and read(p) not in terms:
            terms.append(read(p))
    if terms:
        out.append(("Tcl/Tk", "the user interface's toolkit", terms))
    elif "Tcl/Tk" not in out[0][2][0]:
        raise SystemExit("make_notices: Tcl/Tk's license.terms not found")
    return out


def main(out_dir):
    platform = "win" if WIN else "mac" if MAC else "other"
    sections = python_and_tcl()
    for title, use, dist, module, files, where in COMPONENTS:
        if where not in ("all", platform) or not in_build(module):
            continue
        if dist and not title.startswith("NDI"):     # the NDI runtime's isn't cyndilib's
            try:
                title = f"{title} {metadata.version(dist)}"
            except metadata.PackageNotFoundError:
                continue
        elif dist and not in_installed(dist):
            continue
        sections.append((title, use, texts(files, dist)))

    rule = "=" * 78
    head = [
        f"FFStudio {__version__}: third-party notices",
        "",
        "FFStudio's own code is under the MIT License (LICENSE.txt). FFStudio also",
        "contains the software by others listed below, each used under the licence",
        "that follows its name. These notices are included as those licences require.",
        "",
    ] + NDI_TERMS + [
        "",
        "Contents:",
    ] + [f"  - {t}: {u}" for t, u, _ in sections]
    body = []
    for title, use, parts in sections:
        body += ["", rule, f"{title}: {use}", rule, ""]
        body += ("\n\n" + "-" * 40 + "\n\n").join(parts).split("\n")
    tail = ["", rule, "Sources of the texts not shipped with their packages:", ""]
    tail += [f"  {k}: {v}" for k, v in SOURCES.items()]
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "THIRD_PARTY_NOTICES.txt")
    with open(path, "w", encoding="utf-8") as f:     # the platform's line endings
        f.write("\n".join(head + body + tail) + "\n")
    print(f"wrote {path} ({len(sections)} components)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "dist"))
