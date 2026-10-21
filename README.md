# FFMaker

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
| `tests/` | Regression runner (`run_corpus.py`) and feature fixtures |
| `sample-shaders/` | Test corpus |
| `FFMaker-Mac/` | Old, separate Mac port; to be retired once the main code runs on macOS |

## Windows setup

```
python -m venv venv
venv\Scripts\pip install -r requirements.txt
venv\Scripts\python src\main_gui.py
```

Building plugins needs CMake and Visual Studio's C++ tools. GLEW is downloaded on the first build if `deps/` is missing.

## macOS setup (for the Mac port)

```
xcode-select --install                 # Apple compilers
brew install python@3.12 cmake         # Homebrew: https://brew.sh
git clone <this repo> FFMaker && cd FFMaker
python3 -m venv venv
venv/bin/pip install -r requirements.txt
venv/bin/python tests/run_corpus.py    # converts, compiles and renders every sample on this Mac's GPU
venv/bin/python src/main_gui.py
```

Drag-and-drop in the GUI also needs `tkdnd`. Without it, the GUI falls back to the Add Files / Add Folder buttons.
