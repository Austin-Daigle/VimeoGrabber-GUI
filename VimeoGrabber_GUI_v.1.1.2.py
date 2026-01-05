#!/usr/bin/env python3
"""
VimeoGrab GUI v1.1.2 - Graphical User Interface for VimeoGrab
Downloads private Vimeo videos using just a link with an easy-to-use interface

Version: 1.1.2
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
import shutil
import urllib.request
import zipfile
import tempfile
import traceback
import ssl
from collections import deque

try:
    import certifi
except Exception:
    certifi = None

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

def _get_app_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))

def _is_dir_writable(path):
    try:
        os.makedirs(path, exist_ok=True)
        test_file = os.path.join(path, f".write_test_{os.getpid()}")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(test_file)
        return True
    except Exception:
        return False

def get_tools_dir():
    base_dir = _get_app_base_dir()
    portable_tools = os.path.join(base_dir, "tools")
    if _is_dir_writable(portable_tools):
        return portable_tools

    local_appdata = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    fallback_tools = os.path.join(local_appdata, "VimeoGrab", "tools")
    os.makedirs(fallback_tools, exist_ok=True)
    return fallback_tools

def _with_tools_on_path(env=None):
    env = (env or os.environ).copy()
    tools_dir = get_tools_dir()
    path_val = env.get("PATH", "")
    if tools_dir and tools_dir not in path_val.split(os.pathsep):
        env["PATH"] = tools_dir + os.pathsep + path_val

    try:
        tmp_dir = os.path.join(get_tools_dir(), "tmp")
        os.makedirs(tmp_dir, exist_ok=True)
        env.setdefault("TEMP", tmp_dir)
        env.setdefault("TMP", tmp_dir)
        env.setdefault("TMPDIR", tmp_dir)
    except Exception:
        pass

    for key in ("YT_DLP_ARGS", "YTDLP_ARGS", "YOUTUBE_DL_OPTIONS"):
        try:
            env.pop(key, None)
        except Exception:
            pass

    try:
        if certifi is not None:
            ca_path = certifi.where()
            env.setdefault("SSL_CERT_FILE", ca_path)
            env.setdefault("REQUESTS_CA_BUNDLE", ca_path)
    except Exception:
        pass
    return env

def _is_ssl_related_error(text):
    t = (text or "").lower()
    return (
        "certificate_verify_failed" in t
        or "unable to get local issuer certificate" in t
        or "sslc" in t
        or "tls" in t and "handshake" in t
        or "ssl:" in t
    )

def _format_recent_lines(lines, limit=30):
    if not lines:
        return ""
    try:
        tail = list(lines)[-limit:]
    except Exception:
        tail = lines
    return "\n".join(tail)

def _is_vimeo_login_required_error(text):
    t = (text or "").lower()
    return (
        "only works when logged-in" in t
        or "provide account credentials" in t
        or "use --cookies" in t
        or "use --cookies-from-browser" in t
        or "login" in t and "vimeo" in t
    )

def _is_chrome_cookie_copy_error(text):
    t = (text or "").lower()
    return "could not copy chrome cookie database" in t

def _get_browser_cookie_sources():
    sources = []
    try:
        if sys.platform == 'win32':
            local_appdata = os.environ.get('LOCALAPPDATA', '')
            roaming_appdata = os.environ.get('APPDATA', '')

            chrome_profile = os.path.join(local_appdata, 'Google', 'Chrome', 'User Data')
            edge_profile = os.path.join(local_appdata, 'Microsoft', 'Edge', 'User Data')
            firefox_profiles = os.path.join(roaming_appdata, 'Mozilla', 'Firefox', 'Profiles')

            if chrome_profile and os.path.isdir(chrome_profile):
                sources.append('chrome')
            if edge_profile and os.path.isdir(edge_profile):
                sources.append('edge')
            if firefox_profiles and os.path.isdir(firefox_profiles):
                sources.append('firefox')
    except Exception:
        pass

    # Always keep a stable preference order when possible
    preferred = ['chrome', 'edge', 'firefox']
    if sources:
        return [b for b in preferred if b in sources]
    return preferred

def _append_startup_log(message):
    try:
        log_path = os.path.join(get_tools_dir(), "startup.log")
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {message}\n")
    except Exception:
        pass

def get_ffmpeg_exe_path():
    if sys.platform == "win32":
        tools_path = os.path.join(get_tools_dir(), "ffmpeg.exe")
        if os.path.exists(tools_path):
            return tools_path
    found = shutil.which("ffmpeg")
    if found:
        return found
    return None

def check_ffmpeg_installed():
    ffmpeg_path = get_ffmpeg_exe_path()
    if not ffmpeg_path:
        return False
    try:
        result = hidden_subprocess([ffmpeg_path, "-version"], stdout=subprocess.PIPE, text=True, check=False)
        return result.returncode == 0
    except Exception:
        return False

def _ssl_context():
    ctx = ssl.create_default_context()
    try:
        if certifi is not None:
            ctx.load_verify_locations(cafile=certifi.where())
    except Exception:
        pass
    return ctx

def _ps_escape_single_quotes(value):
    return str(value).replace("'", "''")

def _download_file_powershell(url, dest_path, cancel_event=None):
    if sys.platform != "win32":
        raise RuntimeError("powershell_download_not_supported")

    url_escaped = _ps_escape_single_quotes(url)
    dest_escaped = _ps_escape_single_quotes(dest_path)

    ps_script = (
        "$ProgressPreference='SilentlyContinue';"
        "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12;"
        f"Invoke-WebRequest -Uri '{url_escaped}' -OutFile '{dest_escaped}'"
    )

    startupinfo = None
    creationflags = 0
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0
        if hasattr(subprocess, 'CREATE_NO_WINDOW'):
            creationflags = subprocess.CREATE_NO_WINDOW

    proc = subprocess.Popen(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        startupinfo=startupinfo,
        creationflags=creationflags,
    )

    try:
        while proc.poll() is None:
            if cancel_event and cancel_event.is_set():
                try:
                    proc.terminate()
                except Exception:
                    pass
                raise RuntimeError("cancelled")
            time.sleep(0.1)
    finally:
        if proc.poll() is not None:
            try:
                out, err = proc.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                try:
                    proc.kill()
                except Exception:
                    pass
                out, err = ("", "")
        else:
            out, err = ("", "")

    if proc.returncode != 0:
        raise RuntimeError(f"powershell_download_failed: {err.strip() or out.strip()}")

def _download_file(url, dest_path, progress_cb=None, cancel_event=None):
    req = urllib.request.Request(url, headers={"User-Agent": "VimeoGrab/1.1.2"})
    try:
        with urllib.request.urlopen(req, context=_ssl_context(), timeout=60) as resp:
            total = resp.headers.get("Content-Length")
            total = int(total) if total and total.isdigit() else None
            downloaded = 0
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            with open(dest_path, "wb") as out:
                while True:
                    if cancel_event and cancel_event.is_set():
                        raise RuntimeError("cancelled")
                    chunk = resp.read(1024 * 256)
                    if not chunk:
                        break
                    out.write(chunk)
                    downloaded += len(chunk)
                    if progress_cb:
                        progress_cb(downloaded, total)
            return
    except Exception as e:
        msg = str(e)
        if sys.platform == "win32" and ("CERTIFICATE_VERIFY_FAILED" in msg or isinstance(e, ssl.SSLCertVerificationError)):
            _append_startup_log(f"download_ssl_failed_fallback_powershell: {msg}")
            _download_file_powershell(url, dest_path, cancel_event=cancel_event)
            return
        raise

def _install_ytdlp_windows(tools_dir, progress_cb=None, cancel_event=None):
    url = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
    dest = os.path.join(tools_dir, "yt-dlp.exe")
    tmp = dest + ".download"
    _download_file(url, tmp, progress_cb=progress_cb, cancel_event=cancel_event)
    if os.path.exists(dest):
        try:
            os.remove(dest)
        except Exception:
            pass
    os.replace(tmp, dest)
    return dest

def _install_ffmpeg_windows(tools_dir, progress_cb=None, cancel_event=None):
    is_64 = platform.machine().endswith("64")
    url = "https://github.com/BtbN/FFmpeg-Builds/releases/latest/download/ffmpeg-master-latest-win64-gpl.zip" if is_64 else "https://github.com/BtbN/FFmpeg-Builds/releases/latest/download/ffmpeg-master-latest-win32-gpl.zip"
    zip_path = os.path.join(tools_dir, "ffmpeg.zip")
    tmp_zip = zip_path + ".download"
    _download_file(url, tmp_zip, progress_cb=progress_cb, cancel_event=cancel_event)
    if os.path.exists(zip_path):
        try:
            os.remove(zip_path)
        except Exception:
            pass
    os.replace(tmp_zip, zip_path)

    with zipfile.ZipFile(zip_path, "r") as zf:
        ffmpeg_member = None
        ffprobe_member = None
        for name in zf.namelist():
            lower = name.lower()
            if lower.endswith("/ffmpeg.exe"):
                ffmpeg_member = name
            elif lower.endswith("/ffprobe.exe"):
                ffprobe_member = name
        if not ffmpeg_member:
            raise RuntimeError("ffmpeg.exe not found in archive")

        ffmpeg_dest = os.path.join(tools_dir, "ffmpeg.exe")
        ffprobe_dest = os.path.join(tools_dir, "ffprobe.exe")
        with zf.open(ffmpeg_member) as src, open(ffmpeg_dest, "wb") as dst:
            shutil.copyfileobj(src, dst)
        if ffprobe_member:
            with zf.open(ffprobe_member) as src, open(ffprobe_dest, "wb") as dst:
                shutil.copyfileobj(src, dst)

    try:
        os.remove(zip_path)
    except Exception:
        pass

    return os.path.join(tools_dir, "ffmpeg.exe")

class DependencyInstallerUI:
    def __init__(self, root, missing_items, use_root_window=False):
        self.root = root
        self.missing_items = missing_items
        self.cancel_event = threading.Event()
        self.success = False

        self._owns_root = bool(use_root_window)
        if use_root_window:
            self.top = root
        else:
            self.top = tk.Toplevel(root)

        self.top.title("VimeoGrab Setup")
        self.top.geometry("520x260")
        self.top.resizable(False, False)
        self.top.protocol("WM_DELETE_WINDOW", self._on_cancel)

        try:
            self.top.deiconify()
        except Exception:
            pass

        frame = ttk.Frame(self.top, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        title = ttk.Label(frame, text="Required components are missing", font=("Arial", 12, "bold"))
        title.pack(anchor=tk.W)

        items_text = "\n".join([f"- {x}" for x in self.missing_items])
        items = ttk.Label(frame, text=items_text, font=("Arial", 10))
        items.pack(anchor=tk.W, pady=(10, 10))

        self.status_var = tk.StringVar(value="Install now?")
        status = ttk.Label(frame, textvariable=self.status_var, font=("Arial", 10))
        status.pack(anchor=tk.W, pady=(0, 10))

        self.progress = ttk.Progressbar(frame, mode="determinate", length=460, maximum=100)
        self.progress.pack(pady=(0, 15))
        self.progress["value"] = 0

        btns = ttk.Frame(frame)
        btns.pack(fill=tk.X)

        self.install_btn = ttk.Button(btns, text="Install", command=self._on_install)
        self.install_btn.pack(side=tk.RIGHT, padx=(5, 0))

        self.cancel_btn = ttk.Button(btns, text="Cancel", command=self._on_cancel)
        self.cancel_btn.pack(side=tk.RIGHT)

        if not use_root_window:
            try:
                if root.state() != "withdrawn":
                    self.top.transient(root)
            except Exception:
                pass
        self.top.grab_set()

        try:
            self.top.update_idletasks()
            w = self.top.winfo_width()
            h = self.top.winfo_height()
            sw = self.top.winfo_screenwidth()
            sh = self.top.winfo_screenheight()
            x = int(sw / 2 - w / 2)
            y = int(sh / 2 - h / 2)
            self.top.geometry(f"{w}x{h}+{x}+{y}")
            self.top.lift()
            self.top.attributes("-topmost", True)
            self.top.after(250, lambda: self.top.attributes("-topmost", False))
            self.top.focus_force()
        except Exception:
            pass

    def run(self):
        if self._owns_root:
            try:
                self.top.mainloop()
            except Exception:
                pass
            return self.success

        self.root.wait_window(self.top)
        return self.success

    def _set_status(self, text):
        self.status_var.set(text)

    def _set_progress(self, value):
        try:
            self.progress["value"] = max(0, min(100, float(value)))
        except Exception:
            pass

    def _on_cancel(self):
        self.cancel_event.set()
        self.success = False
        try:
            self.top.destroy()
        except Exception:
            pass

    def _on_install(self):
        self.install_btn.config(state="disabled")
        self.cancel_btn.config(text="Close")
        threading.Thread(target=self._install_worker, daemon=True).start()

    def _install_worker(self):
        try:
            tools_dir = get_tools_dir()
            total_steps = sum(1 for _ in self.missing_items)
            completed_steps = 0

            def step_progress(downloaded, total):
                if total and total > 0:
                    pct = (downloaded / total) * 100.0
                else:
                    pct = 0.0
                overall = (completed_steps / max(1, total_steps)) * 100.0
                blended = overall + (pct / max(1, total_steps))
                self.root.after(0, lambda v=blended: self._set_progress(v))

            for item in self.missing_items:
                if self.cancel_event.is_set():
                    raise RuntimeError("cancelled")
                if item == "yt-dlp":
                    self.root.after(0, lambda: self._set_status("Downloading yt-dlp..."))
                    _install_ytdlp_windows(tools_dir, progress_cb=step_progress, cancel_event=self.cancel_event)
                elif item == "ffmpeg":
                    self.root.after(0, lambda: self._set_status("Downloading ffmpeg..."))
                    _install_ffmpeg_windows(tools_dir, progress_cb=step_progress, cancel_event=self.cancel_event)
                completed_steps += 1
                self.root.after(0, lambda v=(completed_steps / max(1, total_steps)) * 100.0: self._set_progress(v))

            self.root.after(0, lambda: self._set_status("Installation complete"))
            self.root.after(0, lambda: self._set_progress(100))
            self.success = True
            self.root.after(0, lambda: self.top.destroy())
        except Exception as e:
            if str(e) == "cancelled":
                return
            _append_startup_log(f"install_failed: {traceback.format_exc()}")
            def _fail_ui():
                try:
                    messagebox.showerror("Setup Failed", str(e), parent=self.top)
                except Exception:
                    pass
                try:
                    self._set_status("Install failed. Check your internet/time settings and try again.")
                    self.install_btn.config(state="normal")
                    self.cancel_btn.config(text="Cancel")
                except Exception:
                    pass
            self.root.after(0, _fail_ui)

def ensure_runtime_dependencies(root, use_root_window=False):
    _append_startup_log("ensure_runtime_dependencies: start")
    missing = []
    if not check_ytdl_installed():
        missing.append("yt-dlp")
    if not check_ffmpeg_installed():
        missing.append("ffmpeg")
    if not missing:
        _append_startup_log("ensure_runtime_dependencies: nothing_missing")
        return True

    _append_startup_log(f"ensure_runtime_dependencies: missing={','.join(missing)}")
    ui = DependencyInstallerUI(root, missing, use_root_window=use_root_window)
    return ui.run()

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
     
    if sys.platform == 'win32':
        tools_path = os.path.join(get_tools_dir(), 'yt-dlp.exe')
        if os.path.exists(tools_path):
            return tools_path
    else:
        tools_path = os.path.join(get_tools_dir(), 'yt-dlp')
        if os.path.exists(tools_path):
            return tools_path
     
    # When running as a script, use the system's yt-dlp
    return 'yt-dlp'

def check_ytdl_installed():
    """Check if yt-dlp is available"""
    ytdlp_path = get_ytdlp_path()
    
    try:
        result = hidden_subprocess([ytdlp_path, '--version'], 
                              stdout=subprocess.PIPE, 
                              text=True, 
                              check=False,
                              env=_with_tools_on_path())
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
        self.root.title("VimeoGrab v1.1.2")
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
        self.ytdlp_auth_args = []
        self.ytdlp_transport_args = []
        self.ytdlp_auth_source = ""
        
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
            ytdlp_path = get_ytdlp_path()
            env = _with_tools_on_path()

            def run_info(auth_args=None, transport_args=None):
                auth_args = auth_args or []
                transport_args = transport_args or []
                cmd = [ytdlp_path, '--ignore-config'] + auth_args + transport_args + ['--dump-json', self.vimeo_url]
                return hidden_subprocess(cmd, stdout=subprocess.PIPE, text=True, check=False, env=env)

            def error_text(res):
                return (res.stderr or "") + "\n" + (res.stdout or "")

            self.ytdlp_auth_args = []
            self.ytdlp_transport_args = []
            self.ytdlp_auth_source = ""

            cookie_copy_failed = False

            result = run_info()

            if result.returncode != 0 and _is_ssl_related_error(error_text(result)):
                result = run_info(transport_args=['--no-check-certificate'])
                if result.returncode == 0:
                    self.ytdlp_transport_args = ['--no-check-certificate']

            login_required = result.returncode != 0 and _is_vimeo_login_required_error(error_text(result))
            if login_required:
                cookies_path = get_cookies_path()
                auth_candidates = []
                if cookies_path:
                    auth_candidates.append((['--cookies', cookies_path], 'cookies_file'))
                for browser in _get_browser_cookie_sources():
                    auth_candidates.append((['--cookies-from-browser', browser], f'browser:{browser}'))

                last_result = result
                for auth_args, source in auth_candidates:
                    transport_args = list(self.ytdlp_transport_args)
                    last_result = run_info(auth_args=auth_args, transport_args=transport_args)

                    if _is_chrome_cookie_copy_error(error_text(last_result)):
                        cookie_copy_failed = True

                    if last_result.returncode != 0 and not transport_args and _is_ssl_related_error(error_text(last_result)):
                        transport_args = ['--no-check-certificate']
                        last_result = run_info(auth_args=auth_args, transport_args=transport_args)

                    if last_result.returncode == 0:
                        self.ytdlp_auth_args = auth_args
                        self.ytdlp_transport_args = transport_args
                        self.ytdlp_auth_source = source
                        _append_startup_log(f"ytdlp_auth_selected: {source}")
                        result = last_result
                        break

                if result.returncode != 0:
                    result = last_result

            if result.returncode != 0:
                details = (result.stderr or "").strip()
                if not details:
                    details = (result.stdout or "").strip()
                if details:
                    _append_startup_log(f"ytdlp_info_failed: {details}")

                if login_required:
                    details = (
                        "This Vimeo link requires you to be logged in.\n\n"
                        "Please sign in to Vimeo in Microsoft Edge or Google Chrome on this machine, then try again.\n\n"
                        + details
                    )

                if cookie_copy_failed:
                    details = (
                        details
                        + "\n\n"
                        + "Chrome cookie access failed. This usually happens when Chrome (or Chrome background processes) has the Cookies database locked.\n"
                        + "Close all Chrome windows, then in Chrome go to Settings -> System and disable 'Continue running background apps when Google Chrome is closed', then try again."
                    )
                self.root.after(0, lambda: messagebox.showerror(
                    "Error", f"Failed to get video information:\n\n{details}"
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
                return
                
            self.download_path = custom_path
                
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
            # Get path to yt-dlp (bundled or system)
            ytdlp_path = get_ytdlp_path()
            ffmpeg_path = get_ffmpeg_exe_path()

            env = _with_tools_on_path()

            auth_args = list(getattr(self, 'ytdlp_auth_args', []) or [])
            transport_args = list(getattr(self, 'ytdlp_transport_args', []) or [])

            def run_once(extra_args=None):
                extra_args = extra_args or []
                output_tail = deque(maxlen=200)

                cmd = [ytdlp_path,
                       '--ignore-config',
                       *auth_args,
                       *transport_args,
                       '--newline',
                       '--progress-template', "%(progress._percent_str)s|%(progress._speed_str)s|%(progress._eta_str)s"]

                if ffmpeg_path:
                    cmd.extend(['--ffmpeg-location', os.path.dirname(ffmpeg_path)])

                if extra_args:
                    cmd.extend(extra_args)
            
                # Format and quality selection
                if self.selected_quality == "best":
                    cmd.extend(['--format', 'bestvideo+bestaudio/best'])
                elif self.selected_quality == "worst":
                    cmd.extend(['--format', 'worstvideo+worstaudio/worst'])
                else:
                    cmd.extend(['--format', f'bestvideo[height<={self.selected_quality}]+bestaudio/best[height<={self.selected_quality}]'])

                cmd.extend(['--paths', self.download_path])
                cmd.extend(['--output', '%(title)s.%(ext)s'])
                cmd.append(self.vimeo_url)

                # Start the process using our hidden subprocess helper
                startupinfo = None
                if sys.platform == 'win32':
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    startupinfo.wShowWindow = 0  # SW_HIDE

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
                    env=env,
                    **kwargs
                )

                downloaded_file = None
                in_download_phase = True

                for line in self.process.stdout:
                    line = line.strip()
                    output_tail.append(line)
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

                # Stop the progress bar animation if it was in indeterminate mode
                self.root.after(0, lambda: self.progress_bar.stop())

                if not downloaded_file and self.download_path:
                    print(f"No specific file path captured, using download directory: {self.download_path}")
                    downloaded_file = self.download_path

                self.process.wait()
                return self.process.returncode, downloaded_file, output_tail

            rc, downloaded_file, output_tail = run_once()
            if rc != 0 and _is_ssl_related_error(_format_recent_lines(output_tail)):
                self.root.after(0, lambda: self.update_status("Retrying with relaxed certificate checks..."))
                rc, downloaded_file, output_tail = run_once(extra_args=['--no-check-certificate'])

            if rc == 0:
                self.root.after(0, lambda: self.show_completion(downloaded_file))
            else:
                details = _format_recent_lines(output_tail)
                if details:
                    _append_startup_log(f"ytdlp_download_failed: {details}")
                self.root.after(0, lambda d=details: messagebox.showerror(
                    "Error", f"Failed to download the video.\n\n{d}" if d else "Failed to download the video."
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
    try:
        _append_startup_log("main: start")
        _append_startup_log("main: before_tk_setup")
        setup_root = tk.Tk()
        _append_startup_log("main: after_tk_setup")

        ok = ensure_runtime_dependencies(setup_root, use_root_window=True)
        try:
            setup_root.destroy()
        except Exception:
            pass
        if not ok:
            _append_startup_log("main: dependencies_cancelled_or_failed")
            return

        _append_startup_log("main: before_tk_main")
        root = tk.Tk()
        _append_startup_log("main: after_tk_main")
        app = VimeoGrabGUI(root)
    except Exception:
        _append_startup_log(f"startup_failed: {traceback.format_exc()}")
        try:
            tmp_root = tk.Tk()
            tmp_root.withdraw()
            messagebox.showerror("Startup Failed", "VimeoGrab failed to start. See tools\\startup.log for details.", parent=tmp_root)
            tmp_root.destroy()
        except Exception:
            pass
        return
    
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
