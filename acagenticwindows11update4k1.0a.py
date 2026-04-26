"""
Windows 11 AI Updater by ac
Version 0.1
"""

import datetime
import json
import math
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox

# ==================== CONFIG ====================
APP_NAME = "Windows 11 AI Updater"
APP_VERSION = "0.1"
APP_TITLE = f"{APP_NAME} by ac {APP_VERSION}"

CONFIG_FILE = os.path.expanduser("~/ac_windows_update_config.json")

try:
    from plyer import notification
    HAS_PLYER = True
except ImportError:
    HAS_PLYER = False

# Colors
BG = "#f3f3f3"
PANEL = "#ffffff"
TEXT = "#1f1f1f"
MUTED = "#606060"
BLUE = "#0067c0"
GREEN = "#107c10"
RED = "#c42b1c"

FONT = "Segoe UI"
FONT_TITLE = (FONT, 22, "bold")
FONT_BODY = (FONT, 10)


class Windows11AIUpdater:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("960x620")
        self.root.configure(bg=BG)
        self.root.minsize(800, 500)

        self.busy = False
        self.cancel_requested = False
        self.last_checked = "Never"
        self.available_updates = []
        self.log_queue = queue.Queue()
        self.update_history = self.load_history()

        self.build_ui()
        self.poll_log_queue()
        self.boot_check()

    def load_history(self):
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except:
            pass
        return {"update_history": []}

    def save_history(self):
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.update_history, f, indent=2)
        except:
            pass

    def add_to_history(self, action, details):
        entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "action": action,
            "details": details
        }
        self.update_history["update_history"].append(entry)
        self.update_history["update_history"] = self.update_history["update_history"][-30:]
        self.save_history()

    # ==================== UI ====================
    def build_ui(self):
        # Header
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=30, pady=20)

        tk.Label(header, text="Windows 11 AI Updater", font=FONT_TITLE, bg=BG, fg=TEXT).pack(side="left")
        tk.Label(header, text=f"v{APP_VERSION} by ac", font=(FONT, 9), bg=BG, fg=MUTED).pack(side="left", padx=10, pady=6)

        tk.Button(header, text="↻ Refresh", command=self.scan_updates, bg=BLUE, fg="white", relief="flat", padx=12, pady=6).pack(side="right")

        # Status
        self.status_frame = tk.Frame(self.root, bg=PANEL, relief="solid", bd=1)
        self.status_frame.pack(fill="x", padx=30, pady=10)

        self.status_title = tk.Label(self.status_frame, text="Ready", font=(FONT, 16, "bold"), bg=PANEL, fg=TEXT, anchor="w")
        self.status_title.pack(fill="x", padx=20, pady=(15, 5))

        self.status_text = tk.Label(self.status_frame, text="Click Check for Updates to begin", bg=PANEL, fg=MUTED, anchor="w", wraplength=800, justify="left")
        self.status_text.pack(fill="x", padx=20, pady=(0, 15))

        # Progress
        self.progress = tk.Canvas(self.status_frame, height=10, bg="#e6e6e6", highlightthickness=0)
        self.progress.pack(fill="x", padx=20, pady=(0, 15))

        # Buttons
        btn_frame = tk.Frame(self.root, bg=BG)
        btn_frame.pack(pady=15)

        for text, cmd in [
            ("Check for Updates", self.scan_updates),
            ("Install Updates", self.install_updates),
            ("System Health", self.run_health_check),
            ("Open Windows Update", self.open_real_windows_update),
            ("History", self.show_history)
        ]:
            tk.Button(btn_frame, text=text, command=cmd, bg=BLUE, fg="white", relief="flat", padx=16, pady=8, font=(FONT, 9, "bold")).pack(side="left", padx=6)

        # Log
        log_frame = tk.Frame(self.root, bg=BG)
        log_frame.pack(fill="both", expand=True, padx=30, pady=10)

        tk.Label(log_frame, text="Log", bg=BG, fg=MUTED, font=(FONT, 9)).pack(anchor="w")
        self.log_box = tk.Text(log_frame, bg="#0c0c0c", fg="#d7d7d7", font=("Consolas", 9), wrap="word")
        self.log_box.pack(fill="both", expand=True, pady=(5, 0))

        self.log(f"{APP_TITLE} started")

    def update_progress(self, value):
        self.progress.delete("all")
        w = self.progress.winfo_width()
        fill = int(w * (value / 100))
        self.progress.create_rectangle(0, 0, fill, 10, fill=BLUE, outline="")

    def log(self, text):
        stamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_box.insert("end", f"[{stamp}] {text}\n")
        self.log_box.see("end")

    def log_from_thread(self, text):
        self.log_queue.put(text)

    def poll_log_queue(self):
        try:
            while True:
                self.log(self.log_queue.get_nowait())
        except queue.Empty:
            pass
        self.root.after(100, self.poll_log_queue)

    # ==================== CORE ====================
    def set_status(self, title, text):
        self.status_title.config(text=title)
        self.status_text.config(text=text)

    def set_busy(self, busy):
        self.busy = busy
        # Simple disable for now

    def run_thread(self, target):
        if self.busy:
            messagebox.showinfo(APP_TITLE, "Please wait...")
            return
        self.cancel_requested = False
        self.set_busy(True)
        threading.Thread(target=target, daemon=True).start()

    def run_cmd(self, args):
        self.log_from_thread("> " + " ".join(args))
        try:
            result = subprocess.run(args, capture_output=True, text=True, timeout=300)
            for line in result.stdout.splitlines():
                if line.strip():
                    self.log_from_thread(line.strip())
            return result.returncode, result.stdout
        except Exception as e:
            self.log_from_thread(f"Error: {e}")
            return 1, str(e)

    def boot_check(self):
        if not shutil.which("winget"):
            self.log("⚠️ winget not found. Install from Microsoft Store.")

    # ==================== ACTIONS ====================
    def scan_updates(self):
        self.run_thread(self._scan_updates)

    def _scan_updates(self):
        self.root.after(0, lambda: self.set_status("Scanning...", "Checking for updates..."))
        self.root.after(0, lambda: self.update_progress(30))
        self.log("Starting scan...")

        if not shutil.which("winget"):
            self.finish("Error", "winget not found")
            return

        code, out = self.run_cmd(["winget", "upgrade", "--accept-source-agreements"])
        updates = [line for line in out.splitlines() if len(line.strip()) > 40 and not line.startswith(("Name", "-"))]

        self.last_checked = datetime.datetime.now().strftime("%b %d %I:%M %p")
        self.root.after(0, lambda: self.update_progress(100))

        if updates:
            self.available_updates = updates[:30]
            self.root.after(0, lambda: self.set_status(f"{len(updates)} Updates Found", "Ready to install"))
            self.log(f"Found {len(updates)} updates")
        else:
            self.root.after(0, lambda: self.set_status("Up to Date", "No updates available"))
            self.log("No updates found")

        self.root.after(800, lambda: self.set_busy(False))

    def install_updates(self):
        self.run_thread(self._install_updates)

    def _install_updates(self):
        self.root.after(0, lambda: self.set_status("Installing...", "This may take several minutes"))
        self.root.after(0, lambda: self.update_progress(20))

        code, out = self.run_cmd(["winget", "upgrade", "--all", "--accept-package-agreements", "--accept-source-agreements"])

        self.root.after(0, lambda: self.update_progress(100))
        if code == 0:
            self.log("Installation completed successfully")
            self.add_to_history("Install", "winget --all completed")
        else:
            self.log(f"Installation finished with code {code}")

        self.root.after(1000, lambda: self.set_busy(False))

    def run_health_check(self):
        self.run_thread(self._run_health_check)

    def _run_health_check(self):
        self.root.after(0, lambda: self.set_status("Health Check", "Running SFC /scannow..."))
        self.root.after(0, lambda: self.update_progress(40))
        code, _ = self.run_cmd(["sfc", "/scannow"])
        self.root.after(0, lambda: self.update_progress(100))
        self.log("Health check completed")

    def open_real_windows_update(self):
        if os.name == "nt":
            try:
                os.startfile("ms-settings:windowsupdate")
                self.log("Opened official Windows Update")
            except:
                self.log("Could not open Windows Update page")

    def show_history(self):
        history = self.update_history.get("update_history", [])
        if not history:
            messagebox.showinfo("History", "No history yet.")
            return
        text = "\n\n".join([f"{h['timestamp'][:16]} | {h['action']}\n{h['details']}" for h in history[-15:]])
        messagebox.showinfo("Update History", text)

    def finish(self, title, text):
        self.root.after(0, lambda: self.set_status(title, text))
        self.root.after(0, lambda: self.set_busy(False))


def main():
    root = tk.Tk()
    app = Windows11AIUpdater(root)
    root.mainloop()


if __name__ == "__main__":
    main()
