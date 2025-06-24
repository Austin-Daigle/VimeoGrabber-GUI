# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(['standalone_wrapper.py'],
             pathex=[],
             binaries=[],
             datas=[],
             hiddenimports=['yt_dlp.extractor', 'yt_dlp.downloader', 'yt_dlp.postprocessor'],
             hookspath=[],
             hooksconfig={},
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)

# Include required files
a.datas += [('vimeograb_core.py', '../vimeograb_core.py', 'DATA')]
a.datas += [('vimeograb_gui.py', './vimeograb_gui.py', 'DATA')]

# Include FFmpeg binary if needed
# Uncomment the following lines if you want to bundle FFmpeg
# import shutil
# ffmpeg_path = shutil.which('ffmpeg.exe')
# if ffmpeg_path:
#     a.datas += [('ffmpeg.exe', ffmpeg_path, 'DATA')]

pyz = PYZ(a.pure, a.zipped_data,
          cipher=block_cipher)

exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,  
          [],
          name='VimeoGrab',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=False,
          disable_windowed_traceback=False,
          target_arch=None,
          codesign_identity=None,
          entitlements_file=None,
          icon=None)  # You can add an icon file here if you have one
