# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
from pathlib import Path

engine_root = Path(SPECPATH).resolve().parents[2] / 'packages' / 'engine'
datas = [(str(engine_root / 'assets'), 'assets')]
binaries = []
hiddenimports = []
tmp_ret = collect_all('pyaudiowpatch')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['bridge.py'],
    pathex=[str(engine_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
# Qt uses the Windows ICU API. Do not bundle an unrelated ICU from a tool's PATH.
a.binaries = [entry for entry in a.binaries if entry[0].lower() not in ('icuuc.dll', 'icudt78.dll')]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='CopilotEngine',
    icon=str(engine_root / 'assets' / 'copilot.ico'),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
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
    name='CopilotEngine',
)
