# FFMaker User Manual

**FFMaker** converts GLSL shaders into:
- **FFGL 2 plugins** for Resolume 7.21.3+ and other FFGL hosts (`.dll` on Windows; macOS `.bundle` support is planned)
- **ISF 2 files** (`.fs`) for MadMapper, VDMX, Millumin and other ISF hosts

It accepts ISF, Shadertoy, GLSL Sandbox and plain GLSL fragment shaders.

---

## Prerequisites (Windows)

- **Python 3.10+** with the packages in `requirements.txt`: `venv\Scripts\pip install -r requirements.txt`
- **CMake** on your PATH
- **Visual Studio 2022+ or the Build Tools**, with the "Desktop development with C++" workload
- An OpenGL 4.1 GPU. FFMaker compiles and test-renders every shader on your GPU before building it.

The first plugin build sets up a build workspace in `%LOCALAPPDATA%\FFMaker` and compiles the FFGL SDK. This takes about a minute. After that, each plugin builds in about 2 seconds.

---

## Quick start

**GUI:** `venv\Scripts\python src\main_gui.py`

1. Drop shader files or folders onto the **Queue**.
2. Click **Build Queue** to make FFGL plugins, or **Export ISF** to make `.fs` files.
3. Plugins are written to `FFMaker\output\`. Copy them to Resolume's FFGL plugin folder (set in *Preferences → Video → FFGL plugins*), then restart Resolume.

**Command line:**

```
venv\Scripts\python -m ffmaker <files or folders> --to ffgl|isf|both|check [--out DIR] [--no-params] [--test]
```

- `--to check` validates shaders without building anything.
- `--test` loads each finished plugin in FFMaker's built-in test host and renders a few frames.

---

## Supported inputs

| Format | Detected by | Becomes |
| :-- | :-- | :-- |
| **ISF** (`.fs`) | `/*{ JSON }*/` header | Source, Effect (1 image input), or Mixer (Transition category with 2 images) |
| **Shadertoy** | `mainImage()` | Source; or Effect if it reads `iChannel0` |
| **GLSL Sandbox / plain GLSL** | `main()` | Source (or Effect if it declares a `sampler2D` uniform) |

Supported features:
- **ISF:** all input types except audio. Multi-pass and persistent buffers (`PASSES`, `PERSISTENT`, `FLOAT`, `WIDTH`/`HEIGHT` expressions) are supported. So are all `IMG_*` macros, `DATE`, `FRAMEINDEX` and `TIMEDELTA`.
- **Shadertoy:** `iTime`, `iResolution`, `iMouse`, `iDate`, `iFrame`, `iTimeDelta`, `iChannel0-3` (fed from the clip input), and `iChannelResolution`.
- **GLSL Sandbox:** `time`, `resolution`, `mouse` and `surfacePosition`. Unknown `uniform`s become sliders.
- **Older GLSL:** `texture2D`, `gl_FragColor` and similar legacy names are translated automatically.

**Not yet supported** (see `IMPROVEMENT_PLAN.md`):
- ISF `IMPORTED` images: they read black for now.
- Audio inputs.
- Shadertoy multi-buffer projects (Buffer A–D).
- ISF custom vertex shaders.

---

## Parameters

### ISF inputs
These become native FFGL parameters:

| ISF input | FFGL parameter |
| :-- | :-- |
| `float` | Slider with the real MIN/MAX range |
| `long` | Dropdown with the ISF labels |
| `bool` | Toggle |
| `event` | Trigger button |
| `color` | Color picker |
| `point2D` | X and Y sliders |

### Shadertoy / GLSL constants
With **Extract User Parameters** on, top-level `const float/bool/vec3` values and `#define NAME 1.5` lines become sliders, toggles or color pickers:
- Math constants (PI, TAU, epsilons…) are skipped.
- Constants that must stay constant (array sizes, `case` labels) are skipped.
- If turning a constant into a slider would break compilation, FFMaker puts it back as a constant and tells you.

### Built-in controls
- **Speed** is added to every animated shader and scales time smoothly; changing it never makes the animation jump. If the shader already has its own "speed" control, FFMaker's is called **Time Scale** instead.
- **Mouse X/Y** and **Mouse Click** are added when a shader uses the mouse.

### Alpha
Shadertoy and GLSL Sandbox ignore output alpha, so FFMaker makes those plugins opaque. ISF shaders keep their alpha.

---

## Troubleshooting

- **"Shader does not compile"**: the log lists the errors with line numbers from *your* file.
- **Build failed**: check that CMake and Visual Studio's C++ tools are installed. The log shows the compiler's error lines.
- **Plugin missing in Resolume**: make sure the `.dll` is in a folder Resolume scans, then restart Resolume. FFGL shows only the first 16 characters of a plugin name. FFMaker keeps those 16 characters unique within one batch.

---

## Shader licensing

Shaders are the creative property of their authors.
- Shadertoy code defaults to **CC BY-NC-SA 3.0** unless the code says otherwise.
- ISF and GLSL Sandbox shaders vary.

Keep credits, and respect non-commercial and share-alike terms.
