# VimeoGrab GUI v1.1

A graphical user interface for downloading private Vimeo videos with ease.

[Download v.1.1 Here - Windows Only](https://github.com/Austin-Daigle/VimeoGrabber-GUI/blob/main/VimeoGrabber_GUI_v.1.1.exe)

[Download v.1.2 Here - Windows Only]([https://drive.google.com/file/d/1VBkIL4l_v30je5_fm-fYfp2BiyOEOv0Y/view?usp=sharing](https://drive.google.com/file/d/1jzhobIAoIhxcI1SWpz1te0M2cdJY2jc4/view?usp=sharing))

## Updates/Version History:
- Version 1.0: Stable build, able to download private or public videos from Vimeo.
- Version 1.1: Improved performace, bug fixes with the quality selection interface, opening
               the directory of download location, and selecting download locations.
- Version 1.2: Converted to a fully self-contained EXE (bundles yt-dlp and ffmpeg)
              with robust runtime path detection to fix WinError 2; adds optional cookies
              support, clearer error messages, and   minor UI/progress polish
              (title updated to v1.2).

## Features

- Simple and intuitive graphical interface
- Download private and protected Vimeo videos
- Select from multiple available video qualities
- Option to save directly to your Downloads folder
- Two-phase progress indication:
  - Download phase with percentage, speed, and ETA
  - Processing phase with clear status indication
- Smart file path detection for easy folder access
- Leverages yt-dlp for reliable video extraction
- Automatically checks for and installs dependencies
- Available as standalone Windows executable (no Python required)

## Screenshots

(Screenshots will be available after first run)

## Requirements

- Python 3.6 or higher
- tkinter (usually included with Python)
- yt-dlp (installed automatically if missing)

## Installation

1. Make sure you have Python installed on your system
2. The application will check for and install yt-dlp if it's not already installed
3. Run the application using Python:

```
python vimeograb_gui.py
```

## Usage

1. Run the application
2. Enter a Vimeo video URL in the input field
3. Choose whether to save to Downloads folder (checked by default)
4. Click "Get Video Information"
5. Select your preferred video quality
6. Click "Download"
7. Monitor the download progress
8. When complete, you can open the folder containing the downloaded video

## Troubleshooting

- **Error getting video information**: Make sure the URL is correct and the video is accessible
- **Download fails**: Check your internet connection and try again
- **Progress not updating**: Some videos may not provide accurate progress information
- **GUI freezes**: The application runs downloads in a separate thread to prevent freezing

## Related Projects

- `vimeograb_cli.py`: Command-line version of VimeoGrab
- `vimeograb_core.py`: Core functionality used by both GUI and CLI versions

## Legal Notice

This tool is intended for personal use only on videos that you have permission to download. Please respect copyright laws and Vimeo's terms of service.
