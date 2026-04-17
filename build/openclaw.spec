# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for building OpenClaw Brain standalone executables.
Supports Linux, Windows, and macOS (universal2 for M1/M2).
"""

import sys
from pathlib import Path

a = Analysis(
    ['main.py'],
    pathex=[str(Path('.').resolve())],
    binaries=[],
    datas=[
        ('config', 'config'),
        ('data', 'data'),
        ('interface/web', 'interface/web'),
    ],
    hiddenimports=[
        'fastapi',
        'uvicorn',
        'spacy',
        'chromadb',
        'sentence_transformers',
        'trafilatura',
        'feedparser',
        'pydantic',
        'sqlalchemy',
        'aiofiles',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludedimports=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='openclaw-brain',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
