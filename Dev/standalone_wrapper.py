#!/usr/bin/env python3
"""
VimeoGrab GUI v1.1 Standalone Wrapper
This script ensures the application can run as a standalone executable
"""

import os
import sys
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox

# Make sure we can find our resources and modules
if getattr(sys, 'frozen', False):
    # We're running as a bundled exe
    bundle_dir = os.path.dirname(sys.executable)
    sys.path.insert(0, bundle_dir)
    
    # Ensure temp directory exists for yt-dlp
    temp_dir = os.path.join(os.environ.get('TEMP', os.path.join(os.environ['USERPROFILE'], 'AppData', 'Local', 'Temp')), 'VimeoGrab')
    os.makedirs(temp_dir, exist_ok=True)
    os.environ['YTDLP_CACHEDIR'] = temp_dir
else:
    # We're running in a normal Python environment
    bundle_dir = os.path.dirname(os.path.abspath(__file__))

def ensure_ytdlp():
    """Make sure yt-dlp is available"""
    try:
        subprocess.run(['yt-dlp', '--version'], 
                       stdout=subprocess.PIPE, 
                       stderr=subprocess.PIPE,
                       creationflags=subprocess.CREATE_NO_WINDOW)
        return True
    except:
        # yt-dlp not found, check if pip is available
        try:
            # Install yt-dlp using pip
            subprocess.run([sys.executable, '-m', 'pip', 'install', 'yt-dlp'],
                          stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE,
                          creationflags=subprocess.CREATE_NO_WINDOW)
            return True
        except:
            # Couldn't install yt-dlp
            return False

def main():
    """Start the VimeoGrab GUI"""
    if not ensure_ytdlp():
        root = tk.Tk()
        root.withdraw()  # Hide the main window
        messagebox.showerror(
            "Dependency Error",
            "Could not find or install yt-dlp. Please install it manually:\n"
            "pip install yt-dlp"
        )
        root.destroy()
        return
    
    # Start the actual application
    from vimeograb_gui import main as start_gui
    start_gui()

if __name__ == "__main__":
    main()
