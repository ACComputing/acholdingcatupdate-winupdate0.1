# AC'S WIN UPDATE 1.0
# Windows 7-style updater dashboard for Windows 11.
#
# This does NOT replace Microsoft's protected Windows Update engine.
# It gives you your own update center for:
# - winget app updates
# - Defender signature updates and quick scan
# - SFC and DISM repair tools
# - restore point creation
# - update history log
# - reboot button
#
# Run:
#   python acs_win_update.py

import ctypes
import datetime
import os
import platform
import queue
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox


APP_NAME = "AC'S WIN UPDATE"
APP_VERSION = "1.0"
LOG_FILE = "acs_win_update_history.log"


class ACWinUpdate:
    def __init__(self, root):
        self.root = root
        self.root.title(f"{APP_NAME} {APP_VERSION}")
        self.root.geometry("1080x720")
        self.root.minsize(980, 640)

        self.busy = False
        self.log_queue = queue.Queue()
        self.available_updates = []
        self.is_admin = self.check_admin()

        self.colors = {
            "bg": "#dce9f7",
            "panel": "#f8fbff",
            "card": "#ffffff",
            "border": "#8aa9cc",
            "header": "#1f5f9f",
            "header2": "#2d73b9",
            "green": "#137333",
            "red": "#b00020",
            "yellow": "#fff4ce",
            "text": "#1b1b1b",
            "muted": "#555555",
            "link": "#005a9e",
        }

        self.setup_style()
        self.build_ui()
        self.start_log_pump()
        self.boot_report()

    def check_admin(self):
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False

    def setup_style(self):
        self.root.configure(bg=self.colors["bg"])
        self.style = ttk.Style()

        try:
            self.style.theme_use("clam")
        except Exception:
            pass

        self.style.configure(
            "Blue.Horizontal.TProgressbar",
            troughcolor="#edf4fb",
            bordercolor=self.colors["border"],
            background=self.colors["header2"],
            lightcolor=self.colors["header2"],
            darkcolor=self.colors["header"],
        )

        self.style.configure(
            "Classic.TButton",
            font=("Segoe UI", 10),
            padding=(10, 6),
        )

        self.style.configure(
            "Big.TButton",
            font=("Segoe UI", 11, "bold"),
            padding=(14, 9),
        )

    def build_ui(self):
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(1, weight=1)

        self.build_header()
        self.build_body()
        self.build_status_bar()

    def build_header(self):
        header = tk.Frame(self.root, bg=self.colors["header"], height=88)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        header.grid_columnconfigure(1, weight=1)

        tk.Label(
            header,
            text="↻",
            bg=self.colors["header"],
            fg="white",
            font=("Segoe UI", 42, "bold"),
        ).grid(row=0, column=0, padx=(28, 16), pady=10)

        title_box = tk.Frame(header, bg=self.colors["header"])
        title_box.grid(row=0, column=1, sticky="w")

        tk.Label(
            title_box,
            text=APP_NAME,
            bg=self.colors["header"],
            fg="white",
            font=("Segoe UI", 25, "bold"),
        ).pack(anchor="w")

        tk.Label(
            title_box,
            text="Windows 7-style update center for Windows 11",
            bg=self.colors["header"],
            fg="#dcecff",
            font=("Segoe UI", 10),
        ).pack(anchor="w")

        admin_text = "Administrator mode" if self.is_admin else "Standard mode"
        admin_color = "#d8ffd8" if self.is_admin else "#fff0b3"

        tk.Label(
            header,
            text=admin_text,
            bg=self.colors["header"],
            fg=admin_color,
            font=("Segoe UI", 10, "bold"),
        ).grid(row=0, column=2, padx=28)

    def build_body(self):
        body = tk.Frame(self.root, bg=self.colors["bg"])
        body.grid(row=1, column=0, sticky="nsew", padx=18, pady=18)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        self.sidebar = tk.Frame(
            body,
            bg=self.colors["panel"],
            width=250,
            highlightbackground=self.colors["border"],
            highlightthickness=1,
        )
        self.sidebar.grid(row=0, column=0, sticky="ns", padx=(0, 16))
        self.sidebar.grid_propagate(False)

        self.main = tk.Frame(
            body,
            bg=self.colors["panel"],
            highlightbackground=self.colors["border"],
            highlightthickness=1,
        )
        self.main.grid(row=0, column=1, sticky="nsew")
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(4, weight=1)

        self.build_sidebar()
        self.build_main_panel()

    def build_sidebar(self):
        tk.Label(
            self.sidebar,
            text="Control Panel Home",
            bg=self.colors["panel"],
            fg=self.colors["link"],
            font=("Segoe UI", 10, "bold"),
            anchor="w",
        ).pack(fill="x", padx=18, pady=(18, 8))

        self.side_button("Check for updates", self.scan_updates)
        self.side_button("Install updates", self.install_updates)
        self.side_button("View update history", self.show_history)
        self.side_button("Change settings", self.show_settings)
        self.side_button("System health tools", self.show_health_tools)
        self.side_button("Create restore point", self.create_restore_point)
        self.side_button("Restart computer", self.restart_prompt)

        sep = tk.Frame(self.sidebar, bg="#c7d8eb", height=1)
        sep.pack(fill="x", padx=18, pady=18)

        tk.Label(
            self.sidebar,
            text="See also",
            bg=self.colors["panel"],
            fg=self.colors["muted"],
            font=("Segoe UI", 9, "bold"),
            anchor="w",
        ).pack(fill="x", padx=18)

        self.side_button("About AC'S WIN UPDATE", self.show_about)
        self.side_button("Open logs folder", self.open_logs_folder)

        tk.Label(
            self.sidebar,
            text="Note: This app does not control\nMicrosoft Windows Update.",
            bg=self.colors["panel"],
            fg=self.colors["muted"],
            font=("Segoe UI", 9),
            justify="left",
        ).pack(side="bottom", anchor="w", padx=18, pady=18)

    def side_button(self, text, command):
        btn = tk.Button(
            self.sidebar,
            text=text,
            command=command,
            bg=self.colors["panel"],
            fg=self.colors["link"],
            activebackground="#e6f0fa",
            activeforeground=self.colors["link"],
            relief="flat",
            anchor="w",
            font=("Segoe UI", 10),
            padx=18,
            pady=7,
            cursor="hand2",
        )
        btn.pack(fill="x")

    def build_main_panel(self):
        top_card = tk.Frame(
            self.main,
            bg=self.colors["card"],
            highlightbackground="#c8d6e5",
            highlightthickness=1,
        )
        top_card.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 14))
        top_card.grid_columnconfigure(1, weight=1)

        self.big_icon = tk.Label(
            top_card,
            text="✓",
            bg=self.colors["card"],
            fg=self.colors["green"],
            font=("Segoe UI", 44, "bold"),
        )
        self.big_icon.grid(row=0, column=0, rowspan=3, padx=24, pady=24)

        self.main_title = tk.Label(
            top_card,
            text="Your computer is ready to check for updates",
            bg=self.colors["card"],
            fg=self.colors["text"],
            font=("Segoe UI", 18, "bold"),
            anchor="w",
        )
        self.main_title.grid(row=0, column=1, sticky="ew", pady=(24, 2))

        self.main_text = tk.Label(
            top_card,
            text="Check for app updates, Defender updates, and run safe repair tools.",
            bg=self.colors["card"],
            fg=self.colors["muted"],
            font=("Segoe UI", 10),
            anchor="w",
        )
        self.main_text.grid(row=1, column=1, sticky="ew")

        self.last_checked = tk.Label(
            top_card,
            text="Most recent check: Never",
            bg=self.colors["card"],
            fg=self.colors["muted"],
            font=("Segoe UI", 9),
            anchor="w",
        )
        self.last_checked.grid(row=2, column=1, sticky="ew", pady=(8, 24))

        self.progress = ttk.Progressbar(
            self.main,
            style="Blue.Horizontal.TProgressbar",
            mode="determinate",
            maximum=100,
        )
        self.progress.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 14))

        action_row = tk.Frame(self.main, bg=self.colors["panel"])
        action_row.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 16))

        self.check_btn = ttk.Button(
            action_row,
            text="Check for updates",
            style="Big.TButton",
            command=self.scan_updates,
        )
        self.check_btn.pack(side="left", padx=(0, 10))

        self.install_btn = ttk.Button(
            action_row,
            text="Install updates",
            style="Classic.TButton",
            command=self.install_updates,
        )
        self.install_btn.pack(side="left", padx=(0, 10))

        self.defender_btn = ttk.Button(
            action_row,
            text="Update Defender",
            style="Classic.TButton",
            command=self.update_defender,
        )
        self.defender_btn.pack(side="left", padx=(0, 10))

        self.health_btn = ttk.Button(
            action_row,
            text="Repair tools",
            style="Classic.TButton",
            command=self.show_health_tools,
        )
        self.health_btn.pack(side="left")

        details = tk.Frame(self.main, bg=self.colors["panel"])
        details.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 14))
        details.grid_columnconfigure(0, weight=1)
        details.grid_columnconfigure(1, weight=1)
        details.grid_columnconfigure(2, weight=1)

        self.card_backend = self.info_card(details, "Update backend", "winget + Defender + repair tools")
        self.card_backend.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        self.card_os = self.info_card(details, "Detected Windows", self.get_windows_name())
        self.card_os.grid(row=0, column=1, sticky="ew", padx=8)

        self.card_updates = self.info_card(details, "Available app updates", "Unknown")
        self.card_updates.grid(row=0, column=2, sticky="ew", padx=(8, 0))

        log_frame = tk.Frame(
            self.main,
            bg="#0c0c0c",
            highlightbackground="#555555",
            highlightthickness=1,
        )
        log_frame.grid(row=4, column=0, sticky="nsew", padx=20, pady=(0, 20))
        log_frame.grid_columnconfigure(0, weight=1)
        log_frame.grid_rowconfigure(0, weight=1)

        self.log_box = tk.Text(
            log_frame,
            bg="#0c0c0c",
            fg="#e8e8e8",
            insertbackground="white",
            relief="flat",
            font=("Consolas", 10),
            wrap="word",
        )
        self.log_box.grid(row=0, column=0, sticky="nsew")

        scroll = ttk.Scrollbar(log_frame, command=self.log_box.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.log_box.config(yscrollcommand=scroll.set)

    def info_card(self, parent, title, value):
        frame = tk.Frame(
            parent,
            bg=self.colors["card"],
            highlightbackground="#c8d6e5",
            highlightthickness=1,
        )

        tk.Label(
            frame,
            text=title,
            bg=self.colors["card"],
            fg=self.colors["muted"],
            font=("Segoe UI", 9),
            anchor="w",
        ).pack(fill="x", padx=14, pady=(12, 2))

        label = tk.Label(
            frame,
            text=value,
            bg=self.colors["card"],
            fg=self.colors["text"],
            font=("Segoe UI", 10, "bold"),
            anchor="w",
            wraplength=230,
            justify="left",
        )
        label.pack(fill="x", padx=14, pady=(0, 12))

        frame.value_label = label
        return frame

    def build_status_bar(self):
        self.status = tk.Label(
            self.root,
            text="Ready",
            bg="#c8dcf0",
            fg=self.colors["text"],
            anchor="w",
            font=("Segoe UI", 9),
            padx=12,
        )
        self.status.grid(row=2, column=0, sticky="ew")

    def get_windows_name(self):
        try:
            return f"{platform.system()} {platform.release()} {platform.version()}"
        except Exception:
            return "Windows 11"

    def boot_report(self):
        self.log(f"{APP_NAME} {APP_VERSION} started.")
        self.log(f"Admin mode: {self.is_admin}")
        self.log(f"OS: {self.get_windows_name()}")
        self.log("This app does not modify Windows Update policies.")

        if shutil.which("winget"):
            self.log("winget detected.")
        else:
            self.log("WARNING: winget not detected. App update scan will not work.")

        if self.find_mpcmdrun():
            self.log("Microsoft Defender command tool detected.")
        else:
            self.log("WARNING: Defender command tool not found.")

        if not self.is_admin:
            self.log("Tip: Run as Administrator for restore point, SFC, and DISM features.")

    def start_log_pump(self):
        self.root.after(100, self.pump_logs)

    def pump_logs(self):
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self.write_log(msg)
        except queue.Empty:
            pass

        self.root.after(100, self.pump_logs)

    def log(self, msg):
        self.log_queue.put(msg)

    def write_log(self, msg):
        stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{stamp}] {msg}"

        self.log_box.insert("end", line + "\n")
        self.log_box.see("end")

        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass

    def set_busy(self, busy):
        self.busy = busy
        state = "disabled" if busy else "normal"

        for btn in [
            self.check_btn,
            self.install_btn,
            self.defender_btn,
            self.health_btn,
        ]:
            btn.config(state=state)

    def set_status(self, text):
        self.status.config(text=text)

    def set_progress(self, value):
        self.progress.config(value=value)

    def set_main(self, title=None, text=None, icon=None, icon_color=None):
        if title is not None:
            self.main_title.config(text=title)
        if text is not None:
            self.main_text.config(text=text)
        if icon is not None:
            self.big_icon.config(text=icon)
        if icon_color is not None:
            self.big_icon.config(fg=icon_color)

    def run_thread(self, func):
        if self.busy:
            messagebox.showinfo(APP_NAME, "A task is already running.")
            return

        self.set_busy(True)
        thread = threading.Thread(target=func, daemon=True)
        thread.start()

    def finish_task(self):
        self.root.after(0, lambda: self.set_busy(False))
        self.root.after(0, lambda: self.set_status("Ready"))

    def run_cmd(self, args):
        self.log("> " + " ".join(args))

        try:
            proc = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                shell=False,
            )

            lines = []
            for line in proc.stdout:
                line = line.rstrip()
                lines.append(line)
                self.log(line)

            proc.wait()
            self.log(f"Exit code: {proc.returncode}")
            return proc.returncode, "\n".join(lines)

        except FileNotFoundError:
            self.log(f"ERROR: command not found: {args[0]}")
            return 127, ""
        except Exception as e:
            self.log(f"ERROR: {e}")
            return 1, str(e)

    def scan_updates(self):
        self.run_thread(self._scan_updates)

    def _scan_updates(self):
        self.root.after(0, lambda: self.set_status("Checking for updates..."))
        self.root.after(0, lambda: self.set_progress(5))
        self.root.after(0, lambda: self.set_main(
            "Checking for updates...",
            "Searching for app updates with winget.",
            "⟳",
            self.colors["header2"],
        ))

        if not shutil.which("winget"):
            self.log("winget is missing. Install App Installer from Microsoft Store.")
            self.root.after(0, lambda: self.set_main(
                "Could not check for updates",
                "winget was not found on this computer.",
                "!",
                self.colors["red"],
            ))
            self.finish_task()
            return

        self.root.after(0, lambda: self.set_progress(20))

        code, output = self.run_cmd(["winget", "upgrade", "--accept-source-agreements"])

        self.root.after(0, lambda: self.set_progress(80))

        updates = self.parse_winget(output)
        self.available_updates = updates

        now = datetime.datetime.now().strftime("%B %d, %Y %I:%M %p")
        self.root.after(0, lambda: self.last_checked.config(text=f"Most recent check: {now}"))

        if updates:
            self.root.after(0, lambda: self.card_updates.value_label.config(text=str(len(updates))))
            self.root.after(0, lambda: self.set_main(
                f"{len(updates)} app update(s) are available",
                "Click Install updates to update supported apps through winget.",
                "!",
                "#b77900",
            ))

            for item in updates:
                self.log(f"AVAILABLE: {item}")
        else:
            self.root.after(0, lambda: self.card_updates.value_label.config(text="0"))
            self.root.after(0, lambda: self.set_main(
                "No app updates were found",
                "Everything winget can see appears up to date.",
                "✓",
                self.colors["green"],
            ))

        if code != 0:
            self.log("Scan ended with warnings. Check the log output above.")

        self.root.after(0, lambda: self.set_progress(100))
        self.finish_task()

    def parse_winget(self, output):
        updates = []
        lines = output.splitlines()

        for line in lines:
            clean = line.strip()

            if not clean:
                continue

            lower = clean.lower()

            skip = [
                "name",
                "----",
                "the following",
                "no installed package",
                "source requires",
                "terms of transaction",
                "msstore",
                "winget",
                "upgrades available",
            ]

            if any(lower.startswith(s) for s in skip):
                continue

            if "  " in clean and not clean.startswith("-"):
                updates.append(clean)

        return updates[:100]

    def install_updates(self):
        if not shutil.which("winget"):
            messagebox.showerror(APP_NAME, "winget was not found.")
            return

        confirm = messagebox.askyesno(
            APP_NAME,
            "Install all available app updates using winget?\n\n"
            "This does not use Microsoft Windows Update."
        )

        if not confirm:
            return

        self.run_thread(self._install_updates)

    def _install_updates(self):
        self.root.after(0, lambda: self.set_status("Installing updates..."))
        self.root.after(0, lambda: self.set_progress(10))
        self.root.after(0, lambda: self.set_main(
            "Installing updates...",
            "Installing supported app updates through winget.",
            "⟳",
            self.colors["header2"],
        ))

        code, output = self.run_cmd([
            "winget",
            "upgrade",
            "--all",
            "--accept-package-agreements",
            "--accept-source-agreements",
        ])

        self.root.after(0, lambda: self.set_progress(90))

        if code == 0:
            self.root.after(0, lambda: self.set_main(
                "Updates were installed",
                "Restart apps or reboot if any installer requested it.",
                "✓",
                self.colors["green"],
            ))
        else:
            self.root.after(0, lambda: self.set_main(
                "Some updates need attention",
                "Check the log. Some apps may need admin rights or manual installers.",
                "!",
                "#b77900",
            ))

        self.root.after(0, lambda: self.set_progress(100))
        self.finish_task()

    def update_defender(self):
        self.run_thread(self._update_defender)

    def _update_defender(self):
        mpcmd = self.find_mpcmdrun()

        self.root.after(0, lambda: self.set_status("Updating Microsoft Defender..."))
        self.root.after(0, lambda: self.set_progress(10))
        self.root.after(0, lambda: self.set_main(
            "Updating Defender protection...",
            "Checking Microsoft Defender signatures.",
            "🛡",
            self.colors["header2"],
        ))

        if not mpcmd:
            self.log("MpCmdRun.exe not found.")
            self.root.after(0, lambda: self.set_main(
                "Defender tool not found",
                "Microsoft Defender command-line tool could not be located.",
                "!",
                self.colors["red"],
            ))
            self.finish_task()
            return

        self.root.after(0, lambda: self.set_progress(35))

        code, output = self.run_cmd([mpcmd, "-SignatureUpdate"])

        self.root.after(0, lambda: self.set_progress(100))

        if code == 0:
            self.root.after(0, lambda: self.set_main(
                "Defender was updated",
                "Protection signatures were updated or already current.",
                "✓",
                self.colors["green"],
            ))
        else:
            self.root.after(0, lambda: self.set_main(
                "Defender update returned warnings",
                "Check the log for Defender output.",
                "!",
                "#b77900",
            ))

        self.finish_task()

    def defender_quick_scan(self):
        self.run_thread(self._defender_quick_scan)

    def _defender_quick_scan(self):
        mpcmd = self.find_mpcmdrun()

        self.root.after(0, lambda: self.set_status("Running Defender quick scan..."))
        self.root.after(0, lambda: self.set_progress(10))
        self.root.after(0, lambda: self.set_main(
            "Running quick scan...",
            "Microsoft Defender is scanning common malware locations.",
            "🛡",
            self.colors["header2"],
        ))

        if not mpcmd:
            self.log("MpCmdRun.exe not found.")
            self.finish_task()
            return

        code, output = self.run_cmd([mpcmd, "-Scan", "-ScanType", "1"])

        self.root.after(0, lambda: self.set_progress(100))

        if code == 0:
            self.root.after(0, lambda: self.set_main(
                "Quick scan complete",
                "Defender finished scanning.",
                "✓",
                self.colors["green"],
            ))
        else:
            self.root.after(0, lambda: self.set_main(
                "Quick scan returned warnings",
                "Check the log for Defender output.",
                "!",
                "#b77900",
            ))

        self.finish_task()

    def find_mpcmdrun(self):
        candidates = [
            r"C:\ProgramData\Microsoft\Windows Defender\Platform",
            r"C:\Program Files\Windows Defender",
        ]

        for base in candidates:
            if os.path.isdir(base):
                for root, dirs, files in os.walk(base):
                    if "MpCmdRun.exe" in files:
                        return os.path.join(root, "MpCmdRun.exe")

        return shutil.which("MpCmdRun.exe")

    def show_health_tools(self):
        win = tk.Toplevel(self.root)
        win.title("System Health Tools")
        win.geometry("520x420")
        win.configure(bg=self.colors["bg"])
        win.resizable(False, False)

        tk.Label(
            win,
            text="System Health Tools",
            bg=self.colors["bg"],
            fg=self.colors["text"],
            font=("Segoe UI", 18, "bold"),
        ).pack(anchor="w", padx=24, pady=(22, 8))

        tk.Label(
            win,
            text="These tools do not use Windows Update. Administrator mode is recommended.",
            bg=self.colors["bg"],
            fg=self.colors["muted"],
            font=("Segoe UI", 10),
            wraplength=460,
            justify="left",
        ).pack(anchor="w", padx=24, pady=(0, 18))

        self.health_button(win, "Run SFC /scannow", self.run_sfc)
        self.health_button(win, "Run DISM RestoreHealth", self.run_dism)
        self.health_button(win, "Update Microsoft Defender", self.update_defender)
        self.health_button(win, "Run Defender Quick Scan", self.defender_quick_scan)
        self.health_button(win, "Create Restore Point", self.create_restore_point)

        tk.Button(
            win,
            text="Close",
            command=win.destroy,
            font=("Segoe UI", 10),
            padx=14,
            pady=6,
        ).pack(anchor="e", padx=24, pady=18)

    def health_button(self, parent, text, command):
        tk.Button(
            parent,
            text=text,
            command=command,
            bg="#ffffff",
            fg=self.colors["link"],
            activebackground="#e6f0fa",
            relief="solid",
            bd=1,
            font=("Segoe UI", 10),
            anchor="w",
            padx=14,
            pady=8,
        ).pack(fill="x", padx=24, pady=5)

    def run_sfc(self):
        confirm = messagebox.askyesno(
            APP_NAME,
            "Run SFC /scannow?\n\nThis may take several minutes."
        )
        if confirm:
            self.run_thread(self._run_sfc)

    def _run_sfc(self):
        self.root.after(0, lambda: self.set_status("Running SFC..."))
        self.root.after(0, lambda: self.set_progress(10))
        self.root.after(0, lambda: self.set_main(
            "Scanning system files...",
            "Running sfc /scannow.",
            "⟳",
            self.colors["header2"],
        ))

        code, output = self.run_cmd(["sfc", "/scannow"])

        self.root.after(0, lambda: self.set_progress(100))

        if code == 0:
            self.root.after(0, lambda: self.set_main(
                "SFC finished",
                "System File Checker completed. Check the log for details.",
                "✓",
                self.colors["green"],
            ))
        else:
            self.root.after(0, lambda: self.set_main(
                "SFC returned warnings",
                "Run as Administrator if this failed.",
                "!",
                "#b77900",
            ))

        self.finish_task()

    def run_dism(self):
        confirm = messagebox.askyesno(
            APP_NAME,
            "Run DISM RestoreHealth?\n\nThis repairs the Windows component store."
        )
        if confirm:
            self.run_thread(self._run_dism)

    def _run_dism(self):
        self.root.after(0, lambda: self.set_status("Running DISM..."))
        self.root.after(0, lambda: self.set_progress(10))
        self.root.after(0, lambda: self.set_main(
            "Repairing Windows image...",
            "Running DISM /Online /Cleanup-Image /RestoreHealth.",
            "⟳",
            self.colors["header2"],
        ))

        code, output = self.run_cmd([
            "DISM",
            "/Online",
            "/Cleanup-Image",
            "/RestoreHealth",
        ])

        self.root.after(0, lambda: self.set_progress(100))

        if code == 0:
            self.root.after(0, lambda: self.set_main(
                "DISM finished",
                "Windows image repair completed. Check the log for details.",
                "✓",
                self.colors["green"],
            ))
        else:
            self.root.after(0, lambda: self.set_main(
                "DISM returned warnings",
                "Check the log. DISM may need admin rights or source files.",
                "!",
                "#b77900",
            ))

        self.finish_task()

    def create_restore_point(self):
        confirm = messagebox.askyesno(
            APP_NAME,
            "Create a restore point named AC_WIN_UPDATE_RESTORE?\n\n"
            "This requires System Protection to be enabled."
        )

        if not confirm:
            return

        self.run_thread(self._create_restore_point)

    def _create_restore_point(self):
        self.root.after(0, lambda: self.set_status("Creating restore point..."))
        self.root.after(0, lambda: self.set_progress(15))
        self.root.after(0, lambda: self.set_main(
            "Creating restore point...",
            "Using PowerShell Checkpoint-Computer.",
            "⟳",
            self.colors["header2"],
        ))

        code, output = self.run_cmd([
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            "Checkpoint-Computer -Description 'AC_WIN_UPDATE_RESTORE' -RestorePointType 'MODIFY_SETTINGS'"
        ])

        self.root.after(0, lambda: self.set_progress(100))

        if code == 0:
            self.root.after(0, lambda: self.set_main(
                "Restore point created",
                "AC_WIN_UPDATE_RESTORE was requested successfully.",
                "✓",
                self.colors["green"],
            ))
        else:
            self.root.after(0, lambda: self.set_main(
                "Restore point failed",
                "Run as Administrator and make sure System Protection is enabled.",
                "!",
                "#b77900",
            ))

        self.finish_task()

    def show_history(self):
        win = tk.Toplevel(self.root)
        win.title("Update History")
        win.geometry("820x520")
        win.configure(bg=self.colors["bg"])
        win.grid_columnconfigure(0, weight=1)
        win.grid_rowconfigure(1, weight=1)

        tk.Label(
            win,
            text="Update History",
            bg=self.colors["bg"],
            fg=self.colors["text"],
            font=("Segoe UI", 18, "bold"),
        ).grid(row=0, column=0, sticky="w", padx=18, pady=(16, 8))

        text = tk.Text(
            win,
            bg="#ffffff",
            fg="#1f1f1f",
            font=("Consolas", 10),
            wrap="word",
        )
        text.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 18))

        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                text.insert("end", f.read())
        except FileNotFoundError:
            text.insert("end", "No history yet.")
        except Exception as e:
            text.insert("end", f"Could not read history: {e}")

    def show_settings(self):
        win = tk.Toplevel(self.root)
        win.title("Change Settings")
        win.geometry("560x390")
        win.configure(bg=self.colors["bg"])
        win.resizable(False, False)

        tk.Label(
            win,
            text="Change Settings",
            bg=self.colors["bg"],
            fg=self.colors["text"],
            font=("Segoe UI", 18, "bold"),
        ).pack(anchor="w", padx=24, pady=(22, 8))

        tk.Label(
            win,
            text=(
                "AC'S WIN UPDATE uses safe local tools and does not change Microsoft "
                "Windows Update policies. These settings are app-only."
            ),
            bg=self.colors["bg"],
            fg=self.colors["muted"],
            font=("Segoe UI", 10),
            wraplength=500,
            justify="left",
        ).pack(anchor="w", padx=24, pady=(0, 18))

        auto_scan_var = tk.BooleanVar(value=False)
        defender_var = tk.BooleanVar(value=True)
        repair_var = tk.BooleanVar(value=False)

        tk.Checkbutton(
            win,
            text="Check winget apps when app opens",
            variable=auto_scan_var,
            bg=self.colors["bg"],
            fg=self.colors["text"],
            font=("Segoe UI", 10),
        ).pack(anchor="w", padx=24, pady=5)

        tk.Checkbutton(
            win,
            text="Show Defender tools",
            variable=defender_var,
            bg=self.colors["bg"],
            fg=self.colors["text"],
            font=("Segoe UI", 10),
        ).pack(anchor="w", padx=24, pady=5)

        tk.Checkbutton(
            win,
            text="Warn before repair commands",
            variable=repair_var,
            bg=self.colors["bg"],
            fg=self.colors["text"],
            font=("Segoe UI", 10),
        ).pack(anchor="w", padx=24, pady=5)

        tk.Label(
            win,
            text="Settings are visual placeholders in this build.",
            bg=self.colors["bg"],
            fg=self.colors["muted"],
            font=("Segoe UI", 9),
        ).pack(anchor="w", padx=24, pady=(18, 0))

        tk.Button(
            win,
            text="OK",
            command=win.destroy,
            font=("Segoe UI", 10),
            padx=18,
            pady=6,
        ).pack(anchor="e", padx=24, pady=22)

    def show_about(self):
        messagebox.showinfo(
            APP_NAME,
            f"{APP_NAME} {APP_VERSION}\n\n"
            "A Windows 7-style update center for Windows 11.\n\n"
            "Features:\n"
            "- winget app updates\n"
            "- Defender signature update\n"
            "- Defender quick scan\n"
            "- SFC system scan\n"
            "- DISM image repair\n"
            "- Restore point creation\n"
            "- Update history log\n\n"
            "This does not replace or control Microsoft Windows Update."
        )

    def open_logs_folder(self):
        folder = os.getcwd()
        try:
            os.startfile(folder)
        except Exception as e:
            messagebox.showerror(APP_NAME, f"Could not open folder:\n{e}")

    def restart_prompt(self):
        confirm = messagebox.askyesno(
            APP_NAME,
            "Restart the computer now?"
        )

        if confirm:
            self.log("Restart requested by user.")
            try:
                subprocess.Popen(["shutdown", "/r", "/t", "5"])
            except Exception as e:
                messagebox.showerror(APP_NAME, f"Could not restart:\n{e}")


def main():
    if os.name != "nt":
        print("AC'S WIN UPDATE is designed for Windows.")
        sys.exit(1)

    root = tk.Tk()
    app = ACWinUpdate(root)
    root.mainloop()


if __name__ == "__main__":
    main()