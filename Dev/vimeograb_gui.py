#!/usr/bin/env python3
"""
VimeoGrab GUI v1.1 - Graphical User Interface for VimeoGrab
Downloads private Vimeo videos using just a link with an easy-to-use interface

Version: 1.1
Status: Stable

Changelog:
v1.1 - Improved progress indication for two-phase downloads
      - Now clearly distinguishes between download and processing phases
      - Added standalone EXE compilation support
      - Fixed "Open Folder" button functionality
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
import re
import json
from urllib.parse import urlparse

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Try to import the core module
try:
    import vimeograb_core as vgcore
except ImportError:
    messagebox.showerror("Import Error", "Could not import vimeograb_core. Make sure it's in the parent directory.")
    sys.exit(1)

# Main GUI class for VimeoGrab
# Uses a step-by-step workflow for URL input, quality selection, and download
# Handles both download and processing phases with clear progress indication
class VimeoGrabGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("VimeoGrab v1.0")
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
        """Create the quality selection screen"""
        # Clear the frame
        for widget in self.main_frame.winfo_children():
            widget.destroy()
            
        # Title
        title_label = ttk.Label(
            self.main_frame, 
            text=f"Select Quality for:\n{video_title}", 
            font=("Arial", 12, "bold"),
            justify=tk.CENTER
        )
        title_label.pack(pady=(0, 15))
        
        # Quality selection
        quality_frame = ttk.Frame(self.main_frame)
        quality_frame.pack(fill=tk.X, pady=5)
        
        # Create radio buttons for quality options
        self.quality_var = tk.StringVar(value="best")
        
        for i, quality in enumerate(self.available_qualities):
            quality_rb = ttk.Radiobutton(
                quality_frame,
                text=quality['label'],
                value=quality['height'],
                variable=self.quality_var
            )
            quality_rb.pack(anchor=tk.W, padx=20, pady=2)
            
        # Buttons
        button_frame = ttk.Frame(self.main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        back_button = ttk.Button(
            button_frame, 
            text="Back", 
            command=self.create_url_entry_ui
        )
        back_button.pack(side=tk.LEFT, padx=5)
        
        download_button = ttk.Button(
            button_frame, 
            text="Download", 
            command=self.start_download
        )
        download_button.pack(side=tk.RIGHT, padx=5)
        
    def start_download(self):
        """Start the download process"""
        # Get selected quality
        self.selected_quality = self.quality_var.get()
        
        # Determine download path
        if self.save_to_downloads_var.get():
            # Use downloads folder
            downloads_path = os.path.join(os.path.expanduser("~"), "Downloads")
            self.download_path = downloads_path
        else:
            # Ask user for download location
            self.download_path = filedialog.askdirectory(
                title="Select Download Location"
            )
            if not self.download_path:  # User cancelled
                return
                
        # Show download progress UI
        self.create_download_progress_ui()
        
        # Start download thread
        self.download_thread = threading.Thread(
            target=self.download_video,
            daemon=True
        )
        self.download_thread.start()
        
    def create_download_progress_ui(self):
        """Create download progress UI"""
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
        
    def download_video(self):
        """Download the video in a separate thread"""
        try:
            # Build yt-dlp command
            cmd = ['yt-dlp', 
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
            
            # Start the process
            self.process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
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
                        # Update progress bar to show we're in processing phase
                        self.root.after(0, lambda: self.update_progress(100))  # Set progress to 100%
                        self.root.after(0, lambda: self.update_status("Processing video and audio streams..."))
                        # Switch to indeterminate progress mode for processing
                        self.root.after(0, lambda: self.progress_bar.config(mode='indeterminate'))
                        self.root.after(0, lambda: self.progress_bar.start(10))
                    
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
                        
                        # Update progress bar
                        try:
                            percent = float(percent_str.strip('%'))
                            self.root.after(0, lambda p=percent: self.update_progress(p))
                        except (ValueError, TypeError):
                            pass
                            
                        # Update status label
                        status_text = f"Downloading: {speed_str.strip()}, ETA: {eta_str.strip()}"
                        self.root.after(0, lambda t=status_text: self.update_status(t))
                
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
            self.root.after(0, lambda: self.progress_bar.stop())
            
            # If we didn't capture the file path but know the download directory,
            # we can still open the directory
            if not downloaded_file and self.download_path:
                print(f"No specific file path captured, using download directory: {self.download_path}")
                downloaded_file = self.download_path  # Will be treated as a directory in open_download_folder
            
            # Wait for process to complete
            self.process.wait()
            
            if self.process.returncode == 0:
                # Download successful
                self.root.after(0, lambda: self.show_completion(downloaded_file))
            else:
                # Download failed
                self.root.after(0, lambda: messagebox.showerror(
                    "Error", "Failed to download the video"
                ))
                self.root.after(0, self.create_url_entry_ui)
                
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror(
                "Error", f"Error during download: {str(e)}"
            ))
            self.root.after(0, self.create_url_entry_ui)
        
    def update_progress(self, percent):
        """Update progress bar"""
        self.progress_var.set(percent)
        
    def update_status(self, status_text):
        """Update status label"""
        self.status_label.config(text=status_text)
        
    def cancel_download(self):
        """Cancel the download"""
        if self.process:
            try:
                self.process.terminate()
            except Exception:
                pass
                
        messagebox.showinfo("Cancelled", "Download was cancelled")
        self.create_url_entry_ui()
        
    def show_completion(self, downloaded_file):
        """Show completion message"""
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
            # If we don't have a file path, use the download path directly
            if not file_path and self.download_path:
                folder_path = self.download_path
            elif file_path:
                # Even if the exact file doesn't exist, try to open its parent directory
                folder_path = os.path.dirname(os.path.abspath(file_path))
            else:
                # Default to Downloads folder
                folder_path = os.path.join(os.path.expanduser("~"), "Downloads")
                
            print(f"Attempting to open folder: {folder_path}")
            
            # Make sure the path exists
            if not os.path.exists(folder_path):
                raise FileNotFoundError(f"Folder not found: {folder_path}")
                
            # Open folder based on platform
            if sys.platform == 'win32':
                # Use subprocess instead of os.startfile for better error handling
                subprocess.Popen(['explorer', folder_path])
            elif sys.platform == 'darwin':  # macOS
                subprocess.call(['open', folder_path])
            else:  # Linux
                subprocess.call(['xdg-open', folder_path])
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
