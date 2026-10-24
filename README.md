# FFStudio

Converts GLSL shaders (ISF, Shadertoy, GLSL Sandbox) into **FFGL 2 plugins** for Resolume 7.21.3+ and **ISF files** for MadMapper and other ISF hosts.

- `USER_MANUAL.md`: how to use it
- `IMPROVEMENT_PLAN.md`: architecture, status and roadmap
- `TESTING_CHECKLIST.md`: what to check when testing builds in the VJ hosts

## Layout

| Path | What |
| :-- | :-- |
| `ffmaker/` | Core library: conversion, GLSL/ISF emitters, GPU validation and preview, plugin builder, CLI (`python -m ffmaker`) |
| `templates/ffgl/` | The fixed C++ FFGL plugin runtime, driven by a generated `ShaderData.h` |
| `boilerplates/ffgl/` | Vendored Resolume FFGL SDK (BSD-style license, see its `LICENSE.md`) |
| `src/` | GUI (`main_gui.py`, `editor_panel.py`) |
| `assets/icon/` | App icon: `FFStudio.ico` (Windows), `FFStudio.icns` (macOS), `FFStudio.png` (1024 px logo), window icons in `png/`. Regenerate with `python assets/icon/make_icon.py`. |
| `tests/` | Regression runner (`run_corpus.py`) and feature fixtures |
| `sample-shaders/` | Test corpus |

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
git clone <this repo> FFMaker && cd FFMaker
python3 -m venv venv
venv/bin/pip install -r requirements.txt
venv/bin/python tests/run_corpus.py    # converts, compiles and renders every sample on this Mac's GPU
venv/bin/python src/main_gui.py
```

To build the packaged app: `venv/bin/python compile.py` (writes `dist/FFStudio.app`).

Updating an existing Mac checkout after the Windows work (queue rewrite, slider fix): see [MAC_UPDATE.md](MAC_UPDATE.md).

Drag-and-drop in the GUI uses `tkdnd`, which the `tkinterdnd2` package includes for macOS and Windows. Without it, the GUI falls back to the + (add files) / 📁 (add folder) buttons.
