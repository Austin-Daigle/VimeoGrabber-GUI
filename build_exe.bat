@echo off
echo Building VimeoGrab Standalone Executable...

REM Install PyInstaller if not already installed
pip install pyinstaller

REM Clean previous builds
rmdir /S /Q build
rmdir /S /Q dist

REM Build the executable
pyinstaller --clean vimeograb_gui.spec

echo.
echo Build completed. The executable can be found in the dist folder.
echo.
pause
