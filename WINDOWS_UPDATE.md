# Updating the Windows build after the Mac port

These steps bring a Windows checkout up to date with the work done on macOS, check the new features on Windows and rebuild `GLim.exe`. Run the commands in PowerShell from the GLim folder (the git checkout). If you're Claude on the Windows machine helping with this, read "Context" first.

## Context

Everything below was developed and tested on an M1 Mac (Resolume 7.21.3, MadMapper 6.0.1). The Windows code paths were left unchanged, but the shared code changed. None of it has been compiled or run on Windows yet.

Commits since the Windows build was last updated:

| Commit | What changed | Windows impact |
|---|---|---|
| `8fa3cea` | Mac plugin builds (Makefiles generator, universal binary, bundle naming and signing) | Mac-only branches in `glim/build_ffgl.py` and `templates/ffgl/CMakeLists.txt`. The `CMAKE_OSX_*` settings are ignored on Windows. |
| `6adeaff` | ISF export uses `glim_FragCoord` derived from `isf_FragNormCoord`, so output is upright in hosts with a top-left `gl_FragCoord` | Shared. Changes ISF output on every platform. |
| `8fbc698` | `tests/run_corpus.py --isf` reports `FLIP` when ISF output depends on `gl_FragCoord` origin | Shared test code. |
| `6c9ba10` | Platform-aware `GLim.spec` (Mac `.app`, Windows one-file `.exe` as before); `compile.py` runs `python -m PyInstaller`; Ctrl/⌘+Enter binding | `compile.py` now needs PyInstaller in the venv. |
| `20a83a3` | Deleted the old separate Mac folder | The pull deletes it. |
| `8317f96` | Per-channel sampler settings (filter / wrap / vflip) and tempo uniforms (`iBPM`, `iBeat`, `iBarPhase`) | **New C++ in `templates/ffgl/Plugin.cpp` and `GLimPlugin.h`, never compiled with MSVC.** |
| `6f724f2` | `.DS_Store` ignored | None. |

The new C++ is most likely to need a fix:
- GL sampler objects (`glGenSamplers`, `glBindSampler`, `glSamplerParameteri`) and `glGenerateMipmap`. On Windows these come from GLEW, which the FFGL SDK already initialises.
- The `SetBeatInfo(float bpm, float barPhase)` override.

The user manual describes the features in "Sampler settings" and "Tempo". `TESTING_CHECKLIST.md` ("Test batch v3") says what each test plugin should look like.

## 0. Requirements

These are probably still installed from earlier Windows builds:
- Git, and Python 3.10 or newer.
- CMake on the PATH (`cmake --version`).
- Visual Studio 2022 or Build Tools, with the **Desktop development with C++** workload.

## 1. Pull

Before pulling, check `git status` and commit or `git stash` any local changes. The pull deletes the old Mac folder; copy out anything of your own that's in it first.

```powershell
git checkout main
git pull origin main
git log --oneline -1
```

The last line should show the commit that added this file, or a later one.

## 2. Update the Python environment

```powershell
# only if venv\ doesn't exist yet:
python -m venv venv

venv\Scripts\python -m pip install --upgrade -r requirements.txt pyinstaller
```

## 3. Make sure GLEW is in `deps\`

Packaging the exe needs `deps\glew-2.2.0` inside the GLim folder (the git checkout). It isn't in git, so it should still be there from earlier builds.

```powershell
Test-Path deps\glew-2.2.0\lib\Release\x64
```

If that prints `False`:

```powershell
New-Item -ItemType Directory -Force deps | Out-Null
Invoke-WebRequest https://github.com/nigels-com/glew/releases/download/glew-2.2.0/glew-2.2.0-win32.zip -OutFile deps\glew.zip
Expand-Archive deps\glew.zip -DestinationPath deps
Remove-Item deps\glew.zip
```

## 4. Run the tests from source

```powershell
venv\Scripts\python tests\run_corpus.py --isf
venv\Scripts\python tests\run_corpus.py --isf --dir tests\fixtures
```

The first command runs the 79 sample shaders and the second the fixtures, including the new `shadertoy_sampler`, `shadertoy_buffer_sampler` and `shadertoy_tempo`. These render in GLim's preview; they don't build plugins.

**Expected:** every row is `OK`, and the ISF column has no `FAIL` or `FLIP`. On the Mac the result was 79/79, with 40/40 ISF exports OK.

`cc0_anotherBusShader` sometimes shows `DIFFn` in the ISF column. That shader reads uninitialised variables, so its output varies between runs. This isn't new.

## 5. Build plugins from the new fixtures

This step compiles the new plugin C++ with Visual Studio. The first build reconfigures the cached CMake workspace automatically, because `templates/ffgl/CMakeLists.txt` changed. That takes about a minute.

```powershell
foreach ($s in "shadertoy_sampler", "shadertoy_buffer_sampler", "shadertoy_tempo") {
  venv\Scripts\python src\main_gui.py --selftest tests\fixtures\$s.txt output\test_batch_v3_win
  Get-Content output\test_batch_v3_win\selftest.log
}
```

**Expected:** each log ends with a line starting `built` and a `.dll` path.

If CMake complains about the existing workspace, delete `%LOCALAPPDATA%\GLim\ffgl_workspace` and run the loop again.

## 6. Package GLim.exe

```powershell
venv\Scripts\python compile.py
dist\GLim.exe --selftest tests\fixtures\shadertoy_tempo.txt output\exe_selftest
Get-Content output\exe_selftest\selftest.log
```

**Expected:** `dist\GLim.exe` exists, and the log ends with `built …shadertoy_tempo.dll`.

Then open `dist\GLim.exe` normally and check that the window appears. Each single-pass Shadertoy channel in the editor should now have **filter** and **wrap** menus next to its source menu.

## 7. Check the plugins in Resolume

Copy the three `.dll` files from `output\test_batch_v3_win` into `Documents\Resolume Arena\Extra Effects` and restart Resolume. They should look the same as on the Mac:

| Plugin | What you should see |
|---|---|
| `shadertoy_sampler` | Three panels: a sharp checker, a soft tiled one, and one upside down |
| `shadertoy_buffer_sampler` | 16 small discs beside one large disc |
| `shadertoy_tempo` | A bar ramp and a beat flash that both follow Resolume's BPM |

ISF export has no Windows-specific code and was already checked in MadMapper, so it doesn't need testing again.

## If something fails

Most failures would show up in step 5, as MSVC compile errors in `Plugin.cpp` or `GLimPlugin.h`. Fix them in `templates/ffgl/`, not in the cached workspace, which is overwritten on every build. The Mac build must keep working too: if the fix can't be portable, use `#ifdef _WIN32`, as `Plugin.cpp` already does elsewhere.

Commit fixes on a branch, then merge into `main` and push, so they can be pulled back on the Mac.
