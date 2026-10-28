# Finishing the GLim rename

FFStudio became **GLim** (GL interactive media) on 2026-10-28, at version 0.9.0-beta.2. It was a clean rename: nothing reads or accepts the old name any more.

## What changed in the code (done on Windows, pushed)

| Item | Now |
|---|---|
| App | `GLim.exe` / `GLim.app`, built from `GLim.spec`. The Mac bundle ID is `com.busysquirrel.glim`, and the Windows AppUserModelID is `GLim.GLim`. |
| Python package and command line | `glim/`, run as `python -m glim` |
| Icon | A glimmer star (`assets/icon/make_icon.py`): `GLim.ico`, `GLim.icns`, `GLim.png` and `png/glim_N.png` |
| User folders | The cache is `%LOCALAPPDATA%\GLim` on Windows and `~/Library/Caches/GLim` on the Mac. Prefs are in `%APPDATA%\GLim` and `~/Library/Application Support/GLim`. Mac builds go to `~/Documents/GLim/output`. |
| Per-shader files | Settings are `<shader>.glim.json`, and channel lines are `// glim: iChannel0 = …` |
| Generated code | Uniforms and helpers use the prefix `glim_` (it was `ffm_`). The ISF inputs are `glimSpeed`, `glimMouse` and `glimBPM`, and the C++ macros are `GLIM_…`. The FFGL runtime is `GLimPlugin`, and plugin About text says "Made with GLim". |
| Mac plugin bundle IDs | `com.busysquirrel.glim.plugin.<name>.<id>` |
| Video output | The Spout, Syphon and NDI source is called **GLim** |
| OSC | Addresses are under `/glim/…`. The layouts are `touchosc/GLim_desktop.tosc` and `GLim_phone.tosc`. |
| Not changed | Plugin IDs, which come from each plugin's own name. Resolume sets keep finding plugins rebuilt under the same name. |

What this means for your existing files:
- **Shader settings:** settings saved as `<shader>.ffstudio.json` are no longer read. Rename any you want to keep to `<shader>.glim.json`. The same goes for `// ffstudio:` lines, which become `// glim:`.
- **Remembered folders:** the folders GLim remembers for builds, exports and saved code start empty.
- **Old ISF exports:** ISF files exported by FFStudio use the old `ffm` names. They work in ISF hosts as they are, but to convert one again, convert the original shader instead.

---

## 1. GitHub: rename the repo (once)

On github.com, go to **bzsqrl/FFStudio**, then **Settings → General → Repository name**, and change it to `GLim`. GitHub redirects the old URL, but point each checkout at the new one anyway (steps 2 and 3).

## 2. Windows: rename `C:\Users\beatf\Documents\ClaudeCode\FFStudio`

The `venv`, the CMake build workspace (which records the path to GLEW) and Claude Code's session history all depend on the folder's path. Everything else moves with the folder.

1. **Finish and close.** `git status` should be clean, with everything pushed. Close GLim, any Claude Code session, editor or terminal open in the folder, and Explorer windows inside it.
2. **Rename the folder and point git at the new repo:**
   ```powershell
   cd C:\Users\beatf\Documents\ClaudeCode
   Rename-Item FFStudio GLim
   cd GLim
   git remote set-url origin https://github.com/bzsqrl/GLim.git
   ```
3. **Recreate the venv** with the same Python (3.10):
   ```powershell
   Remove-Item -Recurse -Force venv
   & "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe" -m venv venv
   venv\Scripts\pip install -r requirements.txt
   venv\Scripts\pip install pyinstaller
   ```
4. **Delete the old user folders.** The first plugin build then sets up the new cache, which takes about a minute.
   ```powershell
   Remove-Item -Recurse -Force "$env:LOCALAPPDATA\FFStudio", "$env:APPDATA\FFStudio"
   ```
5. **Check that GLEW is still there:** `Test-Path deps\glew-2.2.0\include` should be True. It isn't in git; it moves with the folder.
6. **Test and rebuild:**
   ```powershell
   venv\Scripts\python tests\run_corpus.py --dir original-shaders --isf
   venv\Scripts\python tests\run_corpus.py --dir tests\fixtures --isf
   venv\Scripts\python compile.py
   dist\GLim.exe --selftest original-shaders\shapeForge.fs output\selftest
   ```
   Expect OK=30 of 30, then OK=6 and STATIC=6 for the fixtures. `output\selftest\selftest.log` should say `GLim 0.9.0-beta.2`, a `built …shapeForge.dll` line, and Spout, NDI and OSC ok.
7. **Update links:**
   - Pin `dist\GLim.exe` to the taskbar again.
   - In Resolume, re-select the Spout or NDI source, which is now called "GLim".
   - In TouchOSC, load `touchosc\GLim_*.tosc`, because the old layouts send `/ffstudio` messages.
   - If Resolume's plugin folder (*Preferences → Video*) points into the old folder, point it at the new one.
8. **Claude Code:** while Claude Code is closed, rename `C:\Users\beatf\.claude\projects\C--Users-beatf-Documents-ClaudeCode-FFStudio` to `…-GLim`, so `/resume` still finds this project's sessions.

## 3. Mac: pull, then rename the checkout

Replace `~/path/to` with wherever the checkout lives.

1. **Finish and close.** `git status` should be clean. Quit FFStudio.app, any Claude Code session, editor or Terminal tab in the folder, and Resolume.
2. **Point git at the new repo and pull:**
   ```bash
   cd ~/path/to/FFStudio
   git remote set-url origin https://github.com/bzsqrl/GLim.git
   git pull origin main
   ```
3. **Rename the folder:**
   ```bash
   cd ~/path/to && mv FFStudio GLim && cd GLim
   ```
4. **Recreate the venv** (Homebrew Python 3.12 with Tk, as in the README):
   ```bash
   rm -rf venv
   /opt/homebrew/bin/python3.12 -m venv venv
   venv/bin/pip install -r requirements.txt
   venv/bin/pip install pyinstaller
   ```
5. **Delete the old cache and prefs:**
   ```bash
   rm -rf ~/Library/Caches/FFStudio "$HOME/Library/Application Support/FFStudio"
   ```
6. **Test and rebuild:**
   ```bash
   venv/bin/python tests/run_corpus.py --dir original-shaders --isf
   venv/bin/python tests/run_corpus.py --dir tests/fixtures --isf
   venv/bin/python compile.py
   dist/GLim.app/Contents/MacOS/GLim --selftest original-shaders/shapeForge.fs /tmp/glim_selftest
   cat /tmp/glim_selftest/selftest.log
   ```
   Expect the same counts as on Windows, and a `built …bundle` line.
7. **Run the checks in MAC_UPDATE.md section 16.** They cover the new plugin bundle IDs in Resolume, Syphon, NDI and the icon.
8. **Tidy up:**
   - **The app:** replace FFStudio.app in Applications and the Dock with `dist/GLim.app`.
   - **Built plugins:** plugins in `~/Documents/FFStudio/output` can be moved to `~/Documents/GLim/output` or deleted.
   - **Plugins in Resolume:** where a rebuilt plugin replaces an old one in Resolume's plugin folder, **replace the old bundle; don't keep both.** They share a plugin ID.
   - **Claude Code:** rename the session folder in `~/.claude/projects/` that ends in `-FFStudio` so it ends in `-GLim`, while Claude Code is closed.

## 4. Afterwards (both machines)

- **Old zips:** delete the FFStudio zips in `_release/`. The Windows package is now `GLim-0.9.0-beta.2-windows.zip`; make the Mac one on the Mac.
- **Leftover folder:** delete the untracked `FFMaker-Mac/` leftover in the Windows checkout, if it's still there.
- **This file:** once both machines are done, delete it.
