# FFStudio User Manual

**FFStudio** converts GLSL shaders into:
- **FFGL 2 plugins** for Resolume 7.21.3+ and other FFGL hosts (`.dll` on Windows, universal `.bundle` on macOS)
- **ISF 2 files** (`.fs`) for MadMapper, VDMX, Millumin and other ISF hosts

It accepts ISF, Shadertoy, GLSL Sandbox and plain GLSL fragment shaders. It also plays them: a live preview with sliders for every parameter, an output window or fullscreen on a second monitor, a slideshow through your shaders, sending to other apps (Spout, Syphon, NDI®), and remote control from a phone or tablet with TouchOSC.

This is a beta version. Questions, problems and suggestions are welcome: **[bzsqrl@gmail.com](mailto:bzsqrl@gmail.com)** (see *Reporting problems* for what to include). News and new versions: **[bzsqrl.com](https://bzsqrl.com)**.

---

## What's in the package

| File | What it is |
| :-- | :-- |
| `FFStudio.exe` (Windows) or `FFStudio.app` (macOS) | The app. There's no installer: it runs from wherever you put it. |
| `touchosc` | TouchOSC layouts for remote control (see *Remote control* below) |
| `sample-shaders` | Shaders to try FFStudio with |
| `USER_MANUAL.html` | This manual |
| `EULA.txt` | The licence agreement for this beta. By using FFStudio, you agree to it. |
| `THIRD_PARTY_NOTICES.txt` | The licences of the open-source software inside FFStudio |

## System requirements

**Windows**
- 64-bit Windows 10 or 11.
- A graphics card with **OpenGL 4.1** or later and its manufacturer's driver (practically any NVIDIA, AMD or Intel graphics from 2012 on). FFStudio renders every shader on your graphics card, so it doesn't work in a virtual machine or over Remote Desktop.
- *Only for building FFGL plugins:* Microsoft's free Build Tools for Visual Studio (see *Installing on Windows*). Everything else works without them.

**macOS**
- A Mac with **Apple Silicon** (M1 or later). FFStudio.app doesn't run on Intel Macs.
- **macOS 14 Sonoma** or later.
- *Only for building FFGL plugins:* Apple's free Xcode Command Line Tools and CMake (see *Installing on macOS*).

**For the plugins you make:** Resolume 7.21.3 or later, or another FFGL 2 host. Mac plugins are universal: they also run on Intel Macs (macOS 10.15+).

## Installing on Windows

1. Right-click the zip, choose **Extract All…**, and extract it to a folder you can write to, such as Documents or the Desktop.
   - Don't start FFStudio.exe from inside the zip: Windows would run it from a temporary folder, and the plugins it builds would be lost.
   - Don't put it in `Program Files`: FFStudio writes the plugins it builds to an `output` folder next to FFStudio.exe, and its settings files next to your shaders.
2. Double-click **FFStudio.exe**. It isn't code-signed yet, so Windows may say *Windows protected your PC*: click **More info**, then **Run anyway**. Windows asks only once. Some antivirus apps also scan it the first time, which can take a while.
3. FFStudio takes a few seconds to start (it unpacks itself each time).
4. Windows Firewall asks whether FFStudio may use the network. Allow it on **private networks**: remote control and NDI need it. Everything else works without it.

**To build FFGL plugins** (optional: the preview, Export ISF, Spout, NDI and remote control work without it):

1. Download the free **Build Tools for Visual Studio** from [visualstudio.microsoft.com/visual-cpp-build-tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/) and run it. If you already have Visual Studio 2022 or later, open the Visual Studio Installer and modify your installation instead.
2. Tick the **Desktop development with C++** workload and click **Install**. Its default parts are all FFStudio needs (they include CMake). The download is several GB.
3. If FFStudio was running, restart it.

Without them, **Build FFGL** says what's missing and where to get it.

## Installing on macOS

1. Double-click the zip to unpack it, and drag **FFStudio.app** to your **Applications** folder (or wherever you like).
2. The app isn't notarized by Apple yet, so macOS blocks it the first time. Double-click it, and click **Done** (or **OK**) when macOS says it can't verify it. Then open **System Settings → Privacy & Security**, scroll down to the message about FFStudio, click **Open Anyway**, and confirm with your password. macOS asks only once.
   - On macOS 14 you can instead right-click the app and choose **Open**.
   - Or, in Terminal: `xattr -dr com.apple.quarantine /Applications/FFStudio.app`
3. When FFStudio first uses the network (remote control or NDI), macOS asks whether it may find devices on your local network: click **Allow**.
4. Plugins go to `~/Documents/FFStudio/output`, so macOS asks once for access to your Documents folder: click **Allow**.

**To build FFGL plugins** (optional: the preview, Export ISF, Syphon, NDI and remote control work without it):

1. Install the **Xcode Command Line Tools**: open Terminal, type `xcode-select --install`, press Return, and click **Install**. The full Xcode app isn't needed (if you have it, this step is already done).
2. Install **CMake**: download the macOS `.dmg` from [cmake.org/download](https://cmake.org/download/) and drag **CMake.app** to Applications. If you use Homebrew, `brew install cmake` works too.
3. If FFStudio was running, restart it.

Without CMake, **Build FFGL** says what's missing.

## First launch

FFStudio opens with two tabs, **Queue** and **Studio**, and the **Log** at the bottom, which reports everything FFStudio does. Its first lines include FFStudio's version, the graphics card FFStudio uses (`GPU: …`) and the address for remote control (`OSC remote control: …`). If it says *GPU validation unavailable* instead, see *Troubleshooting*.

A first tour, with the sample shaders:

1. Drag the `sample-shaders` folder onto the **Queue** tab (or click **📁** and choose it). Each shader becomes a row in the queue.
2. Press **Shift+Tab** (or click **Studio**). The first shader in the queue plays in the preview, with a slider, switch or menu for each of its parameters.
3. Press **→** and **←** to step through the queue, or click **Auto** to play it as a slideshow. Move a slider to change the shader as it plays.
4. Click **⧉** to open an output window. Drag it to a second monitor and double-click it to make it fullscreen; **Esc** brings it back.
5. Click **Build FFGL** to make a plugin of the shader that's showing (this needs the build tools above). The first build takes about a minute, because it sets up a build workspace and compiles the FFGL SDK; after that, a plugin takes a couple of seconds. The log says where the plugin went: the `output` folder next to FFStudio.exe (on macOS, `~/Documents/FFStudio/output`).
6. Copy the plugin (`.dll` on Windows, `.bundle` on macOS) to **Documents\Resolume Arena\Extra Effects** (macOS: `~/Documents/Resolume Arena/Extra Effects`), which Resolume scans by default (more folders can be added in Resolume's *Preferences → Video*), and restart Resolume. A shader that makes its own picture appears under **Sources**, one that changes a clip under **Effects**.
7. **Export ISF** saves the shader as an `.fs` file for MadMapper, VDMX, Millumin and other ISF hosts.

FFStudio saves each shader's settings (slider values, ranges, names) in a `<shader>.ffstudio.json` file next to the shader, so keep your shaders in a folder you can write to.

## Updating and uninstalling

**To update**, replace FFStudio.exe (or FFStudio.app) with the new one. Your shaders' settings stay, since they're next to the shaders. If the TouchOSC layouts changed, copy them to your phone or tablet again: TouchOSC keeps its own copy.

**To uninstall**, delete FFStudio.exe (or FFStudio.app). FFStudio installs nothing else, but it leaves:
- its build workspace: `%LOCALAPPDATA%\FFStudio` (macOS: `~/Library/Caches/FFStudio`);
- the `output` folder with your plugins (macOS: `~/Documents/FFStudio`);
- the `.ffstudio.json` settings files next to your shaders.

The Build Tools, Command Line Tools and CMake are uninstalled separately, if you installed them for FFStudio.

---

## Using FFStudio

### Queue tab

The queue is the list of shaders to build, export or play.

1. Drop shader files or folders onto the **Queue** (or use **+** to add files and **📁** to add a folder).
2. Click **Build FFGL** to make FFGL plugins, or **Export ISF** to make `.fs` files (it asks for a folder).
3. Plugins are written to the `output` folder (see *First launch*). Copy them to a folder Resolume scans and restart Resolume.

In the queue, select rows with a click (Shift/Ctrl-click for several), or press **Ctrl+A** (⌘A on macOS) to select them all. Ctrl+A works anywhere on the Queue tab; in text fields it keeps its usual meaning.
- **With rows selected**, **Reset**, **Analyze**, **Build FFGL** and **Export ISF** act on just those rows, and show how many in brackets, e.g. **Build FFGL (3)**. Selected rows are rebuilt even if they're already done. Click empty space in the list or press **Esc** to deselect; the buttons then work on the whole queue again (Build skips rows that are already done).
- **Reset** sets built and failed rows back to Pending, so **Build FFGL** converts them again (for example after changing settings) without reloading the files. **Clear Completed** removes the built rows; **Clear All** empties the queue.
- **Delete** removes the selected rows. Right-click for the same actions plus **Open in Studio**; double-clicking a row also opens it in the editor. On macOS, Control-click also opens the menu.
- **Switching to the Studio tab** (its button, or **Shift+Tab**) loads a shader from the queue and sets what ← / → and the slideshow step through: with **one row selected**, that row, stepping through the whole queue; with **several selected**, the first of them, stepping through only those; with **none selected**, the first row, stepping through the whole queue. An empty queue loads nothing. If you come back without changing the queue or its selection, Studio stays on the shader it was showing, so you can glance at the queue mid-playlist. Double-click or **Open in Studio** always loads the row.
- **Shift+Tab** switches between the Queue and Studio tabs from anywhere in the window.
- Drag the column header edges to resize columns. The **Size** column shows each shader file's size. Click the **Filename**, **Type**, **Size** or **GPU** heading to sort the queue by it (click again to reverse; Size and GPU start with the largest). The sorted order becomes the queue's order, for builds and for ← / → and the slideshow.
- **Analyze** fills the **GPU @1080p** column with each shader's GPU load (see *GPU load* below), for the selected rows or the whole queue. Press it again to stop (it reads **Stop Analysis** meanwhile; **Build FFGL** likewise reads **Cancel Build**). Sorting by GPU puts the heaviest first; ⚠ marks shaders that can't hold 60 fps at 1080p on this computer. The log names the heaviest one.

### Studio tab

Open a shader with **+** (or paste one) and click **Analyze** (or press Ctrl+Enter; ⌘+Enter on macOS): it processes the code, loads it into the preview and measures its GPU load. After editing the code, Analyze processes it again; with the code unchanged it only measures. **Build FFGL (.dll)** (`.bundle` on macOS) then makes the plugin and **Export ISF (.fs)** the ISF file, as on the Queue tab. You get:
- **Live preview.** Rendered on your GPU the same way the plugin renders it.
  - **Fullscreen:** click **⛶**, double-click the preview, or press **Ctrl+F** (⌘F on macOS) to fill the monitor FFStudio is on; press **Esc**, **Ctrl+F** / ⌘F again, or double-click to return.
  - **Output window (multi-monitor):** click **⧉** (left of ⛶) to show the live render in its own window, opened on another monitor if you have one. Move and resize it like any window; FFStudio stays usable, and slider changes show up live. Double-click it or press **Ctrl+F** / ⌘F (in it, or in FFStudio) to make it fullscreen on the monitor it's on; **Esc** goes back to the window. The **⧉** button is a toggle (highlighted while the window is open): press it again, or use the window's close button, to close it. While the output is fullscreen the button does nothing; press Esc first.
  - **Sending to other apps (Send row, under the preview):** each button is off when FFStudio starts; click it to turn it on (highlighted) or off. They work together, and on their own: they keep sending when you switch shaders (← / →, the slideshow) or go to the Queue tab, with or without the output window. While one is on, the output window shows the same frames, scaled to fit. Turned on before a shader is loaded, sending starts with the first one.
    - **Spout** (Windows) or **Syphon** (macOS) sends the shader loaded in the Studio tab to other apps on the same computer (Resolume, MadMapper, OBS, TouchDesigner, …) as a source named **FFStudio**, at 1920×1080, about 60 fps, GPU to GPU.
    - **Remote control:** the controls here and the shader's parameters can also be worked from TouchOSC on a phone, tablet or computer (see *Remote control* below).
    - **NDI®** sends it over the network, to apps on this computer or others on the same network, as the source **COMPUTERNAME (FFStudio)**, at 30 fps. The menu beside it picks **1080p** (1920×1080) or **720p** (1280×720); changing it while sending switches straight away. NDI uses some CPU to compress the frames, more at 1080p. The first time, Windows Firewall asks whether FFStudio may use the network (allow it, or other computers won't see the source), and macOS asks for Local Network access. Receive it in Resolume (Sources → NDI), OBS (with the DistroAV plugin), or NDI Studio Monitor (part of the free NDI Tools).
  - Both render at the window's resolution (up to 1920 wide, scaled up beyond that). The output draws on its own thread, so it keeps playing smoothly while FFStudio is busy (e.g. rebuilding the parameter list after a shader switch). While it's open, the small preview keeps running at a lower frame rate (about 10 fps) and follows shader switches; on Windows, FFStudio's own window pauses while you drag the output window.
  - **Queue playlist:** the **←** / **→** buttons under the preview (and the ← / → keys: anywhere in the Studio tab, unless you're typing in the code box or a text field or have clicked a slider (click anywhere else to release it); and in fullscreen or the output window) load the previous / next shader in the **Queue** (or in the selected rows, if several were selected when you switched to Studio) into the Studio tab. Each starts from the beginning with its saved settings, shaders that don't compile are skipped, and the list wraps around. The label next to them shows the position in the queue (e.g. "3 / 12"), or "not in queue" when the loaded shader isn't in it.
  - **Slideshow:** **Auto** (next to the ← / → buttons) steps to the next queue shader every few seconds; type the time in the box beside it (seconds, minimum 1, Enter to apply; default 10). After the last shader it loops back to the first. The button is highlighted while on, and the label counts down ("next in 4s"). Pausing the preview (⏸) holds the countdown; ← / → restart it. It keeps running in fullscreen and with the output window open, so it works as an unattended playlist on a second monitor. Press **Auto** again to stop.
  - Fullscreen and the output window always show the shader loaded in the Studio tab, so loading another shader (from the queue, **+**, or a drop) switches them too, and recompiling after a settings change updates them live. If the loaded shader doesn't compile, they keep showing the last one that did.
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
  - Nudge a slider with the keyboard: click it (its handle turns amber), then press **←** / **→** to step it by 1/100 of its range (1 for whole numbers). Click anywhere else to release it: ← / → then step through the queue again.
- **GPU load.** Under the preview, a bar and readout show how hard the shader works your graphics card, e.g. **29% of 60 fps** and *4.81 ms/frame · ~208 fps max · 1920×1080*.
  - It's the GPU time one frame takes, timed by the graphics card itself (so vsync, the screen and FFStudio's own work don't count), measured at 1920×1080 over about a second.
  - **Live** (highlighted while on) measures continuously: a new reading about every half second, so it follows slider moves and shader switches as you make them. It measures at 1920×1080 in the background (the preview itself stays small) and pauses while the preview isn't showing, e.g. on the Queue tab. It keeps the graphics card busy, so it's **off** by default: switching shaders (e.g. in a slideshow) then costs as little as possible, nothing is measured unless you press **Analyze**, and results already known (from **Analyze**, **Live**, or the queue's **Analyze**) still show. Turn it on for diagnostics or when comparing shaders. While Live is on, **Analyze** only processes changed code (Live does the measuring).
  - **% of 60 fps** is that time as a share of a 60 fps frame (16.7 ms): under 50% (green) leaves plenty of room; 50–100% (amber) is heavy; over 100% (red) means it can't run at 60 fps at 1080p on this computer, even on its own. In Resolume, layers and effects add up: two shaders at 40% each use about 80%.
  - **ms/frame** is the raw time; **fps max** is the highest frame rate the GPU could draw it at (1000 ÷ ms). The cost scales roughly with the number of pixels: 4K (3840×2160) costs about 4× as much as 1080p.
  - It's measured with the current slider values; some sliders (iterations, loops, detail) change the cost a lot. Press **Analyze** to re-measure after moving them (or use **Live**).
  - Why not just time the preview as it plays? With so little to do, the graphics card lowers its clock speed, and a light shader then times up to 2× slower than it really needs. Measurements run frames back to back so the card works at full speed, as it does under a real show's load.
  - While the output window (or fullscreen) is open, measuring times the output itself, at its actual resolution, instead of running a separate 1080p measurement alongside it: continuously with **Live** on ("live in the output"), or for one second when you press **Analyze** ("measured in the output"). These are the output's real frame times, so a light shader can read higher here than measured at 1080p: at 60 fps with little to do, the card lowers its clocks.
  - CPU load isn't shown: shaders run entirely on the GPU, and the plugin's CPU work per frame is tiny.
  - Results depend on the graphics card (and, on laptops, whether it's plugged in). Measurements from the queue and from this tab are shared for the session.
- **Save settings.** Writes `<shader>.ffstudio.json` next to the shader. **Build FFGL** saves it automatically. Queue builds, ISF exports and the command line all use it, so set up a shader once and batch-build it later.

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

## Remote control (OSC, TouchOSC)

FFStudio's Studio tab can be controlled from a phone, a tablet or another computer over the network, with OSC. It's always on: FFStudio listens on UDP port **8000** and sends what it's doing back on port **8001**. The log says so when FFStudio starts, with this computer's address: `OSC remote control: 192.168.1.20, port 8000 (feedback to port 8001)`. The first time, Windows Firewall asks whether FFStudio may use the network: allow it on private networks, or other devices can't reach it. macOS asks for Local Network access.

It controls what's under the preview: play / pause, restart, ← / →, the slideshow (**Auto** and its time), the output window and fullscreen, Spout (Syphon on macOS), NDI and its size, and the loaded shader's parameters. Not the queue, **Build FFGL**, **Export ISF** or **Analyze**.

You need [TouchOSC](https://hexler.net/touchosc) (by hexler, for Windows, macOS, iOS and Android). **TouchOSC layouts** are in the `touchosc` folder:

- `FFStudio_desktop.tosc`: one landscape page, for TouchOSC on a computer or a tablet.
- `FFStudio_phone.tosc`: for phones held upright (made for the Pixel 7a; fits other 20:9 phones). A **CONTROL** page, then the parameters, 8 to a page.

To use one:

1. In TouchOSC, open **Connections → OSC** and set up any connection (the layouts send and receive on all of them; other enabled connections get FFStudio's messages too, which other apps ignore): **UDP**, **Host** = the FFStudio computer's address (from the log; `127.0.0.1` when TouchOSC runs on the same computer), **Send Port** `8000`, **Receive Port** `8001`.
2. Open the layout in TouchOSC and start the control surface (▶). To get it onto a phone or tablet, copy the `.tosc` file there (by cloud drive, email or USB) and open it from TouchOSC. TouchOSC keeps its own copy of a layout on each device: after a new version of FFStudio's layouts, copy the file to the phone or tablet again.
3. The status line (under the shader name on the desktop layout, at the bottom on the phone) changes to **connected: FFStudio on COMPUTERNAME** within a couple of seconds. If it stays at *not connected*, check the address and ports, that both are on the same network, and the firewall.

On a Mac with tap to click turned on, TouchOSC on that Mac misses some taps on the trackpad (FFStudio never receives them; other macOS apps have the same problem). Press the trackpad down instead, or use a mouse.

The layout follows FFStudio: the switches light up as things are turned on (from the layout, in FFStudio or by the slideshow), and loading another shader fills in its parameter names, values and faders.

**Parameters** take up to 24 slots, in the order of the Studio tab's list (without those kept as constants). Each value has a slot: a colour takes one per channel (R, G, B and, if it has one, A) and a point one per axis (X, Y). Unused slots are hidden. A fader covers the parameter's range (as set in the Studio tab); for a menu it steps through the options; a switch is on past the middle, and a trigger fires at the right-hand end. Moving a fader changes the value as the Studio tab's slider does, so it's saved with the shader's settings too. A shader with more than 24 values (rare) shows the first 24; the layout says e.g. *28 parameters: the first 24 are here*.

**From other OSC apps** (Open Stage Control, Max, Lemur, …): send to UDP port 8000 at the FFStudio computer's address. Switches take `1` or `0` (no argument toggles); buttons act on a message with no argument or `1` (not on the `0` a button sends when it's released).

| Address | Argument | What it does |
| :-- | :-- | :-- |
| `/ffstudio/play` | 1 / 0 | Play / pause |
| `/ffstudio/restart` | | Restart the shader |
| `/ffstudio/prev`, `/ffstudio/next` | | Previous / next shader in the queue (as ← / →) |
| `/ffstudio/auto` | 1 / 0 | Slideshow on / off |
| `/ffstudio/auto/seconds` | seconds | Slideshow time (minimum 1) |
| `/ffstudio/auto/seconds/up`, `/down` | | Slideshow time one step longer / shorter (… 8, 10, 12, 15, 20 …) |
| `/ffstudio/output` | 1 / 0 | Output window open / closed (closing works even when it's fullscreen) |
| `/ffstudio/fullscreen` | 1 / 0 | Fullscreen, as ⛶ (the output window's, if it's open) |
| `/ffstudio/spout` | 1 / 0 | Spout (Syphon on macOS) on / off |
| `/ffstudio/ndi` | 1 / 0 | NDI on / off |
| `/ffstudio/ndi/720p` | 1 / 0 | NDI at 1280×720 / 1920×1080 |
| `/ffstudio/param/1` … `/24` | 0 … 1 | Parameter slot (as above) |
| `/ffstudio/ping` | | Answered with `/ffstudio/pong` and the computer's name |
| `/ffstudio/sync` | | Send the whole state again |

FFStudio sends its state to every address that has sent it a message in the last 30 seconds (send `/ffstudio/ping` now and then to keep it coming; the TouchOSC layouts do, every second), on port 8001 and on the port the message came from. The switches come back on their own addresses as `1` / `0`, each parameter slot as its `0 … 1` value, and these as text: `/ffstudio/shader` (the shader's name), `/ffstudio/queue` (e.g. `3 / 12 · next in 4s`), `/ffstudio/time`, `/ffstudio/auto/label` (e.g. `10 s`), `/ffstudio/spout/name` (`Spout` or `Syphon`), `/ffstudio/params` (how many parameters), `/ffstudio/param/<n>/name` and `/ffstudio/param/<n>/value` (both empty for an unused slot). Only what changes is sent again.


---

## Troubleshooting

**Starting FFStudio**
- **Windows protected your PC**, or an antivirus app removes FFStudio.exe: FFStudio isn't code-signed yet. Click **More info → Run anyway**; in the antivirus app, restore the file and allow it.
- **macOS: "FFStudio can't be opened"** or **"is damaged and can't be opened"**: macOS blocks apps from outside the App Store that aren't notarized. Use **Open Anyway** (see *Installing on macOS*), or run `xattr -dr com.apple.quarantine /Applications/FFStudio.app` in Terminal.
- **No preview, or the log says *GPU validation unavailable*:** FFStudio can't use your graphics card's OpenGL 4.1. Install the latest driver from NVIDIA, AMD or Intel (not just the one Windows Update installed). It doesn't work in a virtual machine or over Remote Desktop. On a laptop with two graphics chips, set FFStudio.exe to *High performance* in Windows *Settings → System → Display → Graphics*.

**Shaders and plugins**
- **"Shader does not compile"**: the log lists the errors with line numbers from *your* file.
- **Build FFGL says "No C++ compiler found" or "CMake not found":** install the build tools (see *Installing on Windows* or *Installing on macOS*) and restart FFStudio.
- **Build failed**: the log shows the compiler's error lines.
- **Plugin missing in Resolume**: check that the `.dll` (Windows) or `.bundle` (macOS) is in a folder Resolume scans, then restart Resolume. FFGL shows only the first 16 characters of a plugin name. FFStudio keeps those 16 characters unique within one batch.
- **Settings aren't kept:** FFStudio saves them next to the shader, so the shader's folder must be writable (not inside a zip, a read-only drive or `Program Files`).

**Network (NDI and remote control)**
- **Other computers don't see the NDI source, or TouchOSC stays *not connected*:**
  - Both devices must be on the same network. Guest and public Wi-Fi often keep devices apart.
  - Windows: allow FFStudio through the firewall on private networks (*Windows Security → Firewall & network protection → Allow an app through firewall*), and check that your network is set to *Private* (*Settings → Network & internet*), not *Public*.
  - macOS: turn FFStudio on in *System Settings → Privacy & Security → Local Network*.
- **The log says *OSC remote control unavailable: UDP port 8000 is in use*:** another app (or a second copy of FFStudio) is using port 8000. Close it and restart FFStudio.

## Reporting problems

Email problems, questions and suggestions to **[bzsqrl@gmail.com](mailto:bzsqrl@gmail.com)**. New versions are announced at **[bzsqrl.com](https://bzsqrl.com)**.

When something goes wrong, please send:

- **What you did, what happened, and what you expected.**
- **FFStudio's version:** it's in the title bar and the log's first line (e.g. `FFStudio 0.9.0-beta.1`).
- **Your computer:** Windows or macOS version, and the `GPU: …` line from the log.
- **The log:** click in it, press **Ctrl+A** then **Ctrl+C** (⌘A, ⌘C on macOS), and paste it into your message.
- **The shader**, if it's about one: the shader file and its `.ffstudio.json`, if it has one.
- A screenshot, if it's about how something looks.

If FFStudio won't start at all, its self-test can show why. It converts and builds one shader and checks Spout or Syphon, NDI and remote control, without opening the window, and writes `selftest.log`:

- **Windows:** in the folder with FFStudio.exe, type `powershell` in File Explorer's address bar and press Enter, then type `.\FFStudio.exe --selftest ` and a space, drag any shader file into the window (that types its path), type a space and `selftest`, and press Enter.
- **macOS:** in Terminal, type `/Applications/FFStudio.app/Contents/MacOS/FFStudio --selftest ` and a space, drag any shader file into the window, type a space and `~/Desktop/selftest`, and press Return.

Send the `selftest.log` from the `selftest` folder (the plugin it builds there can be deleted).

---

## Running from source (developers)

### Prerequisites (Windows)

- **Python 3.10+** with the packages in `requirements.txt`: `venv\Scripts\pip install -r requirements.txt`
- **CMake**: on your PATH, in its default folder (`C:\Program Files\CMake`), or the one that comes with Visual Studio
- **Visual Studio 2022+ or the Build Tools**, with the "Desktop development with C++" workload
- An OpenGL 4.1 GPU.

### Prerequisites (macOS)

- **Python 3.12** (Homebrew `python@3.12` and `python-tk@3.12`) with the packages in `requirements.txt`: `venv/bin/pip install -r requirements.txt`
- **CMake** (`brew install cmake`)
- **Xcode Command Line Tools** (`xcode-select --install`). The full Xcode app isn't needed.

### Running and packaging

- **GUI:** `venv\Scripts\python src\main_gui.py` (macOS: `venv/bin/python src/main_gui.py`). Plugins go to the project's `output` folder.
- **Packaged app:** `venv\Scripts\python compile.py` builds `dist\FFStudio.exe`; on macOS, `venv/bin/python compile.py` builds `dist/FFStudio.app` (Apple Silicon, signed ad hoc, not notarized). It also writes the package's documents into `dist`: `EULA.txt` (a copy), `THIRD_PARTY_NOTICES.txt` (`tools/make_notices.py`: the licences of what this platform's build bundles) and `USER_MANUAL.html` (`tools/build_manual.py`, from this file). The version is `__version__` in `ffstudio/__init__.py`: it's shown in the title bar, the log and `selftest.log`, and stamped on FFStudio.exe (*Properties → Details*) and FFStudio.app. Headless check: `FFStudio.exe --selftest <shader> <dir>` (macOS: `FFStudio.app/Contents/MacOS/FFStudio --selftest <shader> <dir>`) writes `selftest.log` into `<dir>`.
- **TouchOSC layouts:** edit `tools/build_touchosc.py` and run `venv\Scripts\python tools\build_touchosc.py`, or edit them in TouchOSC's editor.

### Command line

```
venv\Scripts\python -m ffstudio <files or folders> --to ffgl|isf|both|check [--out DIR] [--no-params] [--test]
```

- `--to check` validates shaders without building anything.
- `--test` loads each finished plugin in FFStudio's built-in test host and renders a few frames.

The command line runs from source only, not from FFStudio.exe or FFStudio.app.

---

## NDI

NDI® is a registered trademark of Vizrt NDI AB. FFStudio uses the NDI® SDK (through the cyndilib library) to send video; it isn't made or endorsed by Vizrt NDI AB. NDI runtime: Copyright © 2023–2026 Vizrt NDI AB, all rights reserved; its licence notices ship with FFStudio (`cyndilib/wrapper/bin/*licenses*.txt`). More about NDI: [ndi.video](https://ndi.video/).

## Shader licensing

Shaders are the creative property of their authors.
- Shadertoy code defaults to **CC BY-NC-SA 3.0** unless the code says otherwise.
- ISF and GLSL Sandbox shaders vary.

Keep credits, and respect non-commercial and share-alike terms.
