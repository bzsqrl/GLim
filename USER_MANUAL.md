# FFMaker User Manual

**FFMaker** is a powerful utility designed to convert GLSL shaders (ISF, Shadertoy, and GLSL Sandbox formats) into native **FFGL (FreeFrameGL) plugins** for use in VJ software like Resolume, VDMX, and MadMapper.

---

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Quick Start](#quick-start)
3. [Supported Formats](#supported-formats)
4. [Interface Overview](#interface-overview)
    - [Queue Tab (Batch Processing)](#queue-tab-batch-processing)
    - [Single File Tab](#single-file-tab)
5. [How Parameter Extraction Works](#how-parameter-extraction-works)
    - [ISF Parameters](#isf-parameters)
    - [Shadertoy Constants](#shadertoy-constants)
6. [Shader Licensing and Ethics](#shader-licensing-and-ethics)
7. [Troubleshooting](#troubleshooting)


---

## Prerequisites

To use FFMaker, your system must have:
- **Windows OS** (Current version is optimized for Windows)
- **Python 3.10+**
- **CMake** (Installed and added to your System PATH)
- **Visual Studio Build Tools** (MSVC compiler)
- **Internet Connection** (On first run, FFMaker downloads the GLEW library automatically)

---

## Quick Start

1. **Launch the Application**: Run `src/main_gui.py`.
2. **Add Shaders**: Drag and drop your `.fs` (ISF) or `.txt` (Shadertoy) files into the window.
3. **Analyze**: In the "Single File" tab, you can paste code directly and click **Analyze Code** to see detected parameters.
4. **Build**: Click **Build Queue** or **Compile FFGL** to generate your plugins.
5. **Install**: The resulting `.dll` files will be placed in the `FFMaker/output/` folder. Copy these to your VJ software's plugin directory.

---

## Supported Formats

FFMaker automatically detects the format of your shader code:

| Format | File Ext | Detection Logic |
| :--- | :--- | :--- |
| **ISF** | `.fs` | Looks for the `/*{ JSON }*/` header. |
| **Shadertoy** | `.txt`, `.glsl` | Looks for `void mainImage(...)` or `iTime`. |
| **GLSL Sandbox** | `.glsl` | Looks for `uniform float time` and `uniform vec2 resolution`. |

> [!NOTE]
> **Multi-pass ISF shaders** are currently not supported for direct conversion. FFMaker will warn you if a shader requires multiple passes.

---

## Interface Overview

### Queue Tab (Batch Processing)
Designed for converting large libraries of shaders quickly.
- **Drag & Drop**: Drop multiple files or entire folders into the list.
- **Status Icons**:
  - `—` Pending
  - `⟳` Building (Compiling)
  - `✓` Success (DLL generated)
  - `✗` Error (Check the Build Log for details)
- **Build Queue**: Compiles all pending items sequentially.

### Single File Tab
Best for debugging or customizing a specific shader.
- **Code Editor**: Paste and edit your GLSL code.
- **Analyze Code**: Scans the shader and lists all parameters that will be exposed as sliders in your VJ software.
- **Output Name**: Specify a custom name for the resulting `.dll`.

---

## How Parameter Extraction Works

FFMaker makes your shaders interactive by exposing variables as FFGL parameters.

### ISF Parameters
FFMaker parses the standard ISF `INPUTS` block. It supports:
- `float` (with optional MIN/MAX/DEFAULT)
- `bool` / `boolean`
- `color` (mapped to RGBA)
- `point2D` (split into X and Y sliders)
- `long` (mapped to dropdown menus)
- `event` (trigger buttons)

### Shadertoy Constants
Since Shadertoy doesn't have a formal input header, FFMaker intelligently "promotes" top-level `const` declarations into UI sliders.
- **Example**: `const float size = 0.5;` becomes a slider named "size".
- **Speed Injection**: FFMaker automatically adds a **Speed** parameter to all Shadertoy shaders, allowing you to slow down or speed up time-based effects.
- **No Cap**: FFMaker extracts all detected constants and exposes them as sliders, giving you full control over the shader's internal parameters.

---

## Shader Licensing and Ethics

Shaders found on public platforms are the creative property of their respective authors. When using FFMaker to convert shaders, it is your responsibility to adhere to the license terms provided by the creator.

### Common Platform Policies
- **Shadertoy**: By default, code on Shadertoy is licensed under **CC BY-NC-SA 3.0** (Attribution-NonCommercial-ShareAlike) unless specified otherwise by the author in the code comments. 
- **ISF (Interactive Shader Format)**: Many ISF shaders are shared under open-source licenses (like MIT or BSD). Always check the `CREDIT` and `DESCRIPTION` fields in the ISF JSON header.
- **GLSL Sandbox**: Most content is public domain or CC0, but authors often include credit lines that should be preserved.

### Best Practices
1. **Check for License Headers**: Always look at the top of the shader source for license text or a link to a license.
2. **Give Credit**: If the shader has a `CREDIT` or `AUTHOR` field, preserve it. 
3. **Non-Commercial Use**: Many shaders are restricted to non-commercial use. Do not use generated FFGL plugins in commercial performances without verifying permission.
4. **Share Alike**: If you modify a shader and the license requires "Share Alike," ensure you share your modifications under the same terms.

---


## Troubleshooting

- **"CMake not found"**: Ensure CMake is installed and you can run `cmake --version` in a command prompt.
- **Blank Output in Resolume**:
  - Check the **Build Log** in FFMaker for GLSL compilation errors.
  - Ensure the shader doesn't use unsupported extensions or textures.
  - Some complex Shadertoy shaders require manual tweaking if they rely on specific `iChannel` inputs.
- **Build Fails**: If the build fails, the Build Log will show the exact error from the MSVC compiler. Common issues include syntax errors in the GLSL code or missing local dependencies.

---

*Manual generated for FFMaker v1.0*
