# -*- mode: python ; coding: utf-8 -*-
# Build with:  venv\Scripts\python compile.py   (Windows: dist\FFStudio.exe)
#              venv/bin/python compile.py       (macOS: dist/FFStudio.app)
import os
import re
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

MAC = sys.platform == 'darwin'

# ffstudio/__init__.py's version, e.g. 0.9.0-beta.1; its numeric part for the
# exe's version resource and the Mac bundle.
with open(os.path.join('ffstudio', '__init__.py'), encoding='utf-8') as f:
    VERSION = re.search(r'__version__ = "([^"]+)"', f.read()).group(1)
NUMBERS = tuple(int(n) for n in VERSION.split('-')[0].split('.'))

# NDI output (Windows and macOS): cyndilib bundles the NDI runtime. Only the main
# library is needed (not its DirectShow / UWP variants), plus the NDI licence
# files, which must ship with it. Its compiled modules import each other, which
# PyInstaller can't see, hence collect_submodules.
ndi_binaries = [b for b in collect_dynamic_libs('cyndilib')
                if not any(v in os.path.basename(b[0]) for v in ('DirectShow', 'UWP'))]
ndi_datas = collect_data_files('cyndilib', includes=['**/*icenses*.txt'])
ndi_imports = collect_submodules('cyndilib') + collect_submodules('pugixml_cython')

ffgl_sdk = [(os.path.join(root, f), os.path.relpath(root, '.'))
            for root, dirs, files in os.walk(os.path.join('boilerplates', 'ffgl'))
            if '.git' not in root and os.sep + 'build' not in root
            for f in files]

if MAC:
    # Plugins link the system OpenGL framework; no GLEW needed.
    # Syphon output: syphon-python loads its Syphon.framework from the package folder.
    platform_datas = collect_data_files('syphon')
    platform_binaries = []
    platform_imports = ['OpenGL.platform.darwin', 'syphon']
else:
    platform_datas = [
        ('deps/glew-2.2.0/include', 'deps/glew-2.2.0/include'),
        ('deps/glew-2.2.0/lib/Release/x64', 'deps/glew-2.2.0/lib/Release/x64'),
    ]
    # Spout output: SpoutGL's extension needs its Spout.dll beside it.
    platform_binaries = collect_dynamic_libs('SpoutGL')
    platform_imports = ['OpenGL.platform.win32', 'SpoutGL']

a = Analysis(
    [os.path.join('src', 'main_gui.py')],
    pathex=['.', 'src'],
    binaries=collect_dynamic_libs('glfw') + platform_binaries + ndi_binaries,
    datas=collect_data_files('customtkinter') + collect_data_files('tkinterdnd2') + [
        ('templates', 'templates'),
        ('assets/icon', 'assets/icon'),          # window icons (paths.icon_dir)
    ] + platform_datas + ndi_datas + ffgl_sdk,
    hiddenimports=['ffstudio', 'glfw', 'OpenGL.GL'] + platform_imports + ndi_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],                                 # numpy: cyndilib (NDI) needs it
    noarchive=False,
    optimize=0,
)
# PyOpenGL's wheel carries GLUT and GLE DLLs (and their licences); FFStudio
# uses neither (its windows are GLFW's), so leave them out.
a.binaries = [b for b in a.binaries
              if not os.path.normpath(b[0]).startswith(os.path.join('OpenGL', 'DLLS'))]
a.datas = [d for d in a.datas
           if not os.path.normpath(d[0]).startswith(os.path.join('OpenGL', 'DLLS'))]

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
            'CFBundleShortVersionString': '.'.join(map(str, NUMBERS)),
            'CFBundleVersion': VERSION,
            'NSHighResolutionCapable': True,
            # Homebrew's Python and Tcl/Tk, bundled here, are built for macOS 14:
            # on older systems Finder should say so instead of the app crashing.
            'LSMinimumSystemVersion': '14.0',
            # NDI finds and announces sources on the local network (Bonjour), which
            # macOS only allows once the user grants Local Network access.
            'NSLocalNetworkUsageDescription':
                'FFStudio sends its output over NDI to other apps and computers on your network, '
                'and can be remote-controlled from them (OSC, e.g. TouchOSC).',
            'NSBonjourServices': ['_ndi._tcp'],
        },
    )
else:
    from PyInstaller.utils.win32 import versioninfo as vi
    quad = (NUMBERS + (0, 0, 0, 0))[:4]
    version_resource = vi.VSVersionInfo(
        ffi=vi.FixedFileInfo(filevers=quad, prodvers=quad),
        kids=[vi.StringFileInfo([vi.StringTable('040904B0', [
                  vi.StringStruct('ProductName', 'FFStudio'),
                  vi.StringStruct('FileDescription', 'FFStudio'),
                  vi.StringStruct('ProductVersion', VERSION),
                  vi.StringStruct('FileVersion', VERSION),
                  vi.StringStruct('OriginalFilename', 'FFStudio.exe')])]),
              vi.VarFileInfo([vi.VarStruct('Translation', [0x0409, 1200])])])
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name='FFStudio',
        icon='assets/icon/FFStudio.ico',
        version=version_resource,
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
