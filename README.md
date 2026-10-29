# GLim

Converts GLSL shaders (ISF, Shadertoy, GLSL Sandbox) into **FFGL 2 plugins** for Resolume 7.21.3+ and **ISF files** for MadMapper and other ISF hosts.

- `USER_MANUAL.md`: how to use it (`compile.py` also writes it as `dist/USER_MANUAL.html` for the package)
- `LICENSE.txt`: GLim's licence (MIT), shipped with the app; the NDI terms are at the top of the generated `THIRD_PARTY_NOTICES.txt` (`tools/make_notices.py`)
- `IMPROVEMENT_PLAN.md`: architecture, status and roadmap
- `TESTING_CHECKLIST.md`: what to check when testing builds in the VJ hosts

## Layout

| Path | What |
| :-- | :-- |
| `glim/` | Core library: conversion, GLSL/ISF emitters, GPU validation and preview, plugin builder, CLI (`python -m glim`) |
| `templates/ffgl/` | The fixed C++ FFGL plugin runtime, driven by a generated `ShaderData.h` |
| `boilerplates/ffgl/` | Vendored Resolume FFGL SDK (BSD-style license, see its `LICENSE.md`) |
| `src/` | GUI (`main_gui.py`, `editor_panel.py`); `osc_remote.py`: OSC remote control of the Studio tab |
| `touchosc/` | TouchOSC layouts for the remote control (desktop and phone), made by `tools/build_touchosc.py` |
| `tools/` | `build_touchosc.py` (the layouts), `make_notices.py` (`THIRD_PARTY_NOTICES.txt`, with the licence texts in `tools/licenses/`), `build_manual.py` (`USER_MANUAL.html`); `compile.py` runs the last two |
| `assets/icon/` | App icon: `GLim.ico` (Windows), `GLim.icns` (macOS), `GLim.png` (1024 px logo), window icons in `png/`. Regenerate with `python assets/icon/make_icon.py`. |
| `tests/` | Regression runner (`run_corpus.py`), its test shaders (`corpus/`: CC0 Shadertoy shaders, each with its link and author, plus shaders written for GLim) and feature fixtures |
| `original-shaders/` | GLim's own ISF shaders, public domain (CC0, credited "GLim - License: CC0"), shipped in the package; check them with `tests/run_corpus.py --dir original-shaders` |

## Windows setup

```
python -m venv venv
venv\Scripts\pip install -r requirements.txt
venv\Scripts\python src\main_gui.py
```

Building plugins needs CMake and Visual Studio's C++ tools. GLEW is downloaded on the first build if `deps/` is missing.

Updating an existing Windows checkout after the Mac port: see [WINDOWS_UPDATE.md](WINDOWS_UPDATE.md).

## macOS setup (for the Mac port)

```
xcode-select --install                 # Apple compilers
brew install python@3.12 python-tk@3.12 cmake   # Homebrew: https://brew.sh
git clone https://github.com/bzsqrl/GLim.git && cd GLim
python3 -m venv venv
venv/bin/pip install -r requirements.txt
venv/bin/python tests/run_corpus.py    # converts, compiles and renders every sample on this Mac's GPU
venv/bin/python src/main_gui.py
```

To build the packaged app: `venv/bin/python compile.py` (writes `dist/GLim.app`).

Updating an existing Mac checkout after the Windows work (queue rewrite, slider fix): see [MAC_UPDATE.md](MAC_UPDATE.md).

Drag-and-drop in the GUI uses `tkdnd`, which the `tkinterdnd2` package includes for macOS and Windows. Without it, the GUI falls back to the + (add files) / 📁 (add folder) buttons.
