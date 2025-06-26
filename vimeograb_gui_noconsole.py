#!/usr/bin/env python3
"""
VimeoGrab GUI v1.1 - Graphical User Interface for VimeoGrab
Downloads private Vimeo videos using just a link with an easy-to-use interface

Version: 1.1
Status: Stable
Last Updated: June 25, 2025

Changelog:
v1.1 - Improved progress indication for two-phase downloads
      - Now clearly distinguishes between download and processing phases
      - Added standalone EXE compilation support
      - Fixed "Open Folder" button functionality
      - Eliminated console windows in standalone mode
"""

# -------- CRITICAL: PREVENT CONSOLE WINDOWS --------
# Redirect stdout and stderr to null to prevent console output
import sys
import os

# Make sure we're redirecting stdout/stderr if running as executable
if getattr(sys, 'frozen', False):
    # We're running in a PyInstaller bundle, redirect output
    class NullWriter:
        def write(self, s): pass
        def flush(self): pass
    
    sys.stdout = NullWriter()
    sys.stderr = NullWriter()

# Imports 
import subprocess
import threading
import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import re
from urllib.parse import urlparse
import time
from pathlib import Path
import platform

# This function overrides all subprocess calls to ensure no console windows appear
def hidden_subprocess(cmd, **kwargs):
    """Run a subprocess with hidden console window on all platforms"""
    # Create platform-specific startupinfo to hide console
    startupinfo = None
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0  # SW_HIDE
    
    # Add startupinfo to kwargs if on Windows
    if sys.platform == "win32":
        kwargs['startupinfo'] = startupinfo
        # Add additional flags to prevent console windows in Windows
        if hasattr(subprocess, 'CREATE_NO_WINDOW'):
            kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
            
    return subprocess.Popen(cmd, **kwargs)

# Hijack the subprocess.Popen to use our version
original_popen = subprocess.Popen
subprocess.Popen = hidden_subprocess

# --- REST OF YOUR CODE FILE HERE ---
# The rest of your vimeograb_gui.py code should be copied here

# Import the rest of the original file 
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "vimeograb_gui.py"), 'r') as f:
    code = f.read()
    # Skip the first section with imports that we already have
    start_index = code.find('# Universal subprocess helper')
    if start_index > 0:
        exec(code[start_index:])  # Execute the rest of the original file
