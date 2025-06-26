#!/usr/bin/env python3
"""
VimeoGrab GUI Launcher
Provides a completely isolated environment for launching the application
with no console windows
"""

import os
import sys
import subprocess
import importlib.util

# Set environment variables to prevent console windows
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUNBUFFERED"] = "1"
os.environ["PYTHONNOUSERSITE"] = "1"  # Don't use user site packages

# Import main module
if __name__ == "__main__":
    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if getattr(sys, 'frozen', False):
        # Running as executable
        script_dir = os.path.dirname(sys.executable)
    
    # Import and run the main module
    try:
        # Load main script dynamically to isolate from environment
        main_script = os.path.join(script_dir, 'vimeograb_gui.py')
        spec = importlib.util.spec_from_file_location("vimeograb_main", main_script)
        module = importlib.util.module_from_spec(spec)
        sys.modules["vimeograb_main"] = module
        spec.loader.exec_module(module)
    except Exception as e:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Error", f"Failed to start VimeoGrab GUI: {str(e)}")
        sys.exit(1)
