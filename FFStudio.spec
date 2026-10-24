# -*- mode: python ; coding: utf-8 -*-
# Build with:  venv\Scripts\python compile.py   (Windows: dist\FFStudio.exe)
#              venv/bin/python compile.py       (macOS: dist/FFStudio.app)
import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

MAC = sys.platform == 'darwin'

ffgl_sdk = [(os.path.join(root, f), os.path.relpath(root, '.'))
            for root, dirs, files in os.walk(os.path.join('boilerplates', 'ffgl'))
            if '.git' not in root and os.sep + 'build' not in root
            for f in files]

if MAC:
    # Plugins link the system OpenGL framework; no GLEW needed.
    platform_datas = []
    platform_imports = ['OpenGL.platform.darwin']
else:
    platform_datas = [
        ('deps/glew-2.2.0/include', 'deps/glew-2.2.0/include'),
        ('deps/glew-2.2.0/lib/Release/x64', 'deps/glew-2.2.0/lib/Release/x64'),
    ]
    platform_imports = ['OpenGL.platform.win32']

a = Analysis(
    [os.path.join('src', 'main_gui.py')],
    pathex=['.', 'src'],
    binaries=collect_dynamic_libs('glfw'),
    datas=collect_data_files('customtkinter') + collect_data_files('tkinterdnd2') + [
        ('templates', 'templates'),
        ('assets/icon', 'assets/icon'),          # window icons (paths.icon_dir)
    ] + platform_datas + ffgl_sdk,
    hiddenimports=['ffmaker', 'glfw', 'OpenGL.GL'] + platform_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['numpy'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

if MAC:
    # One-folder build wrapped in an .app (PyInstaller deprecates one-file .apps).
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='FFStudio',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
    coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='FFStudio')
    app = BUNDLE(
        coll,
        name='FFStudio.app',
        icon='assets/icon/FFStudio.icns',
        bundle_identifier='com.ffstudio.app',
        info_plist={
            'CFBundleShortVersionString': '1.0',
            'NSHighResolutionCapable': True,
            'LSMinimumSystemVersion': '11.0',
        },
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name='FFStudio',
        icon='assets/icon/FFStudio.ico',
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
