# FFStudio User Manual

**FFStudio** (formerly FFMaker) converts GLSL shaders into:
- **FFGL 2 plugins** for Resolume 7.21.3+ and other FFGL hosts (`.dll` on Windows, universal `.bundle` on macOS)
- **ISF 2 files** (`.fs`) for MadMapper, VDMX, Millumin and other ISF hosts

It accepts ISF, Shadertoy, GLSL Sandbox and plain GLSL fragment shaders.

---

## Prerequisites (Windows)

- **Python 3.10+** with the packages in `requirements.txt`: `venv\Scripts\pip install -r requirements.txt`
- **CMake**: on your PATH, in its default folder (`C:\Program Files\CMake`), or the one that comes with Visual Studio
- **Visual Studio 2022+ or the Build Tools**, with the "Desktop development with C++" workload
- An OpenGL 4.1 GPU. FFStudio compiles and test-renders every shader on your GPU before building it.

**Using `FFStudio.exe` on another computer:** copy it anywhere writable (not `Program Files`: plugins go to an `output` folder next to it). It needs no Python. Everything except **Build FFGL** works as it is: preview, the output window, Spout and **Export ISF** need only an OpenGL 4.1 graphics driver (not a virtual machine or Remote Desktop). **Build FFGL** also needs Microsoft's C++ compiler: install the free [Build Tools for Visual Studio](https://visualstudio.microsoft.com/visual-cpp-build-tools/) with the "Desktop development with C++" workload (it includes CMake). Without it, the build says what's missing and where to get it. The exe isn't code-signed, so Windows may warn on first run (*More info → Run anyway*).

## Prerequisites (macOS)

- **Python 3.12** (Homebrew `python@3.12` and `python-tk@3.12`) with the packages in `requirements.txt`: `venv/bin/pip install -r requirements.txt`
- **CMake** (`brew install cmake`)
- **Xcode Command Line Tools** (`xcode-select --install`). The full Xcode app isn't needed.

Plugins are universal `.bundle`s that run on Apple Silicon and Intel Macs (macOS 10.15+).

The first plugin build sets up a build workspace in `%LOCALAPPDATA%\FFStudio` (macOS: `~/Library/Caches/FFStudio`) and compiles the FFGL SDK. This takes about a minute. After that, each plugin builds in about 2 seconds.

---

## Quick start

**GUI:** `venv\Scripts\python src\main_gui.py` (macOS: `venv/bin/python src/main_gui.py`)

1. Drop shader files or folders onto the **Queue** (or use **+** to add files and **📁** to add a folder).
2. Click **Build FFGL** to make FFGL plugins, or **Export ISF** to make `.fs` files.
3. Plugins are written to the `output` folder next to `FFStudio.exe` (from source: the project's `output` folder). Copy them to Resolume's FFGL plugin folder (set in *Preferences → Video → FFGL plugins*; on macOS, `~/Documents/Resolume Arena/Extra Effects` works by default), then restart Resolume.

In the queue, select rows with a click (Shift/Ctrl-click for several), or press **Ctrl+A** (⌘A on macOS) to select them all. Ctrl+A works anywhere on the Queue tab; in text fields it keeps its usual meaning.
- **With rows selected**, **Reset**, **Analyze**, **Build FFGL** and **Export ISF** act on just those rows, and show how many in brackets, e.g. **Build FFGL (3)**. Selected rows are rebuilt even if they're already done. Click empty space in the list or press **Esc** to deselect; the buttons then work on the whole queue again (Build skips rows that are already done).
- **Reset** sets built and failed rows back to Pending, so **Build FFGL** converts them again (for example after changing settings) without reloading the files. **Clear Completed** removes the built rows; **Clear All** empties the queue.
- **Delete** removes the selected rows. Right-click for the same actions plus **Open in Studio**; double-clicking a row also opens it in the editor. On macOS, Control-click also opens the menu.
- **Switching to the Studio tab** (its button, or **Shift+Tab**) loads a shader from the queue and sets what ← / → and the slideshow step through: with **one row selected**, that row, stepping through the whole queue; with **several selected**, the first of them, stepping through only those; with **none selected**, the first row, stepping through the whole queue. An empty queue loads nothing. If you come back without changing the queue or its selection, Studio stays on the shader it was showing, so you can glance at the queue mid-playlist. Double-click or **Open in Studio** always loads the row.
- **Shift+Tab** switches between the Queue and Studio tabs from anywhere in the window.
- Drag the column header edges to resize columns. The **Size** column shows each shader file's size. Click the **Filename**, **Type**, **Size** or **GPU** heading to sort the queue by it (click again to reverse; Size and GPU start with the largest). The sorted order becomes the queue's order, for builds and for ← / → and the slideshow.
- **Analyze** fills the **GPU @1080p** column with each shader's GPU load (see *GPU load* below), for the selected rows or the whole queue. Press it again to stop (it reads **Stop Analysis** meanwhile; **Build FFGL** likewise reads **Cancel Build**). Sorting by GPU puts the heaviest first; ⚠ marks shaders that can't hold 60 fps at 1080p on this computer. The log names the heaviest one.

**Studio tab (editor):** open or paste a shader and click **Process Code** (or press Ctrl+Enter; ⌘+Enter on macOS). **Build FFGL (.dll)** (`.bundle` on macOS) then makes the plugin and **Export ISF (.fs)** the ISF file, as on the Queue tab. You get:
- **Live preview.** Rendered on your GPU the same way the plugin renders it.
  - **Fullscreen:** click **⛶**, double-click the preview, or press **Ctrl+F** (⌘F on macOS) to fill the monitor FFStudio is on; press **Esc**, **Ctrl+F** / ⌘F again, or double-click to return.
  - **Output window (multi-monitor):** click **⧉** (left of ⛶) to show the live render in its own window, opened on another monitor if you have one. Move and resize it like any window; FFStudio stays usable, and slider changes show up live. Double-click it or press **Ctrl+F** / ⌘F (in it, or in FFStudio) to make it fullscreen on the monitor it's on; **Esc** goes back to the window. The **⧉** button is a toggle (amber while the window is open): press it again, or use the window's close button, to close it. While the output is fullscreen the button does nothing; press Esc first.
  - **Spout / Syphon output:** **Spout** (Windows) or **Syphon** (macOS), right of ⛶, sends the shader loaded in the Studio tab to other apps on the same computer (Resolume, MadMapper, OBS, TouchDesigner, …) as a source named **FFStudio**, at 1920×1080, about 60 fps, GPU to GPU. It's off when FFStudio starts; click it to turn it on (amber) or off. It keeps sending when you switch shaders (← / →, the slideshow) or go to the Queue tab, and with or without the output window; while it's on, the output window shows the same 1920×1080 frames, scaled to fit. Turned on before a shader is loaded, it starts with the first one.
  - Both render at the window's resolution (up to 1920 wide, scaled up beyond that). The output draws on its own thread, so it keeps playing smoothly while FFStudio is busy (e.g. rebuilding the parameter list after a shader switch). While it's open, the small preview keeps running at a lower frame rate (about 10 fps) and follows shader switches; on Windows, FFStudio's own window pauses while you drag the output window.
  - **Queue playlist:** the **←** / **→** buttons under the preview (and the ← / → keys in fullscreen or the output window) load the previous / next shader in the **Queue** (or in the selected rows, if several were selected when you switched to Studio) into the Studio tab. Each starts from the beginning with its saved settings, shaders that don't compile are skipped, and the list wraps around. The label next to them shows the position in the queue (e.g. "3 / 12"), or "not in queue" when the loaded shader isn't in it.
  - **Slideshow:** **Auto** (next to the ← / → buttons) steps to the next queue shader every few seconds; type the time in the box beside it (seconds, minimum 1, Enter to apply; default 10). After the last shader it loops back to the first. The button turns amber while on, and the label counts down ("next in 4s"). Pausing the preview (⏸) holds the countdown; ← / → restart it. It keeps running in fullscreen and with the output window open, so it works as an unattended playlist on a second monitor. Press **Auto** again to stop.
  - Fullscreen and the output window always show the shader loaded in the Studio tab, so loading another shader (from the queue, Open File, or a drop) switches them too, and recompiling after a settings change updates them live. If the loaded shader doesn't compile, they keep showing the last one that did.
  - Play/pause with ⏸; restart time and feedback buffers with ⟲.
  - For effects, preview over the test pattern, or choose **Load image…** to use your own picture.
- **Channels.** For Shadertoy shaders, pick what each `iChannel` reads: the clip (`input`), `noise`, `audio`, `none`, or an image file. The **filter** and **wrap** menus next to it set how the channel is sampled (see *Sampler settings* below).
- **Parameters.** For each control you can:
  - **Untick** it to hide it. Hidden controls are compiled in as constants at their current value.
  - **Rename** it. That's the name Resolume and MadMapper show.
  - Set the **min/max** range.
  - Set the **starting value** with the slider, switch, dropdown or color picker.
  - Type a value: click the number to the right of a slider, type, and press Enter (Esc cancels). If the value is outside the min/max range, the range widens to fit.
  - Reset a slider to the shader's own default: right-click it (on macOS also Control-click).
  - Nudge a slider with the keyboard: click it (its handle turns amber), then press **←** / **→** to step it by 1/100 of its range (1 for whole numbers).
- **GPU load.** Under the preview, a bar and readout show how hard the shader works your graphics card, e.g. **29% of 60 fps** and *4.81 ms/frame · ~208 fps max · 1920×1080*.
  - It's the GPU time one frame takes, timed by the graphics card itself (so vsync, the screen and FFStudio's own work don't count), measured at 1920×1080 over about a second.
  - **Live** (amber while on) measures continuously: a new reading about every half second, so it follows slider moves and shader switches as you make them. It measures at 1920×1080 in the background (the preview itself stays small) and pauses while the preview isn't showing, e.g. on the Queue tab. It keeps the graphics card busy, so it's **off** by default: switching shaders (e.g. in a slideshow) then costs as little as possible, nothing is measured unless you press **Analyze**, and results already known (from **Analyze**, **Live**, or the queue's **Analyze**) still show. Turn it on for diagnostics or when comparing shaders. (**Analyze** is greyed out while Live is on.)
  - **% of 60 fps** is that time as a share of a 60 fps frame (16.7 ms): under 50% (green) leaves plenty of room; 50–100% (amber) is heavy; over 100% (red) means it can't run at 60 fps at 1080p on this computer, even on its own. In Resolume, layers and effects add up: two shaders at 40% each use about 80%.
  - **ms/frame** is the raw time; **fps max** is the highest frame rate the GPU could draw it at (1000 ÷ ms). The cost scales roughly with the number of pixels: 4K (3840×2160) costs about 4× as much as 1080p.
  - It's measured with the current slider values; some sliders (iterations, loops, detail) change the cost a lot. Press **Analyze** to re-measure after moving them (or use **Live**).
  - Why not just time the preview as it plays? With so little to do, the graphics card lowers its clock speed, and a light shader then times up to 2× slower than it really needs. Measurements run frames back to back so the card works at full speed, as it does under a real show's load.
  - While the output window (or fullscreen) is open, measuring times the output itself, at its actual resolution, instead of running a separate 1080p measurement alongside it: continuously with **Live** on ("live in the output"), or for one second when you press **Analyze** ("measured in the output"). These are the output's real frame times, so a light shader can read higher here than measured at 1080p: at 60 fps with little to do, the card lowers its clocks.
  - CPU load isn't shown: shaders run entirely on the GPU, and the plugin's CPU work per frame is tiny.
  - Results depend on the graphics card (and, on laptops, whether it's plugged in). Measurements from the queue and from this tab are shared for the session.
- **Save settings.** Writes `<shader>.ffstudio.json` next to the shader (a `<shader>.ffmaker.json` from before the rename is still read, and replaced by the new name on the next save). **Build FFGL** saves it automatically. Queue builds, ISF exports and the command line all use it, so set up a shader once and batch-build it later.

**Packaged app:** `dist\FFStudio.exe` (build it with `venv\Scripts\python compile.py`) runs without Python installed. Building plugins still needs CMake and Visual Studio's C++ tools.

On macOS, `venv/bin/python compile.py` builds `dist/FFStudio.app` (Apple Silicon). It writes plugins to `~/Documents/FFStudio/output`, and building them still needs CMake and the Command Line Tools. The app is signed ad hoc, not notarized: on another Mac, open it the first time with right-click → **Open**. Headless check: `FFStudio.app/Contents/MacOS/FFStudio --selftest <shader> <dir>`.

**Command line:**

```
venv\Scripts\python -m ffstudio <files or folders> --to ffgl|isf|both|check [--out DIR] [--no-params] [--test]
```

- `--to check` validates shaders without building anything.
- `--test` loads each finished plugin in FFStudio's built-in test host and renders a few frames.

---

## Supported inputs

| Format | Detected by | Becomes |
| :-- | :-- | :-- |
| **ISF** (`.fs`) | `/*{ JSON }*/` header | Source, Effect (1 image input), or Mixer (Transition category with 2 images) |
| **Shadertoy** | `mainImage()` | Source; or Effect if it reads `iChannel0` |
| **GLSL Sandbox / plain GLSL** | `main()` | Source (or Effect if it declares a `sampler2D` uniform) |

Supported features:
- **ISF:** all input types. Multi-pass and persistent buffers (`PASSES`, `PERSISTENT`, `FLOAT`, `WIDTH`/`HEIGHT` expressions) are supported, as are all `IMG_*` macros, `DATE`, `FRAMEINDEX` and `TIMEDELTA`.
  - `IMPORTED` images are embedded in the plugin.
  - `audio`/`audioFFT` inputs receive the host's audio spectrum.
  - Companion `.vs` vertex shaders (same file name, next to the `.fs`) are supported.
- **Shadertoy:** `iTime`, `iResolution`, `iMouse`, `iDate`, `iFrame`, `iTimeDelta`, `iChannel0-3` and `iChannelResolution`.
- **GLSL Sandbox:** `time`, `resolution`, `mouse` and `surfacePosition`. Unknown `uniform`s become sliders.
- **Tempo (any dialect):** `iBPM`, `iBeat` and `iBarPhase`. See *Tempo* below.
- **Older GLSL:** `texture2D`, `gl_FragColor` and similar legacy names are translated automatically.
- **Uninitialised variables** are set to zero, as browsers do. Shadertoy code often relies on this.

### Shadertoy channels
By default every `iChannel` reads the clip, which makes the plugin an effect. Choose a different source with a comment line anywhere in the shader:

```glsl
// ffstudio: iChannel1 = textures/rock.jpg   (image file, relative to the shader; embedded in the plugin)
// ffstudio: iChannel2 = noise                (generated RGBA noise texture)
// ffstudio: iChannel3 = audio                (live audio spectrum from the host)
// ffstudio: iChannel0 = input                (the clip; the default)
```

`// ffmaker:` (FFStudio's former name) still works the same, so existing shaders don't need changing.

If an image file is missing, a noise texture is used and FFStudio warns you.

#### Sampler settings
Like Shadertoy's per-channel settings, add `filter`, `wrap` and `vflip` after the source:

```glsl
// ffstudio: iChannel1 = textures/pixels.png filter=nearest wrap=clamp
// ffstudio: iChannel2 = textures/rock.jpg vflip=false
```

| Setting | Values | Default |
| :-- | :-- | :-- |
| `filter` | `nearest` (sharp pixels), `linear`, `mipmap` (smooth when shrunk) | images: `mipmap`; buffers and the clip: `linear` |
| `wrap` | `clamp`, `repeat` (tiles) | images: `repeat`; buffers and the clip: `clamp` |
| `vflip` | `true`, `false` (image upside down, as on Shadertoy) | `true` |

Shadertoy JSON exports carry these settings already. In multi-buffer shaders each pass can read the same buffer with different settings. The clip can't be mipmapped, so `mipmap` acts like `linear` there.

In ISF exports, `nearest` and `repeat` are emulated in the shader, because ISF hosts always sample images smoothly and clamped. Two small differences remain: `mipmap` acts like `linear`, and with `linear` + `repeat`, the half texel at each tile edge clamps instead of blending with the opposite edge (only visible on very low-resolution images).

### Multi-buffer Shadertoy shaders (Buffer A–D)
Either:
- **Shadertoy JSON:** drop the `.json` export of the shader. Passes, channel wiring and texture slots come from the file. Texture images are used if a file with the same name sits next to the JSON; otherwise noise is used.
- **Sectioned text:** paste each tab into one `.txt` under header lines, with channel directives inside each section:

```glsl
// ==== Common ====
...
// ==== Buffer A ====
// ffstudio: iChannel0 = Buffer A     (feedback: reads its own previous frame)
void mainImage(...) { ... }
// ==== Image ====
// ffstudio: iChannel0 = Buffer A
void mainImage(...) { ... }
```

Buffers become float feedback buffers in the FFGL plugin and `PASSES` in ISF exports. Errors are reported as `[Buffer A] line N`.

### Not yet supported
- Shadertoy cubemap and sound-output passes.
- Keyboard input (reads black).
- Real waveform data. FFGL hosts only provide the spectrum, so waveform inputs get the spectrum instead.

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
Top-level `const float/bool/vec3` values and `#define NAME 1.5` lines become sliders, toggles or color pickers. To leave one out, untick it in the Studio tab: it's compiled in as a constant at its current value. (The command line's `--no-params` still turns this off for a whole run.)
- Math constants (PI, TAU, epsilons…) are skipped.
- Constants that must stay constant (array sizes, `case` labels) are skipped.
- If turning a constant into a slider would break compilation, FFStudio puts it back as a constant and tells you.

### Built-in controls
- **Speed** is added to every animated shader and scales time smoothly; changing it never makes the animation jump. If the shader already has its own "speed" control, FFStudio's is called **Time Scale** instead.
- **Sliders that multiply time** (`iTime * speed`, `TIME * rate`, `vec3(rx, ry, rz) * iTime`, also inside `#define`s) don't jump the animation either: the plugin keeps a running total of time × slider, so moving the slider changes how fast things move from that moment on. This also covers the shader's own speed controls. It applies to FFGL plugins and the preview; ISF hosts can't keep a running total, so in ISF exports these sliders (and Speed) still jump. Time that reaches the slider through a variable first (`float t = iTime; … t * speed`) isn't detected.
- **Mouse X/Y** and **Mouse Click** are added when a shader uses the mouse.

### Tempo
Shaders in any dialect can use the host's tempo by reading these names (no declaration needed):

| Name | Value |
| :-- | :-- |
| `iBPM` | Tempo in beats per minute |
| `iBeat` | Beats elapsed, in step with the host's bars (`fract(iBeat)` pulses every beat) |
| `iBarPhase` | 0 to 1 through the current bar |

Resolume sends its tempo to FFGL plugins. Until a host sends any, and in the preview, the plugin runs at 120 BPM. ISF hosts have no tempo input, so ISF exports get a **BPM** slider (default 120) and count beats from `TIME`.

### Alpha
Shadertoy and GLSL Sandbox ignore output alpha, so FFStudio makes those plugins opaque. ISF shaders keep their alpha.

---

## Troubleshooting

- **"Shader does not compile"**: the log lists the errors with line numbers from *your* file.
- **Build failed**: check that CMake and Visual Studio's C++ tools are installed. The log shows the compiler's error lines.
- **Plugin missing in Resolume**: make sure the `.dll` is in a folder Resolume scans, then restart Resolume. FFGL shows only the first 16 characters of a plugin name. FFStudio keeps those 16 characters unique within one batch.

---

## Shader licensing

Shaders are the creative property of their authors.
- Shadertoy code defaults to **CC BY-NC-SA 3.0** unless the code says otherwise.
- ISF and GLSL Sandbox shaders vary.

Keep credits, and respect non-commercial and share-alike terms.
