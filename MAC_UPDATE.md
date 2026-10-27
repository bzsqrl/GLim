# Updating the Mac build after the Windows work

These steps bring a Mac checkout up to date with the work done on Windows, check the new features on macOS and rebuild `FFStudio.app`. Run the commands in Terminal from the FFStudio folder (the git checkout). If you're Claude on the Mac helping with this, read "Context" first.

## Context

Everything below was developed and tested on Windows 11 (RTX 4060, Resolume 7.21.3). The Mac-only code paths were not changed, but shared code was. None of it has been compiled or run on macOS yet, except possibly `100a29c` (see the table).

Commits since the Mac was last in sync (`6e47677`, "Add Windows update instructions"):

| Commit | What changed | Mac impact |
|---|---|---|
| `ac835b5` | Shadertoy channels used only inside a `#define` (`#define FFT(a) texture(iChannel1, …)`) are now declared and wired. Before, these failed with `undefined variable "iChannel1"`. | Shared converter code. |
| `5a72770` | The queue is now a native `ttk.Treeview` instead of one CustomTkinter widget per row. 800+ files load in under a second, where before they froze the window and left rows blank. File types are detected in the background, and the queue's **Export ISF** runs off the UI thread. The build log keeps its last 5,000 lines. New: **Build Selected / Export Selected**, Delete/Backspace to remove, a right-click menu, and double-click to open a file. | **GUI, never run on macOS.** The list uses the `clam` ttk theme with custom colours and the font "Segoe UI", which macOS replaces with a fallback. |
| `100a29c` | Queue review fixes: worker threads no longer read Tk variables, rows removed mid-build are skipped, and right-click is bound to `<Button-2>` on macOS. | The `<Button-2>` binding is Mac-only. It may already be on this Mac if it was committed there. |
| `2892180` | **Sliders multiplied by time no longer scrub.** `iTime * speed`, `vec3(rx, ry, rz) * iTime` and the like become running totals (`ffm_phaseN`). The plugin keeps them (`FFM_PHASES`), adding slider × frame time every frame. ISF exports still use the plain product, so they still jump in ISF hosts. | **New C++ in `templates/ffgl/Plugin.cpp` and `FFStudioPlugin.h`, never compiled with clang.** |

The new C++ is small and should be portable: a `std::vector<double>` of totals, a loop over `FFM_PHASES` in `ProcessOpenGL`, and one `glUniform1f` per total per pass.

The GUI is the most likely place for Mac-specific problems. See step 6.

## 0. Requirements

These should still be installed from the Mac port:
- **Xcode Command Line Tools:** `xcode-select -p` prints a path.
- **Homebrew Python 3.12 with Tk, and CMake:** `brew list python@3.12 python-tk@3.12 cmake`.

## 1. Pull

Before pulling, check `git status`, and commit or `git stash` any local changes.

```bash
git checkout main
git pull origin main
git log --oneline -1
```

The last line should show the commit that added this file, or a later one.

## 2. Update the Python environment

```bash
venv/bin/python -m pip install --upgrade -r requirements.txt pyinstaller
```

## 3. Run the tests from source

```bash
venv/bin/python tests/run_corpus.py --isf
venv/bin/python tests/run_corpus.py --isf --dir tests/fixtures
```

These convert, compile and render on the Mac's GPU. They don't build plugins.

**Expected (the Windows results):**
- **Samples:** 67 `OK` and 12 `STATIC` of 79. ISF export: 40 `OK`, 39 `n/a`.
- **Fixtures:** 6 `OK` and 6 `STATIC` of 12. ISF export: 9 `OK`, 3 `n/a`.
- **No failures:** no `BLACK`, `COMPILE` or `PARSE` rows, and the ISF column has no `REIMPORT`, `DIFF`, `FLIP` or `FAIL`.

`STATIC` isn't a failure: it means the image didn't change between the two sample times. The 12 samples are the still `vv_` patterns and effects; most fixtures are still by design.

Two fixtures are new:
- `shadertoy_define_channel`: channels used only in `#define`s.
- `shadertoy_rate_params`: time × slider in many forms. It also checks that a function parameter shadowing a slider, and a slider used as a divisor, are left alone.

`cc0_anotherBusShader` sometimes shows `DIFFn` in the ISF column. It reads uninitialised variables, so this isn't new.

## 4. Build test batch v4

This compiles the new plugin C++ with clang, then loads each plugin in FFStudio's test host. The first build reconfigures the cached workspace (`~/Library/Caches/FFStudio`), because the runtime template changed. That takes about a minute.

```bash
venv/bin/python -m ffstudio --to both --test --out output/test_batch_v4 \
  tests/fixtures/shadertoy_rate_params.txt tests/fixtures/shadertoy_define_channel.txt \
  tests/corpus/bare_fractalSymetry.txt tests/corpus/bare_lopyfrac3dOrthofractalEvolution.txt
```

**Expected:** for each shader, a `✓ … .fs` line, then a `✓ … .bundle` line followed by `test host: OK`; at the end, `4/4 converted.` (On Windows, the same command gave four `.dll` files, all `test host: OK`.)

If `tests/corpus/` on this Mac no longer has the two `bare_` files, take them from git: `git checkout -- tests/corpus/bare_fractalSymetry.txt tests/corpus/bare_lopyfrac3dOrthofractalEvolution.txt`. (The test shaders moved from `sample-shaders/` to `tests/corpus/` on 2026-10-27; `sample-shaders/` now holds the CC0 shaders that ship with FFStudio.)

If CMake complains about the existing workspace, delete `~/Library/Caches/FFStudio` and run the command again.

## 5. Package FFStudio.app

```bash
venv/bin/python compile.py
dist/FFStudio.app/Contents/MacOS/FFStudio --selftest tests/fixtures/shadertoy_rate_params.txt /tmp/ffm_selftest
cat /tmp/ffm_selftest/selftest.log
```

**Expected:** the log ends with `built …shadertoy_rate_params.bundle`.

## 6. Check the GUI (the new queue)

Open `dist/FFStudio.app`, or run `venv/bin/python src/main_gui.py`. In the **Queue** tab:

| Check | What should happen |
|---|---|
| Look | A dark list with `#`, Filename, Type and Status columns. The text should be readable in the fallback font. The Type column shows `…` briefly, then the type. |
| Big batch | Make ~800 test files: `mkdir -p /tmp/q && for i in $(seq 1 10); do for f in sample-shaders/*; do cp "$f" "/tmp/q/${i}_$(basename "$f")"; done; done`. Drop `/tmp/q` on the queue. All rows should appear within a second or two, scrolling should be smooth and no rows should be blank. |
| Select | Click a row, Shift-click a range, ⌘-click to add single rows. *(Not verified on macOS: Tk may use Control-click for this instead.)* |
| Buttons | With rows selected, the buttons read e.g. **Build FFGL (n)** and **Export ISF (n)** and act on just those rows. Esc, or clicking empty space below the rows, deselects; the buttons go back to **Build FFGL** / **Export ISF**. |
| Remove | The **delete** key (Backspace) removes the selected rows. |
| Right-click | A two-finger click (or right mouse button) opens Build Selected / Export Selected to ISF / Open in Studio / Remove. **Control-click is not bound**; if that's the habit, it's a one-line addition (`<Control-Button-1>`) next to the `<Button-2>` binding in `src/main_gui.py`. |
| Double-click | Opens the file in the **Studio** tab. |
| While building | The window stays responsive during **Build FFGL**, and **Cancel Build** stops it. |

**Parameter panel (since the efficiency pass).** In the **Studio** tab, the parameter rows and Shadertoy channel menus now use plain Tk/ttk widgets (`src/fast_widgets.py`), which have flat corners. **Checked on the Mac (2026-10-24):** everything in this table works on macOS (M1 Max), including GPU load (timer queries give e.g. 9.6 ms/frame for `bare_fractalSymetry` at 1080p) and the preview with the output window open. The checks:

| Check | What should happen |
|---|---|
| Look | Dark rows, readable text, blue slider handles. The checkboxes and entries are dark, not white. |
| Sliders | Dragging moves the value. Clicking the track jumps there and can keep dragging. Right-click (or Control-click) resets. After a click, ← / → step the value and the handle turns amber. |
| Menus | **long** parameters and the channel / filter / wrap menus open a menu on click, and a choice applies. |
| GPU load | **Analyze** (or **Live** on, then loading a shader) shows "measuring…", then e.g. **29% of 60 fps** with ms/frame under the preview. With Live off, switching shaders measures nothing. **Analyze** on the Queue tab fills the GPU @1080p column; clicking that heading sorts by it. With the output window (**⧉**) open the readout says "live in the output". (OpenGL timer queries.) |
| Buttons | Every click on a button works, also right after the output window or fullscreen closes, without moving the mouse first (`src/ctk_fixes.py`). A quick double click on a toggle (⛶, **⧉** (output window), **Auto**, **Live**, play/pause, **Build FFGL**, **Analyze**) acts once; on ← / → it steps twice. |
| Output window | With the output window (**⧉**) open, the small preview keeps updating (about 10 fps), and the slideshow (**Auto**) runs without stalling. On macOS the window-event poll still takes the GPU lock (`validate.window_lock`); on Windows it doesn't. |

## 7. Check the plugins in Resolume

Copy the four `.bundle` folders from `output/test_batch_v4` to `~/Documents/Resolume Arena/Extra Effects`, then restart Resolume.

| Plugin | What you should see |
|---|---|
| `bare_fractalSymetry` | A tunnel fractal. Moving **Speed**, **Time Scale** or **View Rotation Factor Input** changes the speed smoothly, without jumping the animation. |
| `bare_lopyfrac3dOrthofractalEvolution` | A slowly rotating 3D fractal. **Speed** and **Rotation Speed X/Y/Z** change speed without jumps. |
| `shadertoy_rate_params` | Moving colour bands. **Rate**, **Rate2** and **Wobble** change speed without jumps. |
| `shadertoy_define_channel` | A blue dot circling with a fading trail. It's brighter with audio on the **Audio Spectrum** parameter. |

## 8. MadMapper

Load the four `.fs` files from `output/test_batch_v4`. They should render like the plugins. Moving the speed and rate sliders **will still jump** the animation in MadMapper. That's expected: ISF exports keep the plain product. A hidden-buffer approach was tried and reverted, because some shaders rendered blank in MadMapper.

## 9. Syphon output

The **Spout** button on Windows is **Syphon** on macOS (next to ⛶ in the Studio tab). Turned on, it publishes the Studio tab's shader as the Syphon server "FFStudio" at 1920×1080, with or without the output window. On Windows, Spout passed every check (`validate.FrameSender`, `EditorPanel.toggle_sending`). On the Mac it needs:

1. `venv/bin/pip install -r requirements.txt` (adds `syphon-python[opengl]` and PyObjC; its wheel needs macOS 12 or later).
2. From source (`venv/bin/python src/main_gui.py`): load a shader, click **Syphon** (it turns amber, and the log says `Syphon: sending "FFStudio" at 1920x1080`). In Resolume, add the **Syphon** source "FFStudio"; or use Syphon's Simple Client.

| Check | What should happen |
|---|---|
| Picture | The shader, **the right way up** (if it's upside down, flip `is_flipped` in `FrameSender.send`), moving smoothly, at 1920×1080. |
| No window | It keeps sending on the Queue tab, and when switching shaders (← / →, Auto). |
| Output window | Opening **⧉** while sending shows the same frames; closing it keeps sending. Turning Syphon off with the window open keeps the window. |
| Off | Syphon off: the source disappears from the receiver. |
| FFStudio.app | The same works in the packaged app (the spec bundles the Syphon framework via `collect_data_files('syphon')`). |

**Checked on the Mac (2026-10-24, M1 Max, macOS 14.8, syphon-python 0.2.0), from source, with no code changes:** the GUI was driven by a script and a separate Syphon client received the frames. Every row above passed: 1920×1080, the right way up (`is_flipped` stays False), 60 fps sent and received; sending carries on from the Queue tab, across shader switches and while the output window opens, closes and reopens; Syphon off with the window open keeps the window, and the server is gone within about 2 s. Creating the server on GLFW's context works.

**FFStudio.app:** builds with the Syphon framework, passes `--selftest`, and its Syphon output works in Resolume (checked 2026-10-24). `compile.py` then repairs the app's ad-hoc signature (`seal_mac_app`): PyInstaller left the app without a resource seal, and `Syphon.framework` (from a wheel, which can't hold symlinks) with real folders where a framework has symlinks. Now `codesign --verify --deep --strict dist/FFStudio.app` passes.

If creating the server fails, the log says `Syphon unavailable: …` and the button turns off. The likely spot is the context: `syphon.SyphonOpenGLServer(name)` uses the current NSOpenGLContext, which GLFW should have made current inside `gpu()`.

## 10. NDI output

The Studio tab's controls for sending now sit in a **Send** row under the preview: **Syphon**, **NDI**, and the NDI size menu (**1080p** / **720p**). NDI sends the shader as "<Mac name> (FFStudio)" at 30 fps over the network (`validate.NdiSender`: the frame is flipped and scaled on the GPU, read back asynchronously through two pixel buffers, and sent with cyndilib). On Windows every check passed (30 fps, no dropped frames, the right way up, at both sizes, alongside Spout, with and without the output window); the Mac needs:

1. `venv/bin/pip install -r requirements.txt` (adds `cyndilib`, which bundles the NDI runtime, and numpy).
2. From source: load a shader, click **NDI** (highlighted; the log says `NDI: sending "FFStudio" at 1920x1080, 30 fps.`). Receive it in Resolume (**Sources → NDI**) or NDI Video Monitor.

| Check | What should happen |
|---|---|
| Picture | The shader, the right way up, moving smoothly, at 1920×1080; **720p** in the menu switches it to 1280×720 while sending. |
| With Syphon | Both on: both receivers get the shader (Syphon at 60 fps, NDI at 30). Turning one off leaves the other. |
| No window | It keeps sending on the Queue tab and across shader switches, and with the output window opened and closed. |
| Off | The NDI source disappears from the receiver. |
| Self-test | `FFStudio --selftest <shader> <dir>` writes `sender Syphon: ok` and `sender NDI: ok` to `selftest.log`. |
| FFStudio.app | The same works in the packaged app. The first time, macOS asks for **Local Network** access (the spec's `NSLocalNetworkUsageDescription` / `NSBonjourServices`); allow it. If NDI sends from source but not from the app, that permission is the first suspect (System Settings → Privacy & Security → Local Network). `compile.py`'s signing step must still verify with cyndilib's `libndi` included. |

**Checked on the Mac (2026-10-24, M1 Max, macOS 14.8, cyndilib 0.1.3), with no code changes:** every row passed. From source, a script drove the GUI while separate NDI and Syphon receivers watched: the right way up at 1920×1080, and 1280×720 after choosing **720p** while sending; 30 fps with no dropped frames by NDI's own counters (each send about 0.5 ms); alongside Syphon at 60 fps, and turning Syphon off left NDI sending; sending carried on from the Queue tab, across a shader switch and while the output window opened and closed; the source was gone about 2 s after NDI was turned off. The self-test reports both senders `ok`, in the packaged app too. `FFStudio.app` bundles `libndi` and its licence files, still passes `codesign --verify --deep --strict`, and sends to Resolume (after allowing Local Network access), where the source is listed as "<Mac name> (FFStudio)". The app is now 71 MB (was 52 MB), mostly for numpy.

## 11. New look, Analyze, ← / →

The colours and fonts now come from one place, `src/theme.py`: dark surfaces in five steps from the window to a button, one accent (indigo, `#5b5bd6`) for the main actions (Build FFGL, Save settings) and for toggles that are on (output window, fullscreen, Syphon, NDI, Auto, Live; they were amber), and green / amber / red only for done / busy or warning / error, as in the build log's lines. `theme.apply()` patches CustomTkinter's theme before any widget exists, so most widgets take the colours without being told. On Windows the title bar is coloured to match (`colour_title_bar`, a no-op on macOS). No behaviour changed; every Windows GUI test still passes.

Fonts are the first one installed from a list per platform. On macOS the UI uses the system font (`.AppleSystemUIFont`) and code uses SF Mono, else Menlo. Check from source:

| Check | What should happen |
|---|---|
| Start-up | No errors; the window is a near-black blue-grey, not the old grey. |
| Fonts | The UI text is the system font (San Francisco), at the usual size. The code box and the log use a monospaced font. Section labels (PREVIEW, PARAMETERS, GPU, LOG) are small bold capitals. |
| Toggles | Syphon, NDI, Auto, Live and the output-window button turn indigo while on and grey when off. |
| Queue | The list's text, headings and selected row (dark indigo) are readable. |
| Tabs | The Queue / Studio labels are larger (15 px bold); the tab showing has a lighter fill and white text, the other dim text. Shift+Tab updates them too. |
| Studio top row | **+** (open a file) on the left; **Analyze**, **Build FFGL**, **Export ISF** on the right. There is no Process Code button: **Analyze** (and ⌘+Enter) processes the code when it changed, then measures the GPU load. |
| ← / → | Straight after switching to Studio (tab button, Shift+Tab or a double-click in the queue), with no output window, ← / → step through the queue. Not while typing in the code box or a text field, or after clicking a slider (it steps instead); clicking anywhere else releases those, and the arrows step the queue again. The code box's scrollbar keeps its focus. |
| Quick tab switch | Shift+Tab twice quickly leaves the tab it lands on showing, not blank (`_Tabs.set` no longer hides tabs 100 ms later). |
| FFStudio.app | The same in the packaged app. |

If a font comes out wrong (e.g. `.AppleSystemUIFont` not accepted by this Tk), change the macOS lists in `theme._UI_FAMILIES` / `theme._MONO_FAMILIES`.

**Checked on the Mac (2026-10-24, M1 Max, macOS 14.8, Tk 9.1):** every row passed. A script drove the GUI from source with screenshots: the UI font is `.AppleSystemUIFont` and code / the log use Menlo (SF Mono comes only inside Terminal and Xcode, so it isn't found); Syphon and NDI turn indigo while on; Shift+Tab to Studio, then → → ← stepped the queue, → in the code box didn't, and → stepped again once the focus left it; Shift+Tab twice 40 ms apart left Studio showing, and Queue repainted on the way back. The packaged app shows the new look, passes the self-test (both senders `ok`) and `codesign --verify --deep --strict`. One Mac fix: loading a shader logged "will export as <name>.dll"; it now says `.bundle` on the Mac.

## 12. OSC remote control (TouchOSC)

FFStudio now listens for OSC on UDP port 8000 and sends feedback to port 8001 (`src/osc_remote.py`, always on; the USER_MANUAL's *Remote control* section has the addresses). TouchOSC layouts are in `touchosc/` (`tools/build_touchosc.py` makes them). It needs python-osc:

1. `venv/bin/pip install -r requirements.txt` (adds `python-osc`).
2. Start FFStudio from source: the log says `OSC remote control: <address>, port 8000 (feedback to port 8001).`
3. In TouchOSC (on the Mac, an iPad or a phone), set any connection to UDP, host = the Mac's address (`127.0.0.1` on the Mac itself), send port 8000, receive port 8001, and open `touchosc/FFStudio_desktop.tosc` or `FFStudio_phone.tosc`.

| Check | What should happen |
|---|---|
| Connection | The layout's status line says **connected: FFStudio on <Mac name>**. |
| Transport | PLAY / RESTART / PREV / NEXT and the slideshow (AUTO, - / +) work and light up as in FFStudio. |
| Output | OUTPUT WINDOW and FULLSCREEN open and close them; the **Syphon** button (its label says Syphon on macOS) and NDI turn sending on and off. |
| Parameters | The shader's parameter names, values and faders appear; moving a fader moves the Studio tab's slider, and the other way round; switching shaders refills them. |
| FFStudio.app | The same in the packaged app. macOS asks for Local Network access the first time (the spec's `NSLocalNetworkUsageDescription` now mentions remote control): allow it, or a phone can't reach the app. `--selftest` writes `osc: ok`. |

**Checked on the Mac (2026-10-25, M1 Max, macOS 14.8, python-osc 1.10.2), with no code changes:** a script sent real OSC over UDP to FFStudio from source, to `127.0.0.1` and to the Mac's network address, and listened on port 8001: the log line, `/ping` → `/pong FFStudio on <Mac name>`, `/spout/name` = Syphon; PREV / NEXT (not on a button's release), PLAY, RESTART, AUTO and its seconds stepped and lit up; OUTPUT WINDOW, FULLSCREEN, Syphon, NDI and 720p switched with feedback; `/param/1` moved the slider, a slider change came back on `/param/1`, and switching shaders refilled the names. The packaged app writes `osc: ok`, passes `codesign --verify --deep --strict`, and answered the same messages from another process (Syphon and NDI on / off). Not yet checked: the TouchOSC layouts themselves, and a phone or iPad reaching the packaged app (the Local Network prompt).

**TouchOSC on the Mac (2026-10-25):** the layouts connect from TouchOSC on the Mac and on a phone. Two findings:

- **Only connection 10 worked.** The layouts sent and received only on connection 10. `tools/build_touchosc.py` now uses all ten connections (mask `1111111111`, and the script's `CONN`), so any connection can be set to FFStudio. The layouts were regenerated. Checked: the phone works on connection 1 (once the new layout was copied to it; TouchOSC keeps its own copy on each device).
- **Trackpad taps go missing** with the desktop layout in TouchOSC on the same Mac. Pressing the trackpad down works, and so does the phone. An OSC monitor in place of FFStudio showed that a missed tap sends nothing at all. This happened with PLAY (a toggle) as well as NEXT (momentary). Making the buttons toggles didn't help either: many taps still sent nothing. So it's TouchOSC's handling of macOS tap-to-click, which neither FFStudio nor the layout can fix. The USER_MANUAL says to press the trackpad down instead, or use a mouse.

## 13. Beta package: version, licence, notices, HTML manual

FFStudio now has a version number (`__version__` in `ffstudio/__init__.py`, `0.9.0-beta.1`), shown in the title bar, the log's first line and `selftest.log`; `FFStudio.spec` sets the app's `CFBundleShortVersionString` (`0.9.0`) and `CFBundleVersion` (`0.9.0-beta.1`) from it. After building, `compile.py` writes the package's documents into `dist/`: `LICENSE.txt` (copied from the repo), `THIRD_PARTY_NOTICES.txt` (`tools/make_notices.py`: the licences of what this platform's build bundles, read from PyInstaller's `build/FFStudio/PYZ-00.toc`) and `USER_MANUAL.html` (`tools/build_manual.py`). The spec also leaves out PyOpenGL's GLUT/GLE DLLs (Windows only; nothing changes on the Mac).

1. `venv/bin/pip install -r requirements.txt` (adds `markdown`, for `build_manual.py`).
2. `venv/bin/python compile.py`.

| Check | What should happen |
|---|---|
| Build | `compile.py` ends with "The rest of the package (sample shaders, TouchOSC layouts, licence, notices, manual) is there too."; `dist/` has `FFStudio.app`, `sample-shaders/` (99 CC0 shaders), `touchosc/`, `LICENSE.txt`, `THIRD_PARTY_NOTICES.txt`, `USER_MANUAL.html`. *(Since 2026-10-27, `compile.py` copies `sample-shaders/` and `touchosc/` too.)* |
| Notices | `THIRD_PARTY_NOTICES.txt` starts with the NDI terms, and its contents list has Python 3.12, Tcl/Tk (from its `license.terms`), **syphon-python** and **Syphon framework**, and no SpoutGL, Spout or GLEW. If `make_notices.py` stops with "no licence file for dist:LICENSE* (syphon-python)", the wheel has no licence file: find syphon-python's licence in its repository, save it as `tools/licenses/syphon-python.txt`, and change its entry in `COMPONENTS` to `lic:syphon-python.txt`. |
| Manual | `USER_MANUAL.html` opens in Safari with the contents on the left, follows light / dark mode, and its nested lists (e.g. under *Studio tab → Live preview*) are indented. |
| Version | The title bar says **FFStudio 0.9.0-beta.1**; Finder's *Get Info* on FFStudio.app shows version 0.9.0; `--selftest` writes `FFStudio 0.9.0-beta.1` as `selftest.log`'s first line. |
| Zip | Make the Mac zip on the Mac: put FFStudio.app, `touchosc/`, `sample-shaders/`, `USER_MANUAL.html`, `LICENSE.txt` and the Mac `THIRD_PARTY_NOTICES.txt` (all in `dist/` after a build) in one folder and compress it with Finder (*Compress*) or `ditto -c -k --keepParent <folder> <zip>`. Unzip a copy elsewhere and check that the app still opens and `codesign --verify --deep --strict` passes. |

**Checked on the Mac (2026-10-27, M1 Max, macOS 14.8):** every row passed, after two fixes to `tools/make_notices.py`. (1) The first build stopped at "Tcl/Tk's license.terms not found": Homebrew's Tcl/Tk 9.1 keeps Tcl's `license.terms` at the top of its prefix and Tk's (the one naming Apple) in `lib/tk9.1/demos`, not in the library folders the tool looked in; it now looks there too, and the notices carry both. (2) The list of sources at the end named every file in `tools/licenses`, so the Mac notices mentioned Spout (and Windows' would mention Syphon); it now lists only the files used. The notices start with the NDI terms and list Python 3.12.15, Tcl/Tk, syphon-python 0.2.0 and the Syphon framework, with no SpoutGL, Spout or GLEW. The manual opens in Safari with the contents on the left, in dark mode, with nested lists indented. The title bar says FFStudio 0.9.0-beta.1, Finder's version is 0.9.0, `selftest.log` starts with `FFStudio 0.9.0-beta.1`, and the Studio tab's new Save button suggests the shader's name with its extension and saves the code unchanged. A test zip made with `ditto` (30 MB) unpacked elsewhere still passes `codesign --verify --deep --strict` and the self-test (Syphon, NDI and OSC `ok`). The app is still 71 MB, and the plugins it builds are universal (x86_64 and arm64).

## 14. Sample shaders, package folders, save locations

Three changes from Windows (2026-10-27):
- `sample-shaders/` now holds the 99 CC0 Shadertoy shaders that ship with FFStudio (each starts with its Shadertoy link, author and licence). The old test shaders moved to `tests/corpus/`, which `tests/run_corpus.py` now uses by default.
- `compile.py` also copies `sample-shaders/` and `touchosc/` into `dist/`, so a build leaves the whole package there.
- Build FFGL, Export ISF and the Studio tab's save button always ask where to write (Queue and Studio tabs alike). Each dialog opens in the folder last chosen for that kind of file (plugins, ISF files, shader code), kept in `~/Library/Application Support/FFStudio/prefs.json`. With nothing remembered yet, plugins start in `~/Documents/Resolume Arena/Extra Effects` if it exists, else Documents. The app no longer writes to `~/Documents/FFStudio/output` (the command line still uses the project's `output/` unless given `--out`).

Run `venv/bin/python compile.py`, then check:

| Check | Expected |
|---|---|
| Corpus | `venv/bin/python tests/run_corpus.py --isf` gives OK=67, STATIC=12 of 79; with `--dir sample-shaders`, OK=99 of 99. |
| Package | `dist/` has `sample-shaders/` (99 files) and `touchosc/` (2 layouts) next to FFStudio.app. |
| Build folder | In FFStudio.app, **Build FFGL** in the Studio tab opens a folder dialog (in Extra Effects, or Documents). Choose a folder: the plugin goes there. Build again: the dialog opens in that folder. Cancel: nothing is built. |
| Queue | **Build FFGL** and **Export ISF** on the Queue tab ask once per batch; the build dialog opens in the folder chosen in the Studio tab. |
| Across sessions | Quit and reopen FFStudio: each dialog (build, Export ISF, save) opens in the folder chosen last. `prefs.json` lists them under `folders`. |
| Documents access | If macOS asks for access to Documents, **Allow** works and building still succeeds. |

**Checked on the Mac (2026-10-27, M1 Max, macOS 14.8), from source and in the build:** the corpus gives OK=67, STATIC=12 of 79, the fixtures 6 / 6, and `--dir sample-shaders` OK=99 of 99 (ISF OK=99). `compile.py` leaves `sample-shaders/` (99) and `touchosc/` (2) in `dist/`; the app passes the self-test and `codesign --verify --deep --strict` (71 MB). The folder logic was driven from source with the dialogs stubbed to record where they opened: the first Studio build opened in `~/Documents/Resolume Arena/Extra Effects` and the plugin went to the folder chosen; the next build opened there; Cancel built nothing and left Build FFGL usable; the Queue's Build FFGL asked once for two shaders, opening in the Studio tab's last folder; Queue Export ISF asked once (in Documents, with nothing remembered); Save opened in the shader's folder, then in the folder saved to last; `prefs.json` in `~/Library/Application Support/FFStudio` listed all three under `folders`. Still to check by hand in FFStudio.app: the real macOS folder dialogs and the Documents prompt.

**Plugin names from the sample shaders:** every file starts with `stoy_cc0_mrange_`, which is 16 characters, exactly what FFGL shows of a plugin name. So in Resolume every sample plugin is named `stoy_cc0_mrange_`, and in one batch the rest become `stoy_cc0_mrang_2`, `_3`, … (`build_ffgl.unique_plugin_name`); the queue build here named northernJourney's plugin `stoy_cc0_mrang_2.bundle`. Not Mac-specific.

**Fixed (2026-10-27):** the sample files are renamed to their short names (`stoy_cc0_mrange_rainbowWheel.txt` → `rainbowWheel.txt`); each file's header still gives its Shadertoy link, author (mrange) and licence (CC0). `--dir sample-shaders` still gives OK=99 of 99 (ISF OK=99), and `python -m ffstudio sample-shaders --to ffgl --test` builds all 99 plugins, each loading in the test host. Two pairs still share their first 16 characters: `logarithmicSpiralSpheres` / `logarithmicSpiralsTweaked` (`logarithmicSpira`) and `tunnelingThroughApollianFrac` / `tunnelingThroughGoldenFractal` (`tunnelingThrough`). In one batch the second of each is named `logarithmicSpi_2` / `tunnelingThrou_2`; built separately, both of a pair show the same name in Resolume.

## If something fails

- **Build failures (step 4):** most likely clang errors in `templates/ffgl/Plugin.cpp` or `FFStudioPlugin.h`. Fix them in `templates/ffgl/`, not in the cached workspace, which is overwritten on every build. The Windows build must keep working: if the fix can't be portable, use `#ifdef`, as `Plugin.cpp` already does for `localtime_s`.
- **GUI problems (step 6):** these are in `src/main_gui.py`, in `_build_queue_tab` (styling and bindings) and the queue methods below it. Keep Mac-only changes behind `sys.platform == "darwin"`, as the `<Button-2>` binding is.

Commit fixes on a branch, then merge into `main` and push, so they can be pulled back on Windows. Update `IMPROVEMENT_PLAN.md` and `TESTING_CHECKLIST.md` with the results.
