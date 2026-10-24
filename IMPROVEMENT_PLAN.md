# FFStudio Improvement Plan

*Written 2026-10-20 from a code review plus a compile audit of the 79 files in `sample-shaders/`.*

## Status (updated 2026-10-20)

**Phase 0 and most of Phase 1 are done.** Results on the 79 samples:
- **All 79** convert, compile on the GPU, and render. The old pipeline managed 18.
- **All 79** build into DLLs that load and render in FFStudio's test host.
- **All 40** non-ISF samples export ISF that compiles in an ISF host emulator.

Not yet checked inside Resolume or MadMapper.

**New code layout:**
- `ffstudio/`: the core library
  - `glsl.py`: tokenizer
  - `convert.py`: front-ends and transformations
  - `emit_ffgl.py`, `emit_isf.py`: output writers
  - `validate.py`: GPU compile/render checks
  - `isf_host.py`: ISF host emulator
  - `build_ffgl.py`: builds plugins in a cached CMake workspace
  - `ffgl_host.py`: test host
  - `__main__.py`: command line
- `templates/ffgl/`: the fixed C++ plugin runtime, driven by a generated `ShaderData.h`
- `tests/run_corpus.py`: regression runner. Writes thumbnails and `report.json` to `tests/out/`.
- `src/main_gui.py`: the existing GUI, now running on the new core

**Already done ahead of schedule** (Phase 2 / Phase 4 items):
- ISF multi-pass and persistent/float buffers
- ISF transitions as FFGL mixers
- Cached-SDK builds (about 2 s per plugin)

**Done since the first test batch** (user confirmed v1 works in Resolume and MadMapper):
- **Embedded textures:** ISF `IMPORTED`, Shadertoy channel directives, and a noise fallback for missing files.
- **Audio:** an FFGL FFT buffer parameter drives ISF `audio`/`audioFFT` inputs and Shadertoy sound channels.
- **Multi-buffer Shadertoy:** Common plus Buffers A–D from sectioned text or Shadertoy JSON. These export to ISF `PASSES`.
- **ISF `.vs` vertex shaders.**
- **ISF round-trip regression test:** each export is re-imported and its render compared with the original. It found and fixed:
  - uninitialised variables (FFStudio now zero-initialises them, as browsers do);
  - the ISF entry point when a file defines both `main()` and `mainImage()`;
  - user macros shadowing ISF built-ins;
  - `gl_FragColor` inside `#define` lines.
- Test batch v2 is in `output/test_batch_v2`.

**Phase 3 (GUI) and the Windows part of Phase 4 are done** (user confirmed batch v2):
- **Live GPU preview** (`ffstudio/validate.Previewer`, shared with the offline renderer).
- **Parameter editor:** expose/hide, label, range, default.
- **Shadertoy channel pickers.**
- **Per-shader settings** in `<shader>.ffstudio.json`, used by queue, CLI and ISF export. ISF sources get their headers rewritten from these settings.
- **Packaged `.exe` verified:**
  - builds plugins headlessly (`FFStudio.exe --selftest <shader> <dir>`);
  - GLEW is bundled;
  - the SDK is copied to a stable cache path so the workspace isn't reconfigured every launch.
**macOS port done** (M1 Max, macOS 14, Resolume 7.21.3, MadMapper 6.0.1):
- Builds with only the Command Line Tools (Makefiles generator, not Xcode).
- Plugins are universal (arm64 + x86_64) `.bundle`s, macOS 10.15+, each with its own bundle identifier, signed ad hoc. The binary is named after the bundle, because Resolume opens `Contents/MacOS/<bundle name>`.
- Corpus: all 79 convert, compile and render on the Apple GPU. Plugins load in Resolume for Mac.
- ISF exports no longer use `gl_FragCoord` (MadMapper on macOS puts its origin at the top). The corpus `--isf` run now fails an export with `FLIP` if its output depends on `gl_FragCoord`'s origin.
- `FFStudio.spec` builds `dist/FFStudio.app` on macOS. It writes output to `~/Documents/FFStudio/output` and finds Homebrew's CMake when opened from Finder. Verified with `--selftest`.
- Not done: a universal or Intel build of the app itself (Homebrew Python is arm64 only), and Developer ID signing/notarization for distribution.

**Done since the Mac port:**
- **Per-channel sampler settings** (`filter`, `wrap`, `vflip`) from Shadertoy JSON, channel directives and the editor's channel menus. FFGL plugins and the preview use GL sampler objects (a buffer can be read with different settings in different passes; mipmapped buffers rebuild their mipmaps after each render). ISF exports emulate `nearest` and `repeat` in the shader.
- **Tempo:** `iBPM`, `iBeat`, `iBarPhase` from FFGL `SetBeatInfo` (120 BPM fallback); ISF exports get a BPM slider. The test host can send beat info (`smoke_test(..., beat=(bpm, phase))`).
- **Windows sync of the Mac port** passed with no code changes (MSVC built the sampler and tempo C++ as is).
- **`#define` channels:** Shadertoy channels used only inside macro bodies are now declared and wired (`ac835b5`).
- **Queue rewrite** (`5a72770`, `100a29c`): a native `ttk.Treeview`, so 800+ files load in under a second. Type detection and queue ISF export run in the background. Build/Export Selected, Delete to remove, a right-click menu.
- **Sliders multiplied by time no longer scrub in FFGL** (`2892180`): `time * slider` becomes a running total (`ffm_phaseN`, `FFM_PHASES`) that the plugin and preview keep. ISF exports keep the plain product. A hidden persistent-buffer version for ISF failed in MadMapper (several shaders blank; Speed still jumped) and was reverted.
- **Mac sync of the Windows work** (`MAC_UPDATE.md`) passed: corpus and fixtures match the Windows results, clang built the phase C++ as is, test batch v4 passes the test host and was confirmed in Resolume and MadMapper. The queue handles 790 files on macOS (rows in 0.1 s, types in ~7 s in the background). Added Control-click for the queue menu on macOS.
- **Plugin identity on the Mac:** Resolume saves FFGL plugins by plugin ID (`uniqueTypeId`), not bundle ID, so changing a plugin's bundle ID doesn't affect saved sets (checked by swapping builds under a saved set).
- **Studio parameter panel on the Mac** (`MAC_UPDATE.md` step 6, 2026-10-24): the flat Tk/ttk parameter rows and channel menus, GPU load (timer queries work on the M1 Max), the button click fixes and the output window all work on macOS with no changes.
- **Syphon output on the Mac** (`MAC_UPDATE.md` section 9, 2026-10-24): works from source with no changes (1920×1080, right way up, 60 fps, with and without the output window, server gone when turned off). The packaged `FFStudio.app` sends to Resolume too. `compile.py` re-signs the app after PyInstaller (`seal_mac_app`), so `codesign --verify --deep --strict` passes, with the bundled `Syphon.framework` included.
- **Queue Reset Status:** sets built/failed rows (or just the selected ones) back to Pending, so a queue can be converted again without reloading it.

**Next:**
1. **Smaller items:**
   - Shadertoy cubemap passes;
   - letting the preview load a real audio file.

## 1. Baseline: what works today

I ran every sample through the current pipeline (`parser.parse_code` → `builder.build_plugin`, stopped before CMake). Each generated fragment shader was then compiled with the real GPU driver (RTX 4060, NVIDIA 581.80, GL 4.1 core context). NVIDIA's compiler is one of the more forgiving ones, so these numbers are probably better than other GPUs would give.

| Input type | Samples | FFGL shader compiles | ISF export compiles |
|---|---|---|---|
| ISF generator (`.fs`) | 29 | **0** (1 rejected as multi-pass) | n/a |
| ISF effect / transition | 10 | **0** (2 rejected as multi-pass) | n/a |
| Shadertoy (as detected) | 33 | 13 | 29 |
| GLSL Sandbox (as detected) | 7 | 5 | 7 |
| **Total** | **79** | **18 (23%)** | 36 of 40 |

A shader that compiles still isn't proven to look right. See the runtime bugs in §2.3: no effect plugin can work at the moment, even after it compiles.

## 2. Root causes, in order of impact

### 2.1 ISF → FFGL fails every time: two `main()` functions
The old wrapper template always emits its own `void main()`. ISF shaders also have a `void main()`, and the builder only bridges Shadertoy-style `mainImage`. Every one of the 36 ISF samples that got past the parser fails with `function "main" is already defined`. For 28 of them it's the first error the compiler reports.

Other ISF failures hidden behind that one:
- **Texture macros expanded with regex.** `IMG_NORM_PIXEL(img, vec2(a, b))` gets cut at the first `)` and produces broken code (`vv_brokenLCD`: `textureLod(sampler2D, float)`).
- **Missing ISF built-ins:** `DATE`, `IMG_SIZE`, `IMG_THIS_NORM_PIXEL`, `*_LOD` variants, `PASSINDEX`.
- **Transitions** (`startImage` + `endImage`): only the first image is wired up, so `endImage` is undefined.
- **Shadertoy-style ISF files** (the `stoy_*.fs` set): globals like `float iTime = TIME;` and `iGlobalTime` / `iMouse` / `iChannelN` aren't handled.
- **`IMPORTED` images** (5 samples) are ignored.

### 2.2 Shadertoy / Sandbox: const promotion breaks code
`parse_shadertoy` turns `const float x = …;` into a slider using one regex, which causes three problems:
1. **The original declaration is never removed** in the FFGL path, so the shader declares `x` twice (`declaration of "speed" conflicts…`). This is the most common Shadertoy failure.
2. **No scope awareness.** Consts *inside functions* get promoted too (`cc0_alienSkin`: `aa`, `pp`, `rr` are function locals).
3. **Dependants break.** When a promoted const is used in another const, in an array size, or in a global initializer, the result is `non constant expression in initialization`.

Smaller issues:
- `IndexError` crash on `llm_amoebaDance.txt`.
- Format detection reads only the first 2 KB, so files with long license headers can be misdetected.

### 2.3 The FFGL runtime template has bugs, even when the shader compiles
- **Effects get no input image.** `/* FFM_FX_TEXTURE_BIND */` is never replaced, so the host texture is never bound, and `MaxUV` is never set (it stays `0,0`, so every sample reads one texel).
- **Time is fake.** It goes up by `0.016` each frame instead of following the clock, so speed changes with frame rate. `iTimeDelta` is never sent (the code sets `fTimeDelta`, which isn't a uniform).
- **The Speed slider makes the animation jump.** It's applied as `iTime = fTime * Speed`, so moving the slider jumps the shader backwards or forwards in time. It should add up scaled time on the CPU each frame instead.
- **`long` (dropdown) params can't work.** A float is sent to a `uniform int`, which is a GL error and the value never changes. They should be `ParamOption` dropdowns with the ISF labels.
- **Color defaults are ignored.** Every color starts white.
- **Unneeded value remapping.** float min/max is mapped through a 0–1 "trampoline" even though FFGL2 `ParamRange` supports real ranges, so Resolume shows meaningless 0–1 values.
- `iMouse` is always 0 and `iDate` is always 0. In ISF export, `iDate` is hard-coded to 2026-05-13.

### 2.4 Structural problems
- **Text replacement instead of host emulation.** The code rewrites shader text with dozens of regexes. Every new shader style needs a new regex, and fixes collide with each other (that's where the old round-trip marker comments came from).
- **No validation before building.** The tool runs a full CMake/MSVC build and reports "success" without ever compiling the GLSL. Shader errors only show up as a blank clip in Resolume.
- **Slow builds.** Every plugin rebuilds the whole FFGL SDK through CMake, and failed builds leave their folders behind (`boilerplates/` holds about 13,000 leftover `build_temp_*` files). In the packaged `.exe`, builds are written into PyInstaller's temporary extraction folder.
- ~~**The Mac port is a forked copy** of `src/` in a separate Mac folder, so the two versions will drift apart.~~ Fixed: one codebase runs on both.
- Multi-pass is rejected with the message "FFGL does not support it". That's wrong: plugins can render into their own FBOs (`ffglex::FFGLFBO`).

## 3. Target architecture

```
          ┌──────────── detect ────────────┐
 source → │ ISF │ Shadertoy │ Sandbox │ raw │ → ShaderIR → emit_ffgl → validate → package (.dll / .bundle)
          └────────────────────────────────┘      │      → emit_isf  → validate → .fs
                                                  └ passes, inputs, textures, needs(time/mouse/audio/bpm)
```

1. **GLSL tokenizer with scope tracking** (Python, no full AST). It knows brace depth, global vs local declarations, function signatures, comments, strings, and preprocessor lines. All rewrites go through it. Regexes stay only for simple, safe patterns like the `main` signature.
2. **ShaderIR**: a single internal description of the shader. It holds the dialect, the code body, typed inputs with real ranges, passes/buffers (persistent, float, size), image inputs (host, imported, buffer), and the host features the shader needs.
3. **Host emulation instead of rewriting.** Each emitter writes a *preamble* that recreates the source host's environment, and leaves the user's code almost untouched:
   - ISF in FFGL: uniforms `TIME`, `RENDERSIZE`, `DATE`…, a global `isf_FragNormCoord`, and `IMG_*` as **GLSL preprocessor macros**. The GPU's own preprocessor handles nested parentheses correctly. `main` is renamed to `isf_main`, and `gl_FragColor` is mapped with `#define`.
   - Shadertoy in FFGL and ISF: the `i*` uniforms and a call to `mainImage`.
   - Dialect normalization: `texture2D` etc. turn into `texture`, and `#version`, `precision` and ES-only `#extension` lines are removed. Identifiers that are reserved in GLSL 4.10 but valid in ES (`sample`, `input`, `output`, `filter`, `common`, `smooth`, `flat`, `buffer`, `active`, `partition`…) are renamed. Global initializers that aren't constant move into an init function.
4. **Validation built into the pipeline.** Compile with the GPU driver and with `glslangValidator` (stricter, closer to AMD/Intel/Mac behavior), then render one test frame (catches black output and NaN). Errors are mapped back to the user's original line numbers. The compiler also decides param promotion: promote consts, compile, drop any param the errors point at, and repeat.

## 4. Phased roadmap

### Phase 0: Test harness *(a prototype already exists)*
- Turn the audit script into `tests/` plus a CLI (`ffstudio convert <file> --to ffgl|isf [--check]`).
- Pass/fail report per sample covering parse, FFGL compile, ISF compile, and render-not-black.
- Keep a scoreboard so every later change is measured against the 18/79 baseline.

### Phase 1: Correct single-pass conversion *(biggest gain)*
- Tokenizer and ShaderIR. ISF host-emulation preamble for FFGL, which removes the double-`main` error from all 36 ISF samples.
- Rewrite const promotion: top-level only, replace the declaration, check dependants, back off when the compiler complains. Promote `const int` as integer sliders where it's safe (not when used as an array size or loop bound).
- Dialect normalization (see §3.3).
- Template fixes: bind input texture and set MaxUV, real clock time, accumulated Speed, `iTimeDelta`/`iFrame`/`iDate`, `ParamRange` with real min/max, `ParamOption` for `long`, color defaults, Mouse X/Y params feeding `iMouse`.
- ISF export fixes: `DATE`, mouse as a `point2D` input, each `iChannelN` as its own image input, `iChannelResolution` mapped to `IMG_SIZE`, `"ISFVSN": "2"`.
- **Goal:** every single-pass sample compiles and renders for both targets.

### Phase 2: Feature coverage
- **Multi-pass and feedback buffers** in FFGL through FBO ping-pong (ISF `PASSES`/`PERSISTENT`/`FLOAT`, Shadertoy Buffer A–D). Shadertoy buffers also map directly to ISF `PASSES` in the other direction.
- **Textures:** embed ISF `IMPORTED` images and Shadertoy iChannel images in the plugin. Generate Shadertoy-style noise textures procedurally.
- **ISF transitions as Resolume mixer plugins** (`startImage`/`endImage`/`progress` become an FFGL mixer with two inputs).
- **Audio:** ISF `audio`/`audioFFT` and Shadertoy sound input mapped to FFGL2 FFT buffer params.
- Optional BPM / bar-phase uniforms from `SetBeatInfo` for tempo-synced shaders.

### Phase 3: GUI workflow
- Live preview panel with the same renderer used for validation.
- Parameter editor: choose which params to expose, rename them, and set ranges and defaults before building.
- Clear per-shader diagnostics in the queue (with the reason) instead of a generic "Build failed".

### Phase 4: Build and packaging
- Short term: compile the FFGL SDK once and cache it, and use a per-user build/cache folder (`%LOCALAPPDATA%\FFStudio`). Always clean up.
- Longer term: a **prebuilt, data-driven runtime plugin**. The shader, params and textures are stored as data inside a ready-made DLL (Windows resource) or bundle (Mac `Resources/`, then an ad-hoc codesign). End users wouldn't need MSVC/CMake/Xcode, and builds would take under a second.
- Merge the Mac port back into one codebase with platform-specific build backends.
- Update the bundled FFGL SDK snapshot (currently dated 2023-06) to the latest `resolume/ffgl` master.

## 5. Things I can't verify alone
- **Runtime behavior inside Resolume 7.21.3+ and MadMapper.** I can prove that shaders compile and render offline, but loading plugins in the hosts needs you.
- **MadMapper's exact ISF/GLSL dialect,** which may be stricter than the ISF reference implementation.
