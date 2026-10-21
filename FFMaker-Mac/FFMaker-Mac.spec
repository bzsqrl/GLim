# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['src/main_gui.py'],
    pathex=[],
    binaries=[],
    datas=[
        # Note: These paths will need adjustment based on the target machine's site-packages location
        # On Mac with Homebrew, they are typically in /opt/homebrew/lib/python3.x/site-packages/
        ('PLACEHOLDER_SITE_PACKAGES/customtkinter', 'customtkinter/'), 
        ('PLACEHOLDER_SITE_PACKAGES/tkinterdnd2', 'tkinterdnd2/'),
        ('boilerplates_mac', 'boilerplates'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='FFMaker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch='arm64', # Targeting Apple Silicon
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='FFMaker',
)
app = BUNDLE(
    coll,
    name='FFMaker.app',
    icon=None,
    bundle_identifier='com.ffmaker.app',
)
