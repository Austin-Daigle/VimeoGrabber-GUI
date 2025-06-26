# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# First analysis for the launcher script
a = Analysis(
    ['vimeograb_launcher.py'],
    pathex=[],
    binaries=[],
    datas=[('vimeograb_gui.py', '.'), ('yt-dlp.exe', '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['_bootlocale'],
    win_no_prefer_redirects=False,
    cipher=block_cipher,
    noarchive=False,
)

# Create the EXE
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='VimeoGrabGUI_v1.1_NoConsole',
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
    icon=None,
    # These options help prevent console windows
    uac_admin=False,
)
