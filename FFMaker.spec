# -*- mode: python ; coding: utf-8 -*-
# Build with:  venv\Scripts\python compile.py
import os
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

ffgl_sdk = [(os.path.join(root, f), os.path.relpath(root, '.'))
            for root, dirs, files in os.walk(os.path.join('boilerplates', 'ffgl'))
            if '.git' not in root and os.sep + 'build' not in root
            for f in files]

a = Analysis(
    ['src\\main_gui.py'],
    pathex=['.', 'src'],
    binaries=collect_dynamic_libs('glfw'),
    datas=collect_data_files('customtkinter') + collect_data_files('tkinterdnd2') + [
        ('templates', 'templates'),
        ('deps/glew-2.2.0/include', 'deps/glew-2.2.0/include'),
        ('deps/glew-2.2.0/lib/Release/x64', 'deps/glew-2.2.0/lib/Release/x64'),
    ] + ffgl_sdk,
    hiddenimports=['ffmaker', 'glfw', 'OpenGL.GL', 'OpenGL.platform.win32'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['numpy'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='FFMaker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
