# FFMaker macOS Porting Plan

This document outlines the strategy for porting **FFMaker** from Windows to macOS, specifically targeting Apple Silicon (M1/M2/M3) machines.

---

## 1. Environment Setup (macOS)

On the target MacBook Pro, run the following to set up the build environment:

```bash
# Install Homebrew if not already present
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install dependencies
brew install python cmake glew
brew install --cask xcode
# Install tkdnd for drag-and-drop support in Python
brew install tkdnd
```

Install Python packages:
```bash
pip install customtkinter pillow tkinterdnd2 pyinstaller
```

---

## 2. Core Architectural Changes

### 2.1 Plugin Format
- **Windows**: Produces `.dll` files.
- **macOS**: FFGL plugins are typically Mach-O Bundles (`.bundle`).
- **Architecture**: Targeting `arm64` (Apple Silicon). For maximum compatibility, we can build `universal2` (x86_64 + arm64).

### 2.2 Graphics API
- **Windows**: Links against `opengl32.lib`.
- **macOS**: Uses the `OpenGL` and `AppKit` frameworks. Note that OpenGL is deprecated on macOS but still supported for FFGL plugins in hosts like Resolume.

---

## 3. Component Modifications

### 3.1 `src/paths.py`
The path resolution needs to handle macOS directory structures. PyInstaller on Mac uses the same `_MEIPASS` mechanism, but `sys.executable` points to a path inside an `.app` bundle.

### 3.2 `src/builder.py`
- **Compiler Calls**: Switch from MSVC-style CMake flags to Clang/Xcode flags.
- **GLEW Handling**: Instead of downloading a Win32 ZIP, use the system-installed GLEW from Homebrew or a macOS-compiled version.
- **Bundle Output**: Update the CMake properties to generate a `.bundle` with the correct extension.

### 3.3 `boilerplates/ffmaker_plugin/CMakeLists.txt`
Modified to support macOS Frameworks and Bundle output.

---

## 4. Porting Tasks

1.  **Modify `builder.py`**:
    - Update `_run_cancellable` to use Unix-friendly shell commands.
    - Change `opengl32` to `-framework OpenGL -framework AppKit`.
    - Update the search path for GLEW to `/opt/homebrew/opt/glew`.
2.  **Modify `main_gui.py`**:
    - Ensure `customtkinter` appearance matches macOS (vibrant backgrounds).
    - Handle the "Command" key instead of "Control" for shortcuts if applicable.
3.  **Adjust Boilerplate**:
    - Ensure the FFGL SDK is compiled with `-fPIC` and `-bundle` flags.

---

## 5. Bundling for Distribution
Use `PyInstaller` with the provided `.spec` file to create a `FFMaker.app` bundle.

```bash
python compile_mac.py
```

---

## 6. Known Challenges
- **Code Signing**: macOS Gatekeeper will block unsigned `.app` bundles and `.bundle` plugins. For local use, users may need to manually allow the application in "Security & Privacy".
- **TkinterDnD**: Ensure the `tkdnd` library is correctly located by the `tkinterdnd2` wrapper on macOS.
