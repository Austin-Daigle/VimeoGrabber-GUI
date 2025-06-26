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
"""

import os
import sys
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

# Universal subprocess helper to ensure all console windows are hidden
def hidden_subprocess(cmd, **kwargs):
    """Run a subprocess with hidden console window on all platforms"""
    # Create platform-specific startupinfo to hide console
    startupinfo = None
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0  # SW_HIDE
    
    # Add startupinfo to kwargs if on Windows
    if startupinfo:
        kwargs['startupinfo'] = startupinfo
        
    # Redirect stderr to suppress error messages in console
    if 'stderr' not in kwargs:
        kwargs['stderr'] = subprocess.PIPE
        
    # Run the process with all console suppression options
    return subprocess.run(cmd, **kwargs)

# Core functionality embedded directly in the GUI application

def get_ytdlp_path():
    """Get the path to the yt-dlp executable based on environment"""
    # When running as a bundled executable
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
        if sys.platform == 'win32':
            # Look for bundled yt-dlp.exe
            ytdlp_path = os.path.join(base_path, 'yt-dlp.exe')
            if os.path.exists(ytdlp_path):
                return ytdlp_path
        # Look for bundled yt-dlp
        ytdlp_path = os.path.join(base_path, 'yt-dlp')
        if os.path.exists(ytdlp_path):
            return ytdlp_path
    
    # When running as a script, use the system's yt-dlp
    return 'yt-dlp'

def check_ytdl_installed():
    """Check if yt-dlp is available"""
    ytdlp_path = get_ytdlp_path()
    
    try:
        result = hidden_subprocess(['yt-dlp', '--version'], 
                              stdout=subprocess.PIPE, 
                              text=True, 
                              check=False)
        return result.returncode == 0
    except Exception:
        return False

def get_cookies_path():
    """Get path to cookies file if it exists."""
    home_dir = os.path.expanduser("~")
    cookies_path = os.path.join(home_dir, ".vimeo_cookies.txt")
    
    if os.path.isfile(cookies_path):
        print(f"Using cookies file: {cookies_path}")
        return cookies_path
    return None

# Main GUI class for VimeoGrab
# Uses a step-by-step workflow for URL input, quality selection, and download
# Handles both download and processing phases with clear progress indication
class VimeoGrabGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("VimeoGrab v1.1")
        self.root.geometry("500x180")
        self.root.resizable(False, False)
        
        # Set theme colors
        self.bg_color = "#f5f5f5"
        self.accent_color = "#4a90e2"
        self.text_color = "#333333"
        
        self.root.configure(bg=self.bg_color)
        
        # Create style
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure('TFrame', background=self.bg_color)
        self.style.configure('TLabel', background=self.bg_color, foreground=self.text_color, font=("Arial", 10))
        self.style.configure('TButton', background=self.accent_color, foreground="white", font=("Arial", 10, "bold"))
        self.style.configure('TEntry', font=("Arial", 10))
        self.style.configure('TCheckbutton', background=self.bg_color, font=("Arial", 10))
        
        # Initialize variables for later screens
        self.quality_var = tk.StringVar(value="best")
        self.save_to_downloads_var = tk.BooleanVar(value=True)  # Initialize BEFORE creating UI
        self.selected_quality = None
        self.download_path = None
        self.vimeo_url = None
        self.available_qualities = []
        self.download_thread = None
        self.process = None
        
        # Track UI and download state to prevent duplicate progress bar resets
        self.download_in_progress = False
        self.ui_state = "initial"  # Can be: initial, downloading, processing, completed
        
        # Create main frame
        self.main_frame = ttk.Frame(root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Create URL entry components
        self.create_url_entry_ui()
        
    def create_url_entry_ui(self):
        """Create the initial URL entry screen"""
        # Clear the frame
        for widget in self.main_frame.winfo_children():
            widget.destroy()
        
        # Title
        title_label = ttk.Label(
            self.main_frame, 
            text="VimeoGrab - Download Vimeo Videos", 
            font=("Arial", 14, "bold")
        )
        title_label.pack(pady=(0, 15))
        
        # URL Entry
        url_frame = ttk.Frame(self.main_frame)
        url_frame.pack(fill=tk.X, pady=5)
        
        url_label = ttk.Label(url_frame, text="Vimeo URL:")
        url_label.pack(side=tk.LEFT, padx=5)
        
        self.url_entry = ttk.Entry(url_frame, width=50)
        self.url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Save to Downloads option
        save_frame = ttk.Frame(self.main_frame)
        save_frame.pack(fill=tk.X, pady=10)
        
        save_check = ttk.Checkbutton(
            save_frame, 
            text="Save to Downloads folder",
            variable=self.save_to_downloads_var
        )
        save_check.pack(side=tk.LEFT, padx=5)
        
        # Download button
        button_frame = ttk.Frame(self.main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        download_button = ttk.Button(
            button_frame, 
            text="Get Video Information", 
            command=self.process_url
        )
        download_button.pack(side=tk.RIGHT, padx=5)
        
    def process_url(self):
        """Process the URL and get video information"""
        url = self.url_entry.get().strip()
        
        if not url:
            messagebox.showerror("Error", "Please enter a Vimeo URL")
            return
            
        # Basic URL validation
        parsed_url = urlparse(url)
        if not parsed_url.netloc or 'vimeo' not in parsed_url.netloc:
            messagebox.showerror("Error", "Invalid Vimeo URL")
            return
            
        self.vimeo_url = url
        
        # Show loading indicator
        self.show_loading("Getting video information...")
        
        # Start thread to get video information
        threading.Thread(target=self.get_video_information, daemon=True).start()
    
    def show_loading(self, message="Loading..."):
        """Show loading screen"""
        # Clear the frame
        for widget in self.main_frame.winfo_children():
            widget.destroy()
            
        loading_label = ttk.Label(
            self.main_frame, 
            text=message,
            font=("Arial", 12)
        )
        loading_label.pack(pady=30)
        
        progress = ttk.Progressbar(
            self.main_frame,
            mode='indeterminate',
            length=300
        )
        progress.pack(pady=10)
        progress.start(10)
        
    def get_video_information(self):
        """Get video information and available qualities"""
        try:
            # Use yt-dlp to get video information
            cmd = ['yt-dlp', '--dump-json', self.vimeo_url]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                self.root.after(0, lambda: messagebox.showerror(
                    "Error", f"Failed to get video information: {result.stderr}"
                ))
                self.root.after(0, self.create_url_entry_ui)
                return
            
            video_info = json.loads(result.stdout)
            
            # Get available formats
            formats = video_info.get('formats', [])
            
            # Filter video formats and get unique resolutions
            video_formats = [f for f in formats if f.get('vcodec', 'none') != 'none']
            
            # Extract unique heights and create quality options
            heights = set()
            self.available_qualities = []
            
            for fmt in video_formats:
                height = fmt.get('height')
                if height and height not in heights:
                    heights.add(height)
                    self.available_qualities.append({
                        'height': height,
                        'label': f"{height}p"
                    })
            
            # Sort by height, highest first
            self.available_qualities.sort(key=lambda x: x['height'], reverse=True)
            
            # Add 'best' and 'worst' options
            self.available_qualities.insert(0, {'height': 'best', 'label': 'Best Quality'})
            self.available_qualities.append({'height': 'worst', 'label': 'Worst Quality'})
            
            # Show quality selection UI
            video_title = video_info.get('title', 'Video')
            self.root.after(0, lambda: self.create_quality_selection_ui(video_title))
            
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror(
                "Error", f"Failed to get video information: {str(e)}"
            ))
            self.root.after(0, self.create_url_entry_ui)
            
    def create_quality_selection_ui(self, video_title):
        """Create the quality selection screen with dropdown menu for quality selection"""
        # Clear the frame
        for widget in self.main_frame.winfo_children():
            widget.destroy()
        
        # Set window size large enough to show all buttons
        self.root.geometry("500x450")
        
        # --- Video Title ---
        title_frame = ttk.Frame(self.main_frame)
        title_frame.pack(fill=tk.X, pady=15, padx=20)
        
        title_label = ttk.Label(
            title_frame, 
            text=f"Select Quality for:\n{video_title}", 
            font=("Arial", 12, "bold"),
            wraplength=450,
            justify=tk.CENTER
        )
        title_label.pack(pady=5)
        
        # --- Main Content ---
        content_frame = ttk.Frame(self.main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=10)
        
        # --- Quality Selection Dropdown ---
        quality_frame = ttk.LabelFrame(content_frame, text="Video Quality")
        quality_frame.pack(fill=tk.X, pady=10)
        
        # Prepare quality options for dropdown
        quality_options = []
        quality_values = {}
        
        # Check if "Best Quality" is already in the available qualities
        has_best_option = any(q["height"] == "best" for q in self.available_qualities)
        
        # Only add "Best Quality" option if it's not already included
        if not has_best_option:
            quality_options.append("Best Quality")
            quality_values["Best Quality"] = "best"
        
        # Add all available qualities
        for quality in self.available_qualities:
            option_text = quality["label"]
            quality_options.append(option_text)
            quality_values[option_text] = quality["height"]
        
        # Create the dropdown - with full width to prevent horizontal scrollbar
        self.quality_var = tk.StringVar(value=quality_options[0])  # Default to "Best Quality"
        quality_dropdown = ttk.Combobox(
            quality_frame, 
            textvariable=self.quality_var,
            values=quality_options,
            state="readonly",
            width=50  # Wider to avoid horizontal scrollbar
        )
        quality_dropdown.pack(padx=15, pady=15, fill=tk.X)
        
        # Make dropdown match the program's style
        style = ttk.Style()
        # Only modify the dropdown list appearance, not the basic structure
        style.configure('TCombobox', padding=5)
        style.map('TCombobox', 
                 fieldbackground=[('readonly', 'white')],
                 selectbackground=[('readonly', '#0078d7')],
                 selectforeground=[('readonly', 'white')])
        
        # Store the mapping for later use when downloading
        self.quality_values = quality_values
        
        # --- Save Location ---
        save_frame = ttk.LabelFrame(content_frame, text="Save Location")
        save_frame.pack(fill=tk.X, pady=10)
        
        # Use the existing save_to_downloads_var from __init__ to preserve state from main menu
        save_to_downloads_check = ttk.Checkbutton(
            save_frame,
            text="Save to Downloads folder",
            variable=self.save_to_downloads_var,
            command=self.toggle_save_location
        )
        save_to_downloads_check.pack(anchor=tk.W, pady=5, padx=15)
        
        self.custom_path_var = tk.StringVar()
        # Add trace to custom_path_var to validate download button with a delay to prevent excessive validation
        # Use a debouncer to avoid validating on every keystroke
        self.path_validation_after_id = None
        self.custom_path_var.trace_add("write", self.debounced_validate_path)
        
        self.custom_path_frame = ttk.Frame(save_frame)
        
        custom_path_entry = ttk.Entry(
            self.custom_path_frame,
            textvariable=self.custom_path_var,
            width=30
        )
        custom_path_entry.pack(side=tk.LEFT, padx=(15, 5))
        
        browse_button = ttk.Button(
            self.custom_path_frame,
            text="Browse",
            command=self.browse_save_location
        )
        browse_button.pack(side=tk.RIGHT, padx=(0, 15))
        
        # Initially hidden if save to downloads is checked
        if not self.save_to_downloads_var.get():
            self.custom_path_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        # --- Add Separator Line Above Buttons ---
        ttk.Separator(self.main_frame, orient="horizontal").pack(fill=tk.X, padx=20, pady=(20, 0))
                
        # --- Button Section - Navigation and Download Buttons ---
        # Use a Frame with fixed height to ensure it's always rendered
        button_frame = ttk.Frame(self.main_frame, height=80)
        button_frame.pack(fill=tk.X, pady=20, side=tk.BOTTOM)
        button_frame.pack_propagate(False)  # Force the frame to keep its size
        
        # Style for buttons
        style.configure('Download.TButton', 
                        font=('Arial', 11, 'bold'),
                        foreground='white', 
                        background='#0078d7',
                        padding=8)
        
        # Back button on the left side
        back_button = ttk.Button(
            button_frame,
            text="Back",
            command=self.create_url_entry_ui,
            width=15
        )
        back_button.place(relx=0.2, rely=0.5, anchor=tk.CENTER)
        
        # Download button on the right side - more prominent
        self.download_button = ttk.Button(
            button_frame,
            text="Download Video",
            command=self.start_download,
            width=20,
            style='Download.TButton'
        )
        self.download_button.place(relx=0.8, rely=0.5, anchor=tk.CENTER)
        
        # Validate download button state based on current settings
        self.validate_download_button()
        
    def debounced_validate_path(self, *args):
        """Debounce the path validation to avoid excessive validation while typing"""
        # Cancel any pending validation
        if hasattr(self, 'path_validation_after_id') and self.path_validation_after_id:
            self.root.after_cancel(self.path_validation_after_id)
        
        # Schedule a new validation in 500ms
        self.path_validation_after_id = self.root.after(500, self.validate_download_button)
        
    def validate_download_button(self):
        """Enable/disable download button based on save location validity"""
        if not hasattr(self, 'download_button'):
            return
            
        # If using Downloads folder, always enable button
        if self.save_to_downloads_var.get():
            self.download_button.config(state="normal")
            return
            
        # If using custom path, validate it
        custom_path = self.custom_path_var.get().strip()
        
        if not custom_path:
            # No path provided, disable button
            self.download_button.config(state="disabled")
            return
            
        # Check if the directory exists and is valid
        if os.path.isdir(custom_path):
            # Directory exists and is valid
            self.download_button.config(state="normal")
        else:
            # Directory doesn't exist, show error and disable button
            self.download_button.config(state="disabled")
            # Show error dialog on a timer to prevent multiple dialogs
            # Store the last error message time to prevent flood
            current_time = time.time()
            if not hasattr(self, 'last_dir_error_time') or current_time - self.last_dir_error_time > 2:
                self.last_dir_error_time = current_time
                # Use after to avoid blocking the UI thread
                self.root.after(100, lambda: messagebox.showerror("Invalid Directory", f"The directory '{custom_path}' does not exist or is not accessible."))
                
    def toggle_save_location(self):
        """Toggle visibility of the custom path frame based on checkbox state"""
        if self.save_to_downloads_var.get():
            # Use downloads folder, hide custom path
            if self.custom_path_frame.winfo_manager():
                self.custom_path_frame.pack_forget()
        else:
            # Use custom path, show entry
            self.custom_path_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
            
        # Update download button state
        self.validate_download_button()
    
    def browse_save_location(self):
        """Open a directory browser dialog to select save location"""
        directory = filedialog.askdirectory(title="Select Save Location")
        if directory:  # If user didn't cancel
            self.custom_path_var.set(directory)
            # Enable download button since we now have a valid path
            self.validate_download_button()
            
    def start_download(self):
        """Start the download process"""
        # Prevent starting multiple downloads
        if self.download_in_progress:
            print("Download already in progress, ignoring request")
            return
            
        # Set download state to prevent duplicate starts
        self.download_in_progress = True
        
        # Get the selected quality option from dropdown
        try:
            selected_option = self.quality_var.get()
            print(f"Selected quality option: {selected_option}")
            
            # Look up the actual quality value from our mapping
            if selected_option in self.quality_values:
                quality = self.quality_values[selected_option]
            else:
                # Default to best if something goes wrong
                print(f"Option not found in mapping, defaulting to best. Available: {self.quality_values}")
                quality = "best"
                
            # Set the selected quality
            self.selected_quality = quality
            print(f"Using quality value: {quality}")
        except Exception as e:
            print(f"Error in quality selection: {e}")
            # Default to best quality if there's an error
            self.selected_quality = "best"
            
        # We already have the vimeo_url set from the process_url method
        # No need to reset it here
        
        # Determine download path
        if self.save_to_downloads_var.get():
            # Use downloads folder
            downloads_path = os.path.join(os.path.expanduser("~"), "Downloads")
            self.download_path = downloads_path
        else:
            # Use the already validated custom path from the entry field
            custom_path = self.custom_path_var.get().strip()
            
            # This should never happen due to validation, but just in case
            if not custom_path or not os.path.isdir(custom_path):
                messagebox.showerror("Error", "Invalid download directory.")
                self.download_in_progress = False  # Reset flag on error
                return
                
            self.download_path = custom_path
        
        # Set UI state before creating progress UI
        self.ui_state = "downloading"
            
        # Show download progress UI - and ensure it's fully created before proceeding
        self.create_download_progress_ui()
        
        # Ensure UI elements are created before starting the download thread
        if not hasattr(self, 'progress_var') or not hasattr(self, 'status_label'):
            print("Critical error: UI elements not created. Creating emergency UI.")
            # Force UI creation before starting download
            self.ui_state = "initial"  # Reset UI state to force recreation
            self.create_download_progress_ui()
        
        # Start download thread
        self.download_thread = threading.Thread(
            target=self.download_video,
            daemon=True
        )
        self.download_thread.start()
    def create_download_progress_ui(self):
        """Create download progress UI"""
        # Only create UI if we're not already showing a progress UI
        if self.ui_state == "downloading" or self.ui_state == "processing":
            print(f"Current UI state: {self.ui_state}, not recreating download UI")
            # Ensure UI elements exist even if we skip recreation
            if not hasattr(self, 'progress_var') or not hasattr(self, 'status_label'):
                print("UI elements missing. Forcing UI creation despite existing state.")
            else:
                return  # Skip UI creation if already showing progress and UI elements exist
        
        # Clear the frame
        for widget in self.main_frame.winfo_children():
            widget.destroy()
            
        # Title
        title_label = ttk.Label(
            self.main_frame, 
            text="Downloading Video", 
            font=("Arial", 14, "bold")
        )
        title_label.pack(pady=(0, 15))
        
        # Progress frame
        progress_frame = ttk.Frame(self.main_frame)
        progress_frame.pack(fill=tk.X, pady=10, padx=20)
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            progress_frame,
            variable=self.progress_var,
            maximum=100,
            length=400
        )
        self.progress_bar.pack(fill=tk.X, pady=5)
        
        self.status_label = ttk.Label(
            progress_frame, 
            text="Preparing download...", 
            font=("Arial", 10)
        )
        self.status_label.pack(anchor=tk.W, pady=5)
        
        # Cancel button
        button_frame = ttk.Frame(self.main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        self.cancel_button = ttk.Button(
            button_frame, 
            text="Cancel", 
            command=self.cancel_download
        )
        self.cancel_button.pack(side=tk.RIGHT, padx=5)
        
        # Ensure UI is fully updated before continuing
        self.root.update_idletasks()
            
    def download_video(self):
        """Download the video in a separate thread"""
        try:
            # First ensure UI elements are available before proceeding
            if not hasattr(self, 'progress_var') or not hasattr(self, 'status_label'):
                print("Warning: UI elements missing at start of download_video. Attempting emergency UI creation.")
                # Send UI creation to main thread
                self.root.after(0, lambda: (
                    self.create_download_progress_ui(),
                    self.update_status("Starting download..."),
                    self.update_progress(0)
                ))
                # Give UI time to update
                time.sleep(0.5)
                
            # Get path to yt-dlp (bundled or system)
            ytdlp_path = get_ytdlp_path()
            
            # Build yt-dlp command
            cmd = [ytdlp_path, 
                   '--newline',
                   '--progress-template', "%(progress._percent_str)s|%(progress._speed_str)s|%(progress._eta_str)s"]
            
            # Format and quality selection
            if self.selected_quality == "best":
                cmd.extend(['--format', 'bestvideo+bestaudio/best'])
            elif self.selected_quality == "worst":
                cmd.extend(['--format', 'worstvideo+worstaudio/worst'])
            else:
                # Specific height selected
                cmd.extend(['--format', f'bestvideo[height<={self.selected_quality}]+bestaudio/best[height<={self.selected_quality}]'])
            
            # Output directory
            cmd.extend(['--paths', self.download_path])
            
            # Output template - clean filename
            cmd.extend(['--output', '%(title)s.%(ext)s'])
            
            # Add the URL
            cmd.append(self.vimeo_url)
            
            # Start the process using our hidden subprocess helper
            # We still need Popen for streaming the output, so create special case
            startupinfo = None
            if sys.platform == 'win32':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0  # SW_HIDE - explicitly use 0 instead of constant
                
                # Hide Python console too
                if hasattr(subprocess, 'CREATE_NO_WINDOW'):
                    kwargs = {'creationflags': subprocess.CREATE_NO_WINDOW}
                else:
                    kwargs = {}
            else:
                kwargs = {}
            
            self.process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1,
                startupinfo=startupinfo,
                **kwargs
            )
            
            # Process output
            downloaded_file = None
            in_download_phase = True  # Track which phase we're in
            
            for line in self.process.stdout:
                line = line.strip()
                print(f"yt-dlp output: {line}")  # Debug print
                
                # Check for phase changes and update UI accordingly
                if "[ffmpeg]" in line or "Merger" in line or "Post-process" in line:
                    if in_download_phase:  # Only update UI once when transitioning to processing phase
                        in_download_phase = False
                        print("Transitioning to processing phase")
                        # Update UI state to processing
                        self.ui_state = "processing"
                        
                        # Update progress bar to show we're in processing phase - all in one update to prevent flicker
                        def update_processing_ui():
                            self.update_progress(100)  # Set progress to 100%
                            self.update_status("Processing video and audio streams...")
                            # Switch to indeterminate progress mode for processing
                            if hasattr(self, 'progress_bar') and self.progress_bar is not None:
                                self.progress_bar.config(mode='indeterminate')
                                self.progress_bar.start(10)
                        
                        # Use a single after call to batch update the UI
                        if hasattr(self, 'progress_var') and hasattr(self, 'status_label') and hasattr(self, 'progress_bar'):
                            self.root.after(0, update_processing_ui)
                        else:
                            print("Warning: Can't update processing UI, elements don't exist")
                            # Try to recreate UI elements
                            self.root.after(0, lambda: (
                                self.create_download_progress_ui()
                            ))
                    
                    # Capture merged file destination
                    if "Merging formats into" in line:
                        match = re.search(r'Merging formats into\s*"(.+?)"', line)
                        if match:
                            downloaded_file = match.group(1).strip()
                            print(f"Found merged file: {downloaded_file}")
                
                # Only process progress info during download phase
                elif in_download_phase and '|' in line and line.count('|') >= 2:
                    parts = line.split('|')
                    if len(parts) >= 3:
                        percent_str, speed_str, eta_str = parts[0:3]
                        
                        # Update progress bar and status label in a single UI update to prevent flicker
                        try:
                            percent = float(percent_str.strip('%'))
                            status_text = f"Downloading: {speed_str.strip()}, ETA: {eta_str.strip()}"
                            
                            # Use a single after call for all UI updates
                            def update_download_ui(p=percent, t=status_text):
                                if hasattr(self, 'progress_var'):
                                    self.update_progress(p)
                                if hasattr(self, 'status_label'):
                                    self.update_status(t)
                            
                            self.root.after(0, update_download_ui)
                        except (ValueError, TypeError):
                            pass
                
                # Look for file destination messages
                elif "Destination:" in line:
                    match = re.search(r"Destination:\s*(.+)$", line)
                    if match:
                        downloaded_file = match.group(1).strip()
                        print(f"Found destination: {downloaded_file}")
                elif "[download]" in line and "Destination:" in line:
                    # Alternative format
                    match = re.search(r"Destination:\s*(.+)$", line)
                    if match:
                        downloaded_file = match.group(1).strip()
                        print(f"Found destination (alt): {downloaded_file}")
                        
            # Stop the progress bar animation if it was in indeterminate mode
            if hasattr(self, 'progress_bar'):
                self.root.after(0, lambda: self.progress_bar.stop())
            
            # If we didn't capture the file path but know the download directory,
            # we can still open the directory
            if not downloaded_file and self.download_path:
                print(f"No specific file path captured, using download directory: {self.download_path}")
                downloaded_file = self.download_path  # Will be treated as a directory in open_download_folder
            
            # Wait for process to complete
            self.process.wait()
            
            if self.process.returncode == 0:
                # Download successful - use a single after call with fixed delay to prevent double UI updates
                # This ensures any previous UI updates are completed first
                def show_completion_with_state_reset():
                    # Update state before showing completion
                    self.ui_state = "completed"
                    self.show_completion(downloaded_file)
                    
                self.root.after(100, show_completion_with_state_reset)
            else:
                # Download failed - use a single after call for all UI updates
                def handle_download_error():
                    # Reset download state
                    self.download_in_progress = False
                    self.ui_state = "initial"
                    messagebox.showerror("Error", "Failed to download the video")
                    self.create_url_entry_ui()
                    
                self.root.after(100, handle_download_error)
                
        except Exception as e:
            # Handle exceptions with a single after call for consistent UI updates
            def handle_exception_error():
                # Reset download state on exception
                self.download_in_progress = False
                self.ui_state = "initial"
                messagebox.showerror("Error", f"Error during download: {str(e)}")
                self.create_url_entry_ui()
                
            self.root.after(100, handle_exception_error)
        
    def update_progress(self, percent):
        """Update progress bar"""
        # Enhanced safety check for progress_var and progress_bar
        if hasattr(self, 'progress_var') and self.progress_var is not None:
            try:
                self.progress_var.set(percent)
            except Exception as e:
                print(f"Error updating progress bar: {e}")
        else:
            print(f"Warning: Attempted to update progress ({percent}%) but progress_var doesn't exist or is None")
            # If we're in the middle of downloading but UI elements are missing,
            # try creating the UI to prevent further errors
            if self.download_in_progress and self.ui_state in ["downloading", "processing"]:
                print("Attempting emergency UI recreation during progress update")
                # Schedule UI recreation on main thread
                self.root.after(0, self.create_download_progress_ui)
        
    def update_status(self, status_text):
        """Update status label"""
        # Enhanced safety check for status_label
        if hasattr(self, 'status_label') and self.status_label is not None:
            try:
                self.status_label.config(text=status_text)
            except Exception as e:
                print(f"Error updating status label: {e}")
        else:
            print(f"Warning: Attempted to update status to '{status_text}' but status_label doesn't exist or is None")
            # If we're in the middle of downloading but UI elements are missing,
            # try creating the UI to prevent further errors
            if self.download_in_progress and self.ui_state in ["downloading", "processing"]:
                print("Attempting emergency UI recreation during status update")
                # Schedule UI recreation on main thread
                self.root.after(0, self.create_download_progress_ui)
        
    def cancel_download(self):
        """Cancel the download"""
        if self.process:
            try:
                self.process.terminate()
            except Exception:
                pass
        
        # Reset download state
        self.download_in_progress = False
        self.ui_state = "initial"
                
        messagebox.showinfo("Cancelled", "Download was cancelled")
        self.create_url_entry_ui()
        
    def show_completion(self, downloaded_file):
        """Show completion message"""
        # Reset download in progress flag now that we're done
        self.download_in_progress = False
        # UI state is already set to "completed" before this method is called
        
        # Clear the frame
        for widget in self.main_frame.winfo_children():
            widget.destroy()
            
        # Title
        title_label = ttk.Label(
            self.main_frame, 
            text="Download Complete!", 
            font=("Arial", 14, "bold")
        )
        title_label.pack(pady=(0, 15))
        
        # File location
        if downloaded_file:
            location_label = ttk.Label(
                self.main_frame, 
                text=f"Saved to: {downloaded_file}", 
                font=("Arial", 10)
            )
            location_label.pack(pady=5)
            
        # Buttons
        button_frame = ttk.Frame(self.main_frame)
        button_frame.pack(fill=tk.X, pady=15)
        
        open_folder_button = ttk.Button(
            button_frame, 
            text="Open Folder", 
            command=lambda: self.open_download_folder(downloaded_file)
        )
        open_folder_button.pack(side=tk.LEFT, padx=5)
        
        new_download_button = ttk.Button(
            button_frame, 
            text="Download Another Video", 
            command=self.create_url_entry_ui
        )
        new_download_button.pack(side=tk.RIGHT, padx=5)
        
    def open_download_folder(self, file_path):
        """Open the folder containing the downloaded file"""
        try:
            # Determine the correct folder path to open
            if file_path and os.path.isfile(file_path):
                # If it's a file that exists, open its parent directory
                folder_path = os.path.dirname(os.path.abspath(file_path))
                print(f"Opening parent folder of file: {folder_path}")
            elif file_path and os.path.isdir(file_path):
                # If it's already a directory that exists, use it directly
                folder_path = file_path
                print(f"Opening directory: {folder_path}")
            elif hasattr(self, 'download_path') and self.download_path and os.path.isdir(self.download_path):
                # Fall back to the download path if it exists
                folder_path = self.download_path
                print(f"Opening download_path: {folder_path}")
            else:
                # Last resort: Default to Downloads folder
                folder_path = os.path.join(os.path.expanduser("~"), "Downloads")
                print(f"Opening default Downloads folder: {folder_path}")
            
            # Make sure the path exists before trying to open it
            if not os.path.exists(folder_path):
                raise FileNotFoundError(f"Folder not found: {folder_path}")
                
            # Open folder based on platform
            if sys.platform == 'win32':
                print(f"Opening Windows Explorer to: {folder_path}")
                # Use subprocess directly for opening folders
                subprocess.Popen(['explorer', folder_path], shell=False)
            elif sys.platform == 'darwin':  # macOS
                hidden_subprocess(['open', folder_path])
            else:  # Linux
                hidden_subprocess(['xdg-open', folder_path])
        except Exception as e:
            print(f"Error opening folder: {str(e)}")
            messagebox.showerror("Error", f"Could not open the folder: {str(e)}")
            
            # As a fallback, show the path so user can copy it
            if folder_path:
                messagebox.showinfo("Folder Path", f"The file should be located at: {folder_path}")
            elif self.download_path:
                messagebox.showinfo("Folder Path", f"The download folder is: {self.download_path}")

def main():
    """
    Main function to run the VimeoGrab GUI application
    """
    root = tk.Tk()
    app = VimeoGrabGUI(root)
    
    # Set window icon if available
    try:
        # You can add an icon file later
        pass
    except:
        pass
        
    # Center window on screen
    window_width = 500
    window_height = 300
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    center_x = int(screen_width/2 - window_width/2)
    center_y = int(screen_height/2 - window_height/2)
    root.geometry(f'{window_width}x{window_height}+{center_x}+{center_y}')
    
    root.mainloop()


if __name__ == "__main__":
    main()
