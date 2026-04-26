"""
Windows 11 AI Updater by ac
Version 1.0
"""
import datetime
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, messagebox

# ==================== CONFIG ====================
APP_NAME = "Windows 11 AI Updater"
APP_VERSION = "1.0"
APP_TITLE = f"{APP_NAME} by ac {APP_VERSION}"

CONFIG_FILE = os.path.expanduser("~/ac_windows_update_config.json")

try:
    from plyer import notification
    HAS_PLYER = True
except ImportError:
    HAS_PLYER = False

# Windows 11 colors
BG = "#f3f3f3"
CARD_BG = "#ffffff"
TEXT_PRIMARY = "#1f1f1f"
TEXT_SECONDARY = "#616161"
ACCENT = "#0067c0"
ACCENT_HOVER = "#005ba1"
ACCENT_DISABLED = "#b3d4f0"
RED = "#c42b1c"
GREEN = "#107c10"
PROGRESS_COLOR = "#0067c0"

try:
    _AVAILABLE_FONTS = set(tkfont.families())
except Exception:
    _AVAILABLE_FONTS = set()

FONT_FAMILY = "Segoe UI Variable" if "Segoe UI Variable" in _AVAILABLE_FONTS else "Segoe UI"
FONT_TITLE = (FONT_FAMILY, 20, "bold")
FONT_SUBTITLE = (FONT_FAMILY, 12)
FONT_BODY = (FONT_FAMILY, 11)
FONT_SMALL = (FONT_FAMILY, 9)

class Windows11AIUpdater:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("800x700")
        self.root.configure(bg=BG)
        self.root.minsize(720, 600)

        # State
        self.busy = False
        self.cancel_requested = False
        self.last_checked = "Never"
        self.available_updates = []          # list of dicts: {name, id, version, available}
        self.update_history = self.load_history()
        self.log_queue = queue.Queue()

        self.setup_styles()
        self.build_ui()
        self.poll_log_queue()

    # ---------- History persistence ----------
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

    # ---------- ttk styling ----------
    def setup_styles(self):
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")
        else:
            style.theme_use("default")

        # Frame
        style.configure("Card.TFrame", background=CARD_BG, relief="flat", borderwidth=0)
        style.configure("Section.TFrame", background=BG, relief="flat")
        style.configure("Transparent.TFrame", background=BG)

        # Labels
        style.configure("Title.TLabel", font=FONT_TITLE, foreground=TEXT_PRIMARY, background=CARD_BG)
        style.configure("Subtitle.TLabel", font=FONT_SUBTITLE, foreground=TEXT_SECONDARY, background=CARD_BG)
        style.configure("Body.TLabel", font=FONT_BODY, foreground=TEXT_PRIMARY, background=CARD_BG)
        style.configure("Muted.TLabel", font=FONT_BODY, foreground=TEXT_SECONDARY, background=CARD_BG)
        style.configure("UpdateName.TLabel", font=FONT_BODY, foreground=TEXT_PRIMARY, background=CARD_BG)
        style.configure("UpdateVersion.TLabel", font=FONT_SMALL, foreground=TEXT_SECONDARY, background=CARD_BG)
        style.configure("Link.TLabel", font=(FONT_FAMILY, 10, "underline"), foreground=ACCENT, background=BG)

        # Button – primary
        style.configure("Primary.TButton",
                        font=(FONT_FAMILY, 10, "bold"),
                        background=ACCENT,
                        foreground="white",
                        borderwidth=0,
                        focusthickness=0,
                        relief="flat")
        style.map("Primary.TButton",
                  background=[("active", ACCENT_HOVER), ("disabled", ACCENT_DISABLED)],
                  foreground=[("disabled", "#ffffff")])

        # Button – secondary
        style.configure("Secondary.TButton",
                        font=(FONT_FAMILY, 10),
                        background="#e8e8e8",
                        foreground=TEXT_PRIMARY,
                        borderwidth=0,
                        focusthickness=0,
                        relief="flat")
        style.map("Secondary.TButton",
                  background=[("active", "#d9d9d9")])

        # Progress bar
        style.configure("TProgressbar",
                        thickness=10,
                        background=PROGRESS_COLOR,
                        troughcolor="#e6e6e6")

        # Scrollbar
        style.configure("Vertical.TScrollbar", background=CARD_BG, arrowcolor=TEXT_PRIMARY)

    # ---------- UI construction ----------
    def build_ui(self):
        # Main container
        main = ttk.Frame(self.root, style="Section.TFrame")
        main.pack(fill="both", expand=True, padx=0, pady=0)

        # Title bar
        title_bar = ttk.Frame(main, style="Transparent.TFrame")
        title_bar.pack(fill="x", padx=30, pady=(20, 10))
        tk.Label(title_bar, text="Windows Update", font=FONT_TITLE, bg=BG, fg=TEXT_PRIMARY).pack(side="left")
        tk.Label(title_bar, text=f"by ac v{APP_VERSION}", font=FONT_SMALL, bg=BG, fg=TEXT_SECONDARY).pack(side="left", padx=10)

        # White card
        card = ttk.Frame(main, style="Card.TFrame", padding=20, relief="solid", borderwidth=0)
        card.pack(fill="both", expand=True, padx=30, pady=(0, 20))
        card.columnconfigure(0, weight=1)

        # Status message
        self.status_title = ttk.Label(card, text="You're up to date", style="Title.TLabel", anchor="center")
        self.status_title.grid(row=0, column=0, pady=(10, 5), sticky="ew")

        self.status_text = ttk.Label(card, text="Last checked: Never", style="Subtitle.TLabel", anchor="center")
        self.status_text.grid(row=1, column=0, pady=(0, 10), sticky="ew")

        # Progress bar (hidden by default)
        self.progress = ttk.Progressbar(card, mode='indeterminate', length=300)
        self.progress.grid(row=2, column=0, pady=(0, 15))
        self.progress.grid_remove()

        # Primary action button
        self.primary_btn = ttk.Button(card, text="Check for updates", style="Primary.TButton",
                                      command=self.scan_updates)
        self.primary_btn.grid(row=3, column=0, pady=(0, 20))
        self.primary_btn.grid_remove()   # shown after state set

        # Updates list area (hidden until updates found)
        self.list_frame = ttk.Frame(card, style="Card.TFrame")
        self.list_frame.grid(row=4, column=0, sticky="nsew", pady=(0, 10))
        self.list_frame.grid_remove()
        self.list_frame.columnconfigure(0, weight=1)

        # Scrollable listbox with custom rendering
        self.updates_canvas = tk.Canvas(self.list_frame, bg=CARD_BG, highlightthickness=0, bd=0)
        self.scrollbar = ttk.Scrollbar(self.list_frame, orient="vertical", command=self.updates_canvas.yview)
        self.updates_frame = ttk.Frame(self.updates_canvas, style="Card.TFrame")

        self.updates_frame.bind("<Configure>", lambda e: self.updates_canvas.configure(
            scrollregion=self.updates_canvas.bbox("all")))

        self.updates_canvas.create_window((0, 0), window=self.updates_frame, anchor="nw")
        self.updates_canvas.configure(yscrollcommand=self.scrollbar.set)

        self.updates_canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        # Install button (inside list area)
        self.install_btn = ttk.Button(card, text="Install now", style="Primary.TButton",
                                      command=self.install_updates)
        self.install_btn.grid(row=5, column=0, pady=(10, 15))
        self.install_btn.grid_remove()

        # Separator after card
        ttk.Separator(main, orient="horizontal").pack(fill="x", padx=30, pady=5)

        # More options
        options_frame = ttk.Frame(main, style="Transparent.TFrame")
        options_frame.pack(fill="x", padx=40, pady=(10, 20))

        tk.Label(options_frame, text="More options", font=(FONT_FAMILY, 10, "bold"),
                 bg=BG, fg=TEXT_PRIMARY).pack(anchor="w", pady=(0, 5))

        for text, cmd in [
            ("Pause updates", self.pause_updates),
            ("Update history", self.show_history),
            ("Advanced options", self.open_real_windows_update)
        ]:
            lbl = ttk.Label(options_frame, text=text, style="Link.TLabel", cursor="hand2")
            lbl.pack(anchor="w", pady=2)
            lbl.bind("<Button-1>", lambda e, c=cmd: c())

        # Log area (collapsible, for debugging)
        self.log_toggle = ttk.Label(main, text="Show log ▼", style="Link.TLabel", cursor="hand2")
        self.log_toggle.pack(anchor="e", padx=30, pady=(0, 5))
        self.log_toggle.bind("<Button-1>", lambda e: self.toggle_log())

        self.log_frame = ttk.Frame(main, style="Transparent.TFrame")
        self.log_frame.pack(fill="x", padx=30, pady=(0, 15))
        self.log_box = tk.Text(self.log_frame, height=8, bg="#0c0c0c", fg="#d7d7d7",
                               font=("Consolas", 9), wrap="word", state="disabled")
        self.log_box.pack(fill="x")
        self.log_frame.pack_forget()   # hidden by default

        # Initial state
        self.set_idle_state()

    def toggle_log(self):
        if self.log_frame.winfo_viewable():
            self.log_frame.pack_forget()
            self.log_toggle.config(text="Show log ▼")
        else:
            self.log_frame.pack(fill="x", padx=30, pady=(0, 15))
            self.log_toggle.config(text="Hide log ▲")

    # ---------- UI helpers ----------
    def set_busy_state(self, message, sub_message=""):
        self.busy = True
        self.status_title.config(text=message, foreground=TEXT_PRIMARY)
        self.status_text.config(text=sub_message)
        self.progress.grid()
        self.progress.start(15)
        self.primary_btn.grid_remove()
        self.install_btn.grid_remove()
        self.list_frame.grid_remove()
        self.root.update_idletasks()

    def set_idle_state(self):
        self.busy = False
        self.progress.stop()
        self.progress.grid_remove()
        self.cancel_requested = False

        if self.available_updates:
            count = len(self.available_updates)
            self.status_title.config(text=f"Updates available ({count})", foreground=TEXT_PRIMARY)
            self.status_text.config(text=f"Last checked: {self.last_checked}")
            self.primary_btn.grid_remove()
            self.build_update_list()
            self.list_frame.grid()
            self.install_btn.grid()
            self.list_frame.tkraise()
        else:
            self.status_title.config(text="You're up to date", foreground=GREEN)
            self.status_text.config(text=f"Last checked: {self.last_checked}")
            self.primary_btn.config(text="Check for updates", command=self.scan_updates, state="normal")
            self.primary_btn.grid()
            self.list_frame.grid_remove()
            self.install_btn.grid_remove()

    def set_status_manually(self, title, text, color=TEXT_PRIMARY):
        """Used for non-busy manual messages (e.g., after health check)."""
        self.status_title.config(text=title, foreground=color)
        self.status_text.config(text=text)

    def build_update_list(self):
        # Clear existing widgets in the inner frame
        for widget in self.updates_frame.winfo_children():
            widget.destroy()

        if not self.available_updates:
            ttk.Label(self.updates_frame, text="No updates to show.", style="Muted.TLabel").pack(anchor="w", padx=10, pady=10)
            return

        for idx, upd in enumerate(self.available_updates):
            row_frame = ttk.Frame(self.updates_frame, style="Card.TFrame")
            row_frame.pack(fill="x", padx=10, pady=4)

            name_ver = f"{upd.get('name', 'Unknown')}"
            version = f"Version {upd.get('version', '')} → {upd.get('available', '')}"
            # Show size if available (winget may not give size)
            ttk.Label(row_frame, text=name_ver, style="UpdateName.TLabel", anchor="w").pack(side="left", padx=(0, 10))
            ttk.Label(row_frame, text=version, style="UpdateVersion.TLabel", anchor="e").pack(side="right")

            if idx < len(self.available_updates) - 1:
                ttk.Separator(self.updates_frame, orient="horizontal").pack(fill="x", padx=10)

    # ---------- Background threading ----------
    def run_thread(self, target):
        if self.busy:
            messagebox.showinfo(APP_TITLE, "An operation is already in progress.")
            return
        self.cancel_requested = False
        threading.Thread(target=target, daemon=True).start()

    def run_cmd(self, args):
        self.log(f"> {' '.join(args)}")
        try:
            result = subprocess.run(args, capture_output=True, text=True, timeout=300,
                                    encoding='utf-8', errors='replace')
            if result.stdout:
                for line in result.stdout.splitlines():
                    if line.strip():
                        self.log(line.strip())
            if result.stderr:
                for line in result.stderr.splitlines():
                    if line.strip():
                        self.log(f"ERR: {line.strip()}")
            return result.returncode, result.stdout, result.stderr
        except Exception as e:
            self.log(f"Command failed: {e}")
            return 1, "", str(e)

    # ---------- Logging (thread-safe) ----------
    def log(self, text):
        self.log_queue.put(text)

    def poll_log_queue(self):
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self._write_log(msg)
        except queue.Empty:
            pass
        self.root.after(200, self.poll_log_queue)

    def _write_log(self, text):
        self.log_box.config(state="normal")
        stamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_box.insert("end", f"[{stamp}] {text}\n")
        self.log_box.see("end")
        self.log_box.config(state="disabled")

    # ---------- Core actions ----------
    def scan_updates(self):
        if self.busy:
            return
        self.run_thread(self._scan_updates)

    def _scan_updates(self):
        self.root.after(0, lambda: self.set_busy_state("Checking for updates...", "This may take a moment"))
        self.log("Scanning for updates...")

        if not shutil.which("winget"):
            self.root.after(0, lambda: self.set_status_manually(
                "Winget not found", "Please install App Installer from the Microsoft Store.", RED))
            self.root.after(0, self.set_idle_state)
            return

        # Try JSON output first (winget v1.4+)
        code, stdout, stderr = self.run_cmd(["winget", "upgrade", "--output", "json", "--accept-source-agreements"])
        updates = []
        if code == 0 and stdout.strip():
            try:
                parsed = json.loads(stdout)
                if isinstance(parsed, list):
                    updates = parsed
                elif isinstance(parsed, dict) and "packages" in parsed:
                    updates = parsed["packages"]
            except json.JSONDecodeError:
                self.log("JSON parsing failed, falling back to text parsing.")

        # Fallback: parse text output
        if not updates:
            code2, stdout2, _ = self.run_cmd(["winget", "upgrade", "--accept-source-agreements"])
            if code2 == 0:
                lines = stdout2.splitlines()
                # Simple heuristic: skip header lines and pick long lines with versions
                for line in lines:
                    if len(line.strip()) > 40 and '.' in line and not line.startswith(("Name", "-")):
                        parts = line.split()
                        if len(parts) >= 4:
                            updates.append({
                                "name": ' '.join(parts[:-3]),
                                "id": parts[-3],
                                "version": parts[-2],
                                "available": parts[-1],
                                "source": ""
                            })

        self.last_checked = datetime.datetime.now().strftime("%b %d, %Y at %I:%M %p")
        self.available_updates = updates[:40]  # limit for display

        if updates:
            self.log(f"Found {len(updates)} update(s).")
        else:
            self.log("No updates available.")

        # Notify if plyer available
        if HAS_PLYER and updates:
            try:
                notification.notify(
                    title="Windows 11 AI Updater",
                    message=f"{len(updates)} update(s) found",
                    timeout=5
                )
            except:
                pass

        self.root.after(0, self.set_idle_state)

    def install_updates(self):
        if self.busy:
            return
        confirm = messagebox.askyesno(APP_TITLE,
                                      f"Install {len(self.available_updates)} update(s)?")
        if not confirm:
            return
        self.run_thread(self._install_updates)

    def _install_updates(self):
        self.root.after(0, lambda: self.set_busy_state("Installing updates...", "This may take several minutes"))
        self.log("Starting installation...")

        code, _, _ = self.run_cmd(["winget", "upgrade", "--all", "--accept-package-agreements", "--accept-source-agreements"])

        if code == 0:
            self.log("Installation completed successfully.")
            self.add_to_history("Install", f"All updates installed. Count: {len(self.available_updates)}")
            self.available_updates = []
            self.root.after(0, lambda: self.set_status_manually("You're up to date", f"Last checked: {self.last_checked}", GREEN))
        else:
            self.log(f"Installation finished with exit code {code}.")
            self.add_to_history("Install", f"winget --all completed with code {code}")

        self.root.after(0, self.set_idle_state)

    def run_health_check(self):
        if self.busy:
            messagebox.showinfo(APP_TITLE, "Please wait for the current operation to finish.")
            return
        self.run_thread(self._run_health_check)

    def _run_health_check(self):
        self.root.after(0, lambda: self.set_busy_state("Running system health check...", "sfc /scannow is in progress"))
        self.log("Starting SFC /scannow...")
        code, _, _ = self.run_cmd(["sfc", "/scannow"])
        if code == 0:
            self.log("System File Checker completed successfully.")
            self.root.after(0, lambda: self.set_status_manually("Health check complete", "No integrity violations found.", GREEN))
        else:
            self.log("SFC finished with exit code " + str(code))
            self.root.after(0, lambda: self.set_status_manually("Health check complete", "Some issues may have been found. Check logs.", RED))
        self.root.after(0, self.set_idle_state)

    def open_real_windows_update(self):
        if os.name == "nt":
            try:
                os.startfile("ms-settings:windowsupdate")
                self.log("Opened Settings > Windows Update.")
            except Exception as e:
                self.log(f"Could not open Windows Update: {e}")
                messagebox.showerror("Error", "Unable to open Windows Update settings.")

    def pause_updates(self):
        messagebox.showinfo("Pause updates",
                            "Pausing updates is not yet implemented.\nYou can pause directly in Windows Update settings.")

    def show_history(self):
        history = self.update_history.get("update_history", [])
        if not history:
            messagebox.showinfo("Update History", "No history yet.")
            return
        text = "\n\n".join(
            f"{h['timestamp'][:16]} | {h['action']}\n{h['details']}" for h in history[-15:]
        )
        top = tk.Toplevel(self.root)
        top.title("Update History")
        top.geometry("500x400")
        top.configure(bg=BG)
        tk.Label(top, text="Update History", font=FONT_TITLE, bg=BG, fg=TEXT_PRIMARY).pack(pady=10)
        txt = tk.Text(top, wrap="word", bg="white", font=("Consolas", 10))
        txt.pack(fill="both", expand=True, padx=20, pady=10)
        txt.insert("1.0", text)
        txt.config(state="disabled")

def main():
    root = tk.Tk()
    app = Windows11AIUpdater(root)
    root.mainloop()

if __name__ == "__main__":
    main()