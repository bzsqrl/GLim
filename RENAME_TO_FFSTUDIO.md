# Finishing the FFStudio rename

FFMaker became **FFStudio** on 2026-10-23. The app, its windows, the built `FFStudio.exe` / `FFStudio.app` and the GitHub repo (`bzsqrl/FFStudio`) already use the new name. Two things still say FFMaker:

- **Part 1: legacy names in the code.** The `ffmaker` Python package, the `.ffmaker.json` settings files, the build cache folder and some internal names. They were kept so nothing broke during the rename. This is a code change, made once on either machine and pushed.
- **Part 2: the local folders.** The git checkout is still in a folder called `FFMaker` on each machine. Each machine renames its own folder.

The two parts are independent, so you can do either first, or only one. The smoothest order is Part 1 on Windows (commit and push), then Part 2 on Windows, then Part 2 on the Mac, where the pull picks up Part 1.

Nothing here is urgent. Git doesn't care what the folders are called, and every legacy name below works as it is.

---

## Part 1: remove legacy names from the code (once, on either machine)

The easiest way: open Claude Code in the project folder and ask it to *"do Part 1 of RENAME_TO_FFSTUDIO.md"*. The table lists what changes, and which old names must still be accepted so existing work keeps working.

| Item | Where | Change | Keep working |
|---|---|---|---|
| Python package `ffmaker/` | every `from ffmaker import …`, `FFStudio.spec` (`hiddenimports`), `compile.py`, tests, docs | `git mv ffmaker ffstudio` and update the imports. The command line becomes `python -m ffstudio`. | Nothing outside the repo imports it. Update any scripts or shortcuts of your own that run `python -m ffmaker`. |
| Build cache folder | `ffstudio/paths.py` (`cache_dir`): `%LOCALAPPDATA%\FFMaker` / `~/Library/Caches/FFMaker` | Name it `FFStudio`. | Delete the old cache folder afterwards. The first plugin build then recompiles the FFGL SDK (about a minute). |
| Settings files `<shader>.ffmaker.json` | `ffstudio/settings.py` (`SUFFIX`, `load`, `save`) | Save as `<shader>.ffstudio.json`. | **Load must fall back to `.ffmaker.json`** when no `.ffstudio.json` exists, or every shader you've set up loses its settings silently. Saving can then write the new name and delete the old file. Optionally rename the existing files in one go (commands below). |
| `// ffmaker:` channel directives | `ffstudio/convert.py` (`_CHANNEL_DIRECTIVE`), `shadertoy_project.py`, `USER_MANUAL.md`, `tests/fixtures/*` | Use `// ffstudio:` in the docs and fixtures. | **Keep accepting `// ffmaker:`.** It's in your shader files and any you've shared. Keep one fixture that uses `// ffmaker:` so this stays tested. |
| FFGL C++ runtime | `templates/ffgl/FFMakerPlugin.h`, `Plugin.cpp`, `CMakeLists.txt` (`FFMakerPlugin` class and target), `ffstudio/emit_ffgl.py` (`#include`, `FFM_PassSize`), `ffstudio/build_ffgl.py` (`FFMakerPlugin.dll` / `.bundle`, `.ffmaker_stamp`) | Rename to `FFStudioPlugin`. | Internal only. Plugin IDs come from each plugin's own name, so Resolume sets keep finding your plugins. Delete the build cache (row 2) so CMake starts fresh. |
| macOS plugin bundle IDs | `ffstudio/build_ffgl.py`: `com.ffmaker.plugin.<name>.<id>` | `com.ffstudio.plugin.…` | Resolume should identify plugins by their FFGL plugin ID, not the bundle ID, but check: rebuild one plugin, open a Resolume set that uses it, and confirm it still loads before rebuilding the rest. If it doesn't, keep `com.ffmaker`. |
| Smaller leftovers | `.gitignore` (`.ffmaker_cache/`), `validate.py` (`"ffstudio-validate"` is already new), the "former name" comments in `paths.py` / `convert.py`, `tests/fixtures/shadertoy_multipass.json` (`"username": "ffmaker"`) | Update. | — |
| Old notes and data | `IMPROVEMENT_PLAN.md`, `WINDOWS_UPDATE.md` (history), `scratch/`, `categorized_all_source.csv` (old file paths) | Leave as history, or delete what's no longer needed. | — |
| **Keep:** the `ffm_` prefix | generated uniforms and macros (`ffm_Time`, `ffmPhaseN`, …) | Don't rename. | It's in every plugin and ISF file already exported, and re-importing an exported ISF relies on it. |

Renaming existing settings files in one go, after the fallback above is in place (run in each folder of shaders; it skips files that already have a `.ffstudio.json`):

```powershell
# Windows (PowerShell)
Get-ChildItem -Recurse -Filter *.ffmaker.json | ForEach-Object {
  $new = $_.FullName -replace '\.ffmaker\.json$', '.ffstudio.json'
  if (-not (Test-Path $new)) { Rename-Item $_.FullName $new }
}
```

```bash
# macOS (Terminal)
find . -name '*.ffmaker.json' | while read -r f; do
  n="${f%.ffmaker.json}.ffstudio.json"; [ -e "$n" ] || mv "$f" "$n"
done
```

Afterwards, run the usual checks (`tests/run_corpus.py --isf`, the same with `--dir tests/fixtures`, `compile.py`, and the exe's or app's `--selftest`), then commit and push. The other machine needs `git pull`, a fresh build cache (row 2), and a rebuild.

---

## Part 2 on Windows: rename `C:\Users\beatf\Documents\ClaudeCode\FFMaker`

What depends on the folder's path:
- **The `venv`:** its launchers (`pip.exe`, `python.exe` shims) record the folder's full path.
- **The build workspace:** CMake recorded the full path to `deps\glew-2.2.0` inside the folder.
- **Claude Code's session history:** it's filed under the folder path.
- **Shortcuts and pins to `dist\FFStudio.exe`.**

Everything else, including git, `deps`, `dist`, `output` and your shaders, moves with the folder.

1. **Finish and close.** Commit and push, or stash, anything in progress (`git status` should be clean). Then close FFStudio, any Claude Code session, editor or terminal open in the folder, and Explorer windows inside it.
2. **Rename the folder** (PowerShell):
   ```powershell
   cd C:\Users\beatf\Documents\ClaudeCode
   Rename-Item FFMaker FFStudio
   cd FFStudio
   ```
   If Windows says the folder is in use, something from step 1 is still open.
3. **Recreate the venv** with the same Python (3.10):
   ```powershell
   Remove-Item -Recurse -Force venv
   & "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe" -m venv venv
   venv\Scripts\pip install -r requirements.txt
   venv\Scripts\pip install pyinstaller
   ```
4. **Reset the build workspace**, so CMake picks up the new path to GLEW:
   ```powershell
   Remove-Item -Recurse -Force "$env:LOCALAPPDATA\FFMaker\ffgl_workspace"
   ```
   If Part 1 is already done, delete the whole `%LOCALAPPDATA%\FFMaker` folder instead (the cache is now under `FFStudio`).
5. **Check that `deps\glew-2.2.0` is there** (it isn't in git; it moved with the folder): `Test-Path deps\glew-2.2.0\include`.
6. **Test and rebuild:**
   ```powershell
   venv\Scripts\python tests\run_corpus.py --isf
   venv\Scripts\python tests\run_corpus.py --isf --dir tests\fixtures
   venv\Scripts\python compile.py
   dist\FFStudio.exe --selftest sample-shaders\bare_fractalSymetry.txt output\selftest
   ```
   Expect 67 OK / 12 STATIC for the samples, 6 OK / 6 STATIC for the fixtures, and a `built …bare_fractalSymetry.dll` line in `output\selftest\selftest.log`. The first plugin build reconfigures the workspace and takes about a minute.
7. **Update links:** taskbar pins and shortcuts to `...\FFStudio\dist\FFStudio.exe`. If Resolume's FFGL plugin folder (*Preferences → Video*) points into the old `FFMaker` folder, point it at the new one.
8. **Claude Code (optional):**
   - **Memory:** it lives in `C:\Users\beatf\.claude\projects\C--Users-beatf-Documents-ClaudeCode\memory`, which is tied to the parent `ClaudeCode` folder, so it's unaffected.
   - **Session history:** it's filed under `C:\Users\beatf\.claude\projects\C--Users-beatf-Documents-ClaudeCode-FFMaker`. To keep `/resume` working for old sessions, rename that folder to `...-FFStudio` while Claude Code is closed.
   - **Then:** ask Claude to update its project memory for the new path.

---

## Part 2 on the Mac: rename the `FFMaker` checkout

The same idea as on Windows: the `venv`, the build workspace and Claude Code's session history depend on the path. Replace `~/path/to` below with wherever the checkout lives.

1. **Finish and close.** `git status` should be clean, with everything pushed or stashed. Quit FFStudio, any Claude Code session, editor or Terminal tab in the folder, and Resolume if it loads plugins from inside the folder.
2. **If you haven't yet, point git at the renamed repo** (once):
   ```bash
   cd ~/path/to/FFMaker
   git remote set-url origin https://github.com/bzsqrl/FFStudio.git
   ```
3. **Rename the folder:**
   ```bash
   cd ~/path/to
   mv FFMaker FFStudio
   cd FFStudio
   ```
4. **Recreate the venv** (Homebrew Python 3.12 with Tk, as in the README):
   ```bash
   rm -rf venv
   /opt/homebrew/bin/python3.12 -m venv venv
   venv/bin/pip install -r requirements.txt
   venv/bin/pip install pyinstaller
   ```
5. **Reset the build workspace:**
   ```bash
   rm -rf ~/Library/Caches/FFMaker/ffgl_workspace
   ```
   If Part 1 is already done, delete the whole `~/Library/Caches/FFMaker` instead.
6. **Pull, test and rebuild:**
   ```bash
   git pull origin main
   venv/bin/python tests/run_corpus.py --isf
   venv/bin/python tests/run_corpus.py --isf --dir tests/fixtures
   venv/bin/python compile.py
   dist/FFStudio.app/Contents/MacOS/FFStudio --selftest tests/fixtures/shadertoy_rate_params.txt /tmp/ffs_selftest
   ```
   Expect the same OK / STATIC counts as on Windows, and a `built …bundle` line in `/tmp/ffs_selftest/selftest.log`.
7. **Tidy up:**
   - **Apps:** replace any `FFMaker.app` or `FFStudio.app` in Applications and the Dock with the new `dist/FFStudio.app`.
   - **Plugins:** plugins built before the app rename are in `~/Documents/FFMaker/output`. Move what you want to keep, then delete it. New builds go to `~/Documents/FFStudio/output`.
   - **Resolume:** the plugins you copied to `~/Documents/Resolume Arena/Extra Effects` don't depend on any of this.
8. **Claude Code (optional):**
   - **Session history:** it's filed under `~/.claude/projects/` in a folder named after the checkout's path (slashes become dashes, ending in `-FFMaker`). Rename it to end in `-FFStudio` while Claude Code is closed, to keep `/resume` for old sessions.
   - **Memory:** if Claude Code was run from inside the checkout, its project memory is in that folder's `memory/`, so it moves along. Then ask Claude to update its memory for the new path.
