# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Gene Desktop Application
"""

import os
import sys

block_cipher = None

# Get the project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(SPEC)))

# Data files to include
datas = [
    # Gene icon
    (os.path.join(PROJECT_ROOT, 'interfaces', 'desktop', 'assets'), 'assets'),
    # Config files
    (os.path.join(PROJECT_ROOT, 'config'), 'config'),
]

# Hidden imports that PyInstaller might miss
hidden_imports = [
    'customtkinter',
    'PIL',
    'PIL.Image',
    'PIL.ImageTk',
    'PIL.ImageEnhance',
    'sqlite3',
    'json',
    'threading',
    'datetime',
    'pathlib',
    'requests',
    'urllib3',
    'certifi',
]

a = Analysis(
    [os.path.join(PROJECT_ROOT, 'interfaces', 'desktop', 'app.py')],
    pathex=[PROJECT_ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'tkinter.test',
        'unittest',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Gene',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # No console window for GUI app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(PROJECT_ROOT, 'installer', 'gene.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Gene',
)
