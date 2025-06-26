# -*- mode: python ; coding: utf-8 -*-

import os
import sys
import site
from PyInstaller.utils.hooks import collect_all

block_cipher = None

# Directly specify the path to yt-dlp.exe in the Scripts directory
yt_dlp_path = 'C:\\Users\\Austin\\miniconda3\\Scripts\\yt-dlp.exe'

# Collect all yt-dlp dependencies
ytdlp_datas = []
ytdlp_binaries = []

if yt_dlp_path:
    print(f"Found yt-dlp at: {yt_dlp_path}")
    ytdlp_binaries.append((yt_dlp_path, '.'))

a = Analysis(['vimeograb_gui.py'],
             pathex=['c:\\Users\\Austin\\Georgia Tech Dev\\vimeograb_gui'],
             binaries=ytdlp_binaries,
             datas=ytdlp_datas,
             hiddenimports=['PIL._tkinter_finder'],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)

pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)

exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [],
          name='VimeoGrabV1.1',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=False,
          hide_console='hide-early',
          disable_windowed_traceback=False,
          target_arch=None,
          codesign_identity=None,
          entitlements_file=None,
          icon='NONE')
