# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

# Resolve cross-platform paths; when PyInstaller executes this spec,
# __file__ is not defined, so we base paths on the current working
# directory (the project root).
ROOT = Path(os.getcwd()).resolve()
ENTRY_SCRIPT = str(ROOT / 'py_client' / 'main.py')
ASSETS_DIR = str(ROOT / 'py_client' / 'assets')
ENV_FILE = str(ROOT / 'python_backend' / '.env')

# Determine icon per platform
icon_file = None
if sys.platform == 'darwin':
    cand = ROOT / 'py_client' / 'assets' / 'pharmaspot-icon.icns'
    icon_file = str(cand) if cand.is_file() else None
elif os.name == 'nt':
    cand = ROOT / 'py_client' / 'assets' / 'pharmaspot-icon.ico'
    icon_file = str(cand) if cand.is_file() else None
else:
    # Linux: optional .ico or .png is fine to skip
    cand = ROOT / 'py_client' / 'assets' / 'pharmaspot-icon.ico'
    icon_file = str(cand) if cand.is_file() else None

hiddenimports = []
hiddenimports += collect_submodules('python_backend')
hiddenimports += collect_submodules('qdarktheme')
hiddenimports += collect_submodules('passlib.handlers')
hiddenimports += [
    'passlib.handlers.bcrypt',
    'bcrypt',
]

a = Analysis(
    [ENTRY_SCRIPT],
    pathex=[str(ROOT / 'py_client'), str(ROOT)],
    binaries=[],
    datas=[
        (ASSETS_DIR, 'assets'),
        (ENV_FILE, 'python_backend'),
    ],
    hiddenimports=hiddenimports,
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
    a.binaries,
    a.datas,
    [],
    name='PharmaSpot',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=(sys.platform == 'darwin'),
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[icon_file] if icon_file else None,
)

# On macOS, also build a .app bundle so that CI
# and distribution scripts can find dist/PharmaSpot.app.
if sys.platform == 'darwin':
    app = BUNDLE(
        exe,
        name='PharmaSpot.app',
        icon=icon_file if icon_file else None,
        bundle_identifier='com.pharmaspot.PharmaSpot',
    )
