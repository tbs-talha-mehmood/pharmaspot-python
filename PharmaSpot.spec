# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = []
hiddenimports += collect_submodules('python_backend')
hiddenimports += collect_submodules('qdarktheme')
hiddenimports += collect_submodules('passlib.handlers')
hiddenimports += [
    'passlib.handlers.bcrypt',
    'bcrypt',
]


a = Analysis(
    ['py_client\\main.py'],
    pathex=['py_client', '.'],
    binaries=[],
    datas=[
        ('py_client/assets', 'assets'),
        # Ship backend .env so the frozen build uses the same DB config.
        ('python_backend/.env', 'python_backend'),
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
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['py_client\\assets\\pharmaspot-icon.ico'],
)
