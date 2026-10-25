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
  sample-shaders/bare_fractalSymetry.txt sample-shaders/bare_lopyfrac3dOrthofractalEvolution.txt
```

**Expected:** for each shader, a `✓ … .fs` line, then a `✓ … .bundle` line followed by `test host: OK`; at the end, `4/4 converted.` (On Windows, the same command gave four `.dll` files, all `test host: OK`.)

If `sample-shaders/` on this Mac no longer has the two `bare_` files, take them from git: `git checkout -- sample-shaders/bare_fractalSymetry.txt sample-shaders/bare_lopyfrac3dOrthofractalEvolution.txt`.

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
3. In TouchOSC (on the Mac, an iPad or a phone), set connection 10 to UDP, host = the Mac's address (`127.0.0.1` on the Mac itself), send port 8000, receive port 8001, and open `touchosc/FFStudio_desktop.tosc` or `FFStudio_phone.tosc`.

| Check | What should happen |
|---|---|
| Connection | The layout's status line says **connected: FFStudio on <Mac name>**. |
| Transport | PLAY / RESTART / PREV / NEXT and the slideshow (AUTO, - / +) work and light up as in FFStudio. |
| Output | OUTPUT WINDOW and FULLSCREEN open and close them; the **Syphon** button (its label says Syphon on macOS) and NDI turn sending on and off. |
| Parameters | The shader's parameter names, values and faders appear; moving a fader moves the Studio tab's slider, and the other way round; switching shaders refills them. |
| FFStudio.app | The same in the packaged app. macOS asks for Local Network access the first time (the spec's `NSLocalNetworkUsageDescription` now mentions remote control): allow it, or a phone can't reach the app. `--selftest` writes `osc: ok`. |

**Checked on the Mac (2026-10-25, M1 Max, macOS 14.8, python-osc 1.10.2), with no code changes:** a script sent real OSC over UDP to FFStudio from source, to `127.0.0.1` and to the Mac's network address, and listened on port 8001: the log line, `/ping` → `/pong FFStudio on <Mac name>`, `/spout/name` = Syphon; PREV / NEXT (not on a button's release), PLAY, RESTART, AUTO and its seconds stepped and lit up; OUTPUT WINDOW, FULLSCREEN, Syphon, NDI and 720p switched with feedback; `/param/1` moved the slider, a slider change came back on `/param/1`, and switching shaders refilled the names. The packaged app writes `osc: ok`, passes `codesign --verify --deep --strict`, and answered the same messages from another process (Syphon and NDI on / off). Not yet checked: the TouchOSC layouts themselves, and a phone or iPad reaching the packaged app (the Local Network prompt).

## If something fails

- **Build failures (step 4):** most likely clang errors in `templates/ffgl/Plugin.cpp` or `FFStudioPlugin.h`. Fix them in `templates/ffgl/`, not in the cached workspace, which is overwritten on every build. The Windows build must keep working: if the fix can't be portable, use `#ifdef`, as `Plugin.cpp` already does for `localtime_s`.
- **GUI problems (step 6):** these are in `src/main_gui.py`, in `_build_queue_tab` (styling and bindings) and the queue methods below it. Keep Mac-only changes behind `sys.platform == "darwin"`, as the `<Button-2>` binding is.

Commit fixes on a branch, then merge into `main` and push, so they can be pulled back on Windows. Update `IMPROVEMENT_PLAN.md` and `TESTING_CHECKLIST.md` with the results.
