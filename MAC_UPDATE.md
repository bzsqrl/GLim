# Updating the Mac build after the Windows work

These steps bring a Mac checkout up to date with the work done on Windows, check the new features on macOS and rebuild `FFStudio.app`. Run the commands in Terminal from the FFMaker folder (the git checkout). If you're Claude on the Mac helping with this, read "Context" first.

## The app is now FFStudio

FFMaker was renamed **FFStudio**, and its **Single File** tab is now **Studio**. After the pull, `compile.py` builds `dist/FFStudio.app` (bundle id `com.ffstudio.app`), and plugins are written to `~/Documents/FFStudio/output` (plugins built earlier stay in `~/Documents/FFMaker/output`). The old `dist/FFMaker.app` and any copy in Applications can be deleted. Unchanged, so existing work keeps working: `<shader>.ffmaker.json` settings, `// ffmaker:` channel directives (`// ffstudio:` works too), plugin IDs, the `ffmaker` Python package (`python -m ffmaker`), the `~/Library/Caches/FFMaker` build workspace and the local folder name (the GitHub repo itself is now `bzsqrl/FFStudio`; see step 1).

## Context

Everything below was developed and tested on Windows 11 (RTX 4060, Resolume 7.21.3). The Mac-only code paths were not changed, but shared code was. None of it has been compiled or run on macOS yet, except possibly `100a29c` (see the table).

Commits since the Mac was last in sync (`6e47677`, "Add Windows update instructions"):

| Commit | What changed | Mac impact |
|---|---|---|
| `ac835b5` | Shadertoy channels used only inside a `#define` (`#define FFT(a) texture(iChannel1, …)`) are now declared and wired. Before, these failed with `undefined variable "iChannel1"`. | Shared converter code. |
| `5a72770` | The queue is now a native `ttk.Treeview` instead of one CustomTkinter widget per row. 800+ files load in under a second, where before they froze the window and left rows blank. File types are detected in the background, and the queue's **Export ISF** runs off the UI thread. The build log keeps its last 5,000 lines. New: **Build Selected / Export Selected**, Delete/Backspace to remove, a right-click menu, and double-click to open a file. | **GUI, never run on macOS.** The list uses the `clam` ttk theme with custom colours and the font "Segoe UI", which macOS replaces with a fallback. |
| `100a29c` | Queue review fixes: worker threads no longer read Tk variables, rows removed mid-build are skipped, and right-click is bound to `<Button-2>` on macOS. | The `<Button-2>` binding is Mac-only. It may already be on this Mac if it was committed there. |
| `2892180` | **Sliders multiplied by time no longer scrub.** `iTime * speed`, `vec3(rx, ry, rz) * iTime` and the like become running totals (`ffm_phaseN`). The plugin keeps them (`FFM_PHASES`), adding slider × frame time every frame. ISF exports still use the plain product, so they still jump in ISF hosts. | **New C++ in `templates/ffgl/Plugin.cpp` and `FFMakerPlugin.h`, never compiled with clang.** |

The new C++ is small and should be portable: a `std::vector<double>` of totals, a loop over `FFM_PHASES` in `ProcessOpenGL`, and one `glUniform1f` per total per pass.

The GUI is the most likely place for Mac-specific problems. See step 6.

## 0. Requirements

These should still be installed from the Mac port:
- **Xcode Command Line Tools:** `xcode-select -p` prints a path.
- **Homebrew Python 3.12 with Tk, and CMake:** `brew list python@3.12 python-tk@3.12 cmake`.

## 1. Pull

Before pulling, check `git status`, and commit or `git stash` any local changes.

The GitHub repo is now `bzsqrl/FFStudio` (renamed from `FFMaker`). GitHub redirects the old address, but point the checkout at the new one first (once):

```bash
git remote set-url origin https://github.com/bzsqrl/FFStudio.git
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

This compiles the new plugin C++ with clang, then loads each plugin in FFStudio's test host. The first build reconfigures the cached workspace (`~/Library/Caches/FFMaker`), because the runtime template changed. That takes about a minute.

```bash
venv/bin/python -m ffmaker --to both --test --out output/test_batch_v4 \
  tests/fixtures/shadertoy_rate_params.txt tests/fixtures/shadertoy_define_channel.txt \
  sample-shaders/bare_fractalSymetry.txt sample-shaders/bare_lopyfrac3dOrthofractalEvolution.txt
```

**Expected:** for each shader, a `✓ … .fs` line, then a `✓ … .bundle` line followed by `test host: OK`; at the end, `4/4 converted.` (On Windows, the same command gave four `.dll` files, all `test host: OK`.)

If `sample-shaders/` on this Mac no longer has the two `bare_` files, take them from git: `git checkout -- sample-shaders/bare_fractalSymetry.txt sample-shaders/bare_lopyfrac3dOrthofractalEvolution.txt`.

If CMake complains about the existing workspace, delete `~/Library/Caches/FFMaker` and run the command again.

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

**Parameter panel (since the efficiency pass).** In the **Studio** tab, the parameter rows and Shadertoy channel menus now use plain Tk/ttk widgets (`src/fast_widgets.py`), which have flat corners. They were only tested on Windows, so check them here:

| Check | What should happen |
|---|---|
| Look | Dark rows, readable text, blue slider handles. The checkboxes and entries are dark, not white. |
| Sliders | Dragging moves the value. Clicking the track jumps there and can keep dragging. Right-click (or Control-click) resets. After a click, ← / → step the value and the handle turns amber. |
| Menus | **long** parameters and the channel / filter / wrap menus open a menu on click, and a choice applies. |
| GPU load | **Analyze** (or **Live** on, then loading a shader) shows "measuring…", then e.g. **29% of 60 fps** with ms/frame under the preview. With Live off, switching shaders measures nothing. **Analyze** on the Queue tab fills the GPU @1080p column; clicking that heading sorts by it. With the output window (**⧉**) open the readout says "live in the output". (OpenGL timer queries; untested on macOS.) |
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

## If something fails

- **Build failures (step 4):** most likely clang errors in `templates/ffgl/Plugin.cpp` or `FFMakerPlugin.h`. Fix them in `templates/ffgl/`, not in the cached workspace, which is overwritten on every build. The Windows build must keep working: if the fix can't be portable, use `#ifdef`, as `Plugin.cpp` already does for `localtime_s`.
- **GUI problems (step 6):** these are in `src/main_gui.py`, in `_build_queue_tab` (styling and bindings) and the queue methods below it. Keep Mac-only changes behind `sys.platform == "darwin"`, as the `<Button-2>` binding is.

Commit fixes on a branch, then merge into `main` and push, so they can be pulled back on Windows. Update `IMPROVEMENT_PLAN.md` and `TESTING_CHECKLIST.md` with the results.
