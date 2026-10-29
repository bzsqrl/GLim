# GLim

GLim turns GLSL shaders (ISF, Shadertoy, GLSL Sandbox) into **FFGL 2 plugins** for Resolume 7.21.3+ and **ISF files** for MadMapper and other ISF hosts. It previews them live, gives every parameter a slider, and can send its output over Spout, Syphon or NDI, under OSC remote control.

**Download:** the Windows and macOS (Apple Silicon) builds are on the [Releases](https://github.com/bzsqrl/GLim/releases) page. Each zip includes the user manual, 18 shaders to start with and the TouchOSC layouts. [USER_MANUAL.md](USER_MANUAL.md) covers installing and using GLim.

The rest of this page is about running GLim from source.

## Running from source

### Windows

Needs Python 3.10 (the version GLim is built and tested with). To build plugins you also need CMake and Visual Studio's C++ tools (the free Build Tools are enough).

```
python -m venv venv
venv\Scripts\pip install -r requirements.txt
venv\Scripts\python src\main_gui.py
```

GLEW is downloaded on the first plugin build.

### macOS

Needs an Apple Silicon Mac with macOS 14 or later, plus Homebrew's Python 3.12 with Tk.

```
xcode-select --install                          # Apple's compilers
brew install python@3.12 python-tk@3.12 cmake   # Homebrew: https://brew.sh
/opt/homebrew/bin/python3.12 -m venv venv
venv/bin/pip install -r requirements.txt
venv/bin/python src/main_gui.py
```

### Command line

`python -m glim <files or folders> --to ffgl|isf|both|check [--out folder]` converts without the GUI. `python -m glim --help` lists the options.

### Tests

```
venv/bin/python tests/run_corpus.py --isf                          # tests/corpus: 40 shaders
venv/bin/python tests/run_corpus.py --dir tests/fixtures --isf     # feature fixtures
venv/bin/python tests/run_corpus.py --dir original-shaders --isf   # the shaders that ship with GLim
```

Each shader is converted, compiled and rendered on this computer's GPU (use `venv\Scripts\python` on Windows). The expected results are OK=38 and STATIC=2 for the corpus (`glim_wipeTransition` and `glim_twoPassBloom` don't change over time), OK=6 and STATIC=6 for the fixtures, and OK=18 for `original-shaders`. [tests/corpus/README.md](tests/corpus/README.md) lists where each test shader comes from.

### Packaging

`pip install pyinstaller`, then `python compile.py` builds `dist/GLim.exe` or `dist/GLim.app` and copies the rest of the package next to it. `GLim.exe --selftest <shader> <folder>` (on macOS, `GLim.app/Contents/MacOS/GLim --selftest …`) runs a headless check and writes `selftest.log`.

## Layout

| Path | What |
| :-- | :-- |
| `glim/` | Core library: conversion, GLSL and ISF emitters, GPU validation and preview, plugin builder, command line |
| `src/` | The GUI (`main_gui.py`, `editor_panel.py`) and OSC remote control (`osc_remote.py`) |
| `templates/ffgl/` | The C++ FFGL plugin runtime, driven by a generated `ShaderData.h` |
| `boilerplates/ffgl/` | The Resolume FFGL SDK, vendored (BSD license, see its `LICENSE.md`) |
| `original-shaders/` | The shaders that ship with GLim (CC0) |
| `touchosc/` | TouchOSC layouts for remote control, made by `tools/build_touchosc.py` |
| `tools/` | Generators for the TouchOSC layouts, `THIRD_PARTY_NOTICES.txt` (license texts in `tools/licenses/`) and `USER_MANUAL.html` |
| `assets/icon/` | The app icon; regenerate it with `python assets/icon/make_icon.py` |
| `assets/social-preview.png` | GitHub's social preview and the website's link preview (`docs/img/og.jpg`), made by `tools/make_social_preview.py` |
| `tests/` | The test runner, test shaders (`corpus/`) and feature fixtures |
| `docs/` | The website, [glim.sqrl.biz](https://glim.sqrl.biz), served by GitHub Pages. `python tools/build_manual.py docs` refreshes its copy of the manual, and `python tools/render_stills.py` its shader stills. |

Drag and drop in the GUI uses `tkdnd`, which comes with the `tkinterdnd2` package. Without it, use the **+** and **📁** buttons.

## License

GLim is released under the [MIT license](LICENSE.txt). The shaders in `original-shaders/` and the test shaders written for GLim are public domain (CC0). GLim includes the NDI® SDK runtime: its terms are at the top of `THIRD_PARTY_NOTICES.txt`, which `compile.py` writes into `dist/`. NDI® is a registered trademark of Vizrt NDI AB.

Questions, problems and suggestions: please [open an issue](https://github.com/bzsqrl/GLim/issues).
