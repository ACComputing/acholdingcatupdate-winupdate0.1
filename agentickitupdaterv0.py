# Agentic Update 0.2
# A Windows Update-style updater that does NOT use Windows Update.
# It uses winget to scan/update apps and includes safe system health tools.
#
# Requirements:
# - Windows 10/11
# - Python 3
# - winget installed
#
# Run:
#   python agentic_update.py

import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import threading
import datetime
import shutil
import os
import sys


APP_NAME = "Agentic Update"
APP_VERSION = "0.2"


class AgenticUpdate:
    def __init__(self, root):
        self.root = root
        self.root.title(f"{APP_NAME} {APP_VERSION}")
        self.root.geometry("1050x680")
        self.root.minsize(950, 600)
        self.root.configure(bg="#f3f3f3")

        self.busy = False
        self.last_scan = "Never"
        self.available_updates = []

        self.setup_style()
        self.build_ui()
        self.boot_check()

    def setup_style(self):
        self.style = ttk.Style()
        try:
            self.style.theme_use("vista")
        except Exception:
            pass

        self.style.configure("TFrame", background="#f3f3f3")
        self.style.configure("Card.TFrame", background="#ffffff")
        self.style.configure("Title.TLabel", font=("Segoe UI", 24, "bold"), background="#f3f3f3", foreground="#1f1f1f")
        self.style.configure("Subtitle.TLabel", font=("Segoe UI", 11), background="#f3f3f3", foreground="#5c5c5c")
        self.style.configure("CardTitle.TLabel", font=("Segoe UI", 14, "bold"), background="#ffffff", foreground="#1f1f1f")
        self.style.configure("CardText.TLabel", font=("Segoe UI", 10), background="#ffffff", foreground="#555555")
        self.style.configure("Blue.TButton", font=("Segoe UI", 10, "bold"))
        self.style.configure("Side.TButton", font=("Segoe UI", 10), padding=8)

    def build_ui(self):
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        self.sidebar = tk.Frame(self.root, bg="#eeeeee", width=230)
        self.sidebar.grid(row=0, column=0, sticky="ns")
        self.sidebar.grid_propagate(False)

        self.main = ttk.Frame(self.root, style="TFrame")
        self.main.grid(row=0, column=1, sticky="nsew", padx=28, pady=24)
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(4, weight=1)

        tk.Label(
            self.sidebar,
            text="Agentic\nUpdate",
            font=("Segoe UI", 22, "bold"),
            bg="#eeeeee",
            fg="#1f1f1f",
            justify="left"
        ).pack(anchor="w", padx=22, pady=(28, 24))

        self.nav_status = tk.Label(
            self.sidebar,
            text="● Ready",
            bg="#eeeeee",
            fg="#107c10",
            font=("Segoe UI", 10, "bold")
        )
        self.nav_status.pack(anchor="w", padx=24, pady=(0, 18))

        self.make_sidebar_button("Home", self.show_home)
        self.make_sidebar_button("Scan apps", self.scan_updates)
        self.make_sidebar_button("Install updates", self.install_updates)
        self.make_sidebar_button("Health tools", self.show_health)
        self.make_sidebar_button("About", self.show_about)

        tk.Label(
            self.sidebar,
            text="Does not control\nWindows Update.",
            bg="#eeeeee",
            fg="#777777",
            font=("Segoe UI", 9),
            justify="left"
        ).pack(side="bottom", anchor="w", padx=24, pady=24)

        self.header = ttk.Label(self.main, text="Agentic Update", style="Title.TLabel")
        self.header.grid(row=0, column=0, sticky="w")

        self.subheader = ttk.Label(
            self.main,
            text="Your own updater for apps, tools, and safe maintenance.",
            style="Subtitle.TLabel"
        )
        self.subheader.grid(row=1, column=0, sticky="w", pady=(4, 20))

        self.status_card = tk.Frame(self.main, bg="#ffffff", highlightbackground="#dddddd", highlightthickness=1)
        self.status_card.grid(row=2, column=0, sticky="ew", pady=(0, 18))
        self.status_card.grid_columnconfigure(0, weight=1)

        self.status_title = tk.Label(
            self.status_card,
            text="You're up to date-ish",
            bg="#ffffff",
            fg="#1f1f1f",
            font=("Segoe UI", 18, "bold")
        )
        self.status_title.grid(row=0, column=0, sticky="w", padx=24, pady=(22, 4))

        self.status_text = tk.Label(
            self.status_card,
            text="Run a scan to check app updates through winget.",
            bg="#ffffff",
            fg="#555555",
            font=("Segoe UI", 10)
        )
        self.status_text.grid(row=1, column=0, sticky="w", padx=24)

        self.progress = ttk.Progressbar(self.status_card, mode="determinate", maximum=100)
        self.progress.grid(row=2, column=0, sticky="ew", padx=24, pady=(18, 8))

        self.button_row = tk.Frame(self.status_card, bg="#ffffff")
        self.button_row.grid(row=3, column=0, sticky="w", padx=24, pady=(10, 22))

        self.scan_btn = ttk.Button(self.button_row, text="Check for updates", command=self.scan_updates)
        self.scan_btn.pack(side="left", padx=(0, 10))

        self.install_btn = ttk.Button(self.button_row, text="Install app updates", command=self.install_updates)
        self.install_btn.pack(side="left", padx=(0, 10))

        self.health_btn = ttk.Button(self.button_row, text="Run health check", command=self.run_health_check)
        self.health_btn.pack(side="left")

        self.info_row = tk.Frame(self.main, bg="#f3f3f3")
        self.info_row.grid(row=3, column=0, sticky="ew", pady=(0, 18))
        self.info_row.grid_columnconfigure(0, weight=1)
        self.info_row.grid_columnconfigure(1, weight=1)

        self.left_info = self.small_card(self.info_row, "Last checked", self.last_scan)
        self.left_info.grid(row=0, column=0, sticky="ew", padx=(0, 9))

        self.right_info = self.small_card(self.info_row, "Backend", "winget")
        self.right_info.grid(row=0, column=1, sticky="ew", padx=(9, 0))

        self.log_box = tk.Text(
            self.main,
            bg="#0c0c0c",
            fg="#d7d7d7",
            insertbackground="#ffffff",
            font=("Consolas", 10),
            wrap="word",
            relief="flat"
        )
        self.log_box.grid(row=4, column=0, sticky="nsew")
        self.log("Agentic Update started.")
        self.log("This app uses winget. It does not modify Windows Update policies.")

    def make_sidebar_button(self, text, command):
        btn = tk.Button(
            self.sidebar,
            text=text,
            command=command,
            bg="#eeeeee",
            fg="#222222",
            activebackground="#dddddd",
            activeforeground="#000000",
            relief="flat",
            anchor="w",
            padx=24,
            pady=10,
            font=("Segoe UI", 10)
        )
        btn.pack(fill="x")

    def small_card(self, parent, title, value):
        frame = tk.Frame(parent, bg="#ffffff", highlightbackground="#dddddd", highlightthickness=1)
        tk.Label(frame, text=title, bg="#ffffff", fg="#666666", font=("Segoe UI", 9)).pack(anchor="w", padx=18, pady=(14, 2))
        label = tk.Label(frame, text=value, bg="#ffffff", fg="#1f1f1f", font=("Segoe UI", 12, "bold"))
        label.pack(anchor="w", padx=18, pady=(0, 14))
        frame.value_label = label
        return frame

    def boot_check(self):
        if not shutil.which("winget"):
            self.status_title.config(text="winget not found")
            self.status_text.config(text="Install App Installer from Microsoft Store or use a newer Windows build.")
            self.nav_status.config(text="● Backend missing", fg="#c42b1c")
            self.log("ERROR: winget was not found on this system.")
        else:
            self.log("winget found.")

    def set_busy(self, value):
        self.busy = value
        state = "disabled" if value else "normal"
        self.scan_btn.config(state=state)
        self.install_btn.config(state=state)
        self.health_btn.config(state=state)

    def log(self, text):
        stamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_box.insert("end", f"[{stamp}] {text}\n")
        self.log_box.see("end")

    def run_thread(self, target):
        if self.busy:
            messagebox.showinfo(APP_NAME, "Already working. Let the current task finish.")
            return
        t = threading.Thread(target=target, daemon=True)
        t.start()

    def run_cmd(self, args):
        self.log(f"> {' '.join(args)}")
        try:
            proc = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                shell=False
            )

            output_lines = []
            for line in proc.stdout:
                line = line.rstrip()
                output_lines.append(line)
                self.root.after(0, lambda l=line: self.log(l))

            proc.wait()
            return proc.returncode, "\n".join(output_lines)

        except Exception as e:
            self.root.after(0, lambda: self.log(f"ERROR: {e}"))
            return 1, str(e)

    def show_home(self):
        self.status_title.config(text="Agentic Update ready")
        self.status_text.config(text="Scan apps, install package updates, or run safe health checks.")
        self.log("Home opened.")

    def show_health(self):
        self.status_title.config(text="Health tools")
        self.status_text.config(text="Use SFC/DISM checks from inside the app. Some checks may need Administrator.")
        self.log("Health tools opened.")

    def show_about(self):
        messagebox.showinfo(
            APP_NAME,
            f"{APP_NAME} {APP_VERSION}\n\n"
            "A custom updater dashboard.\n\n"
            "Uses:\n"
            "- winget upgrade\n"
            "- optional SFC/DISM health tools\n\n"
            "Does not use Windows Update."
        )

    def scan_updates(self):
        self.run_thread(self._scan_updates)

    def _scan_updates(self):
        self.set_busy_safe(True)
        self.progress_safe(0)
        self.nav_safe("● Scanning", "#0067c0")
        self.title_safe("Checking for app updates...")
        self.text_safe("Scanning installed apps through winget.")
        self.log_safe("Starting app update scan.")

        if not shutil.which("winget"):
            self.log_safe("Cannot scan: winget missing.")
            self.title_safe("winget not found")
            self.text_safe("Install winget/App Installer first.")
            self.done()
            return

        self.progress_safe(20)

        code, out = self.run_cmd(["winget", "upgrade", "--accept-source-agreements"])

        self.progress_safe(80)

        updates = self.parse_winget_upgrade(out)
        self.available_updates = updates

        now = datetime.datetime.now().strftime("%b %d, %Y %I:%M %p")
        self.last_scan = now
        self.root.after(0, lambda: self.left_info.value_label.config(text=now))

        if code == 0:
            if updates:
                self.title_safe(f"{len(updates)} app update(s) found")
                self.text_safe("Click Install app updates to update through winget.")
                for app in updates:
                    self.log_safe(f"FOUND: {app}")
            else:
                self.title_safe("No app updates found")
                self.text_safe("Everything winget can see appears up to date.")
        else:
            self.title_safe("Scan finished with warnings")
            self.text_safe("Check the log. winget may need source agreements or repair.")

        self.progress_safe(100)
        self.done()

    def parse_winget_upgrade(self, out):
        updates = []
        lines = out.splitlines()

        for line in lines:
            clean = line.strip()

            if not clean:
                continue

            skip_words = [
                "Name",
                "----",
                "The following",
                "No installed package",
                "upgrades available",
                "source agreements",
                "msstore",
                "winget"
            ]

            if any(clean.lower().startswith(w.lower()) for w in skip_words):
                continue

            if "  " in clean and not clean.startswith("-"):
                updates.append(clean)

        return updates[:50]

    def install_updates(self):
        if not self.available_updates:
            ask = messagebox.askyesno(
                APP_NAME,
                "No scan results are loaded.\n\nRun install anyway with winget upgrade --all?"
            )
            if not ask:
                return

        confirm = messagebox.askyesno(
            APP_NAME,
            "Install all available winget app updates?\n\n"
            "This does not use Windows Update, but it may update installed apps."
        )
        if not confirm:
            return

        self.run_thread(self._install_updates)

    def _install_updates(self):
        self.set_busy_safe(True)
        self.progress_safe(0)
        self.nav_safe("● Installing", "#0067c0")
        self.title_safe("Installing app updates...")
        self.text_safe("Using winget upgrade --all.")
        self.log_safe("Starting app updates.")

        if not shutil.which("winget"):
            self.log_safe("Cannot install: winget missing.")
            self.title_safe("winget not found")
            self.text_safe("Install winget/App Installer first.")
            self.done()
            return

        self.progress_safe(20)

        code, out = self.run_cmd([
            "winget",
            "upgrade",
            "--all",
            "--accept-package-agreements",
            "--accept-source-agreements"
        ])

        self.progress_safe(90)

        if code == 0:
            self.title_safe("App updates complete")
            self.text_safe("Restart apps or reboot if anything requests it.")
            self.log_safe("Install process finished.")
        else:
            self.title_safe("Install finished with warnings")
            self.text_safe("Some apps may need manual update or admin permissions.")
            self.log_safe(f"winget exited with code {code}.")

        self.progress_safe(100)
        self.done()

    def run_health_check(self):
        confirm = messagebox.askyesno(
            APP_NAME,
            "Run Windows health checks?\n\n"
            "This runs:\n"
            "sfc /scannow\n\n"
            "It does not use Windows Update."
        )
        if not confirm:
            return

        self.run_thread(self._run_health_check)

    def _run_health_check(self):
        self.set_busy_safe(True)
        self.progress_safe(0)
        self.nav_safe("● Checking", "#0067c0")
        self.title_safe("Running health check...")
        self.text_safe("Running SFC. Admin mode is recommended.")
        self.log_safe("Starting system file checker.")

        self.progress_safe(20)
        code, out = self.run_cmd(["sfc", "/scannow"])

        self.progress_safe(90)

        if code == 0:
            self.title_safe("Health check complete")
            self.text_safe("SFC finished. Check the log for details.")
        else:
            self.title_safe("Health check returned warnings")
            self.text_safe("Try running this app as Administrator.")

        self.progress_safe(100)
        self.done()

    def set_busy_safe(self, value):
        self.root.after(0, lambda: self.set_busy(value))

    def progress_safe(self, value):
        self.root.after(0, lambda: self.progress.config(value=value))

    def title_safe(self, text):
        self.root.after(0, lambda: self.status_title.config(text=text))

    def text_safe(self, text):
        self.root.after(0, lambda: self.status_text.config(text=text))

    def nav_safe(self, text, color):
        self.root.after(0, lambda: self.nav_status.config(text=text, fg=color))

    def log_safe(self, text):
        self.root.after(0, lambda: self.log(text))

    def done(self):
        self.root.after(0, lambda: self.nav_status.config(text="● Ready", fg="#107c10"))
        self.root.after(0, lambda: self.set_busy(False))


def main():
    if os.name != "nt":
        print("Agentic Update is designed for Windows.")
        sys.exit(1)

    root = tk.Tk()
    app = AgenticUpdate(root)
    root.mainloop()


if __name__ == "__main__":
    main()