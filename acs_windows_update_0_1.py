"""
ac's windows update 0.1

A Windows 11 Settings / Windows Update style updater shell.
This is NOT Microsoft Windows Update and does not replace it.
It can:
  - scan/install app updates through winget
  - open the real Windows Update Settings page
  - run a safe SFC health check

Python 3.10+ / Python 3.14-ready.
Run on Windows:
  python acs_windows_update_0_1.py
"""

import datetime
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


APP_NAME = "ac's windows update"
APP_VERSION = "0.1"
APP_TITLE = f"{APP_NAME} {APP_VERSION}"
WINDOWS_VERSION_LABEL = "Windows 11, version 25H2"

BG = "#f3f3f3"
PANEL = "#ffffff"
SIDEBAR = "#f7f7f7"
CARD_BORDER = "#e5e5e5"
TEXT = "#1f1f1f"
MUTED = "#606060"
BLUE = "#0067c0"
BLUE_LIGHT = "#60cdff"
BLACK = "#000000"
GREEN = "#107c10"
RED = "#c42b1c"
YELLOW = "#f9a825"

FONT = "Segoe UI"
FONT_TITLE = (FONT, 26, "bold")
FONT_H1 = (FONT, 18, "bold")
FONT_H2 = (FONT, 13, "bold")
FONT_BODY = (FONT, 10)
FONT_SMALL = (FONT, 9)
FONT_MONO = ("Consolas", 10)


class UpdateProgress25H2:
    """
    Windows-Update-like staged progress model.

    It uses weighted phases and a smooth easing curve. The goal is to feel
    like Windows Update: fast at the beginning, slower while installing, then
    a short final verification phase. It is deterministic, not random.
    """

    PHASES = [
        ("Getting things ready", 4, 350),
        ("Checking for updates", 14, 650),
        ("Preparing download", 24, 700),
        ("Downloading", 58, 1300),
        ("Installing", 88, 1700),
        ("Verifying", 97, 800),
        ("Finishing up", 100, 550),
    ]

    @staticmethod
    def ease(x: float) -> float:
        x = max(0.0, min(1.0, x))
        # Smoothstep with a tiny cosine drag near the middle, like real update
        # progress bars that move quickly, slow down, then complete.
        smooth = x * x * (3.0 - 2.0 * x)
        drag = math.sin(math.pi * x) * 0.025
        return max(0.0, min(1.0, smooth - drag))

    @classmethod
    def phase_plan(cls):
        return list(cls.PHASES)


class Win11ProgressBar(tk.Canvas):
    def __init__(self, parent, **kwargs):
        super().__init__(
            parent,
            height=8,
            bg=PANEL,
            highlightthickness=0,
            bd=0,
            relief="flat",
            **kwargs,
        )
        self.value = 0.0
        self.bind("<Configure>", lambda _event: self.draw())

    def set_value(self, value: float):
        self.value = max(0.0, min(100.0, float(value)))
        self.draw()

    def draw(self):
        self.delete("all")
        width = max(1, self.winfo_width())
        height = max(1, self.winfo_height())
        radius = height // 2
        self.create_rectangle(0, 2, width, height - 2, fill="#e6e6e6", outline="")
        fill_width = int(width * (self.value / 100.0))
        if fill_width > 0:
            self.create_rectangle(0, 2, fill_width, height - 2, fill=BLUE, outline="")
            self.create_oval(0, 2, height, height - 2, fill=BLUE, outline="")
            if fill_width > radius:
                self.create_oval(fill_width - height, 2, fill_width, height - 2, fill=BLUE, outline="")


class ACSWindowsUpdate:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1080x720")
        self.root.minsize(980, 650)
        self.root.configure(bg=BG)

        self.busy = False
        self.last_checked = "Never"
        self.available_updates = []
        self.buttons = []
        self.log_queue = queue.Queue()
        self.progress_value = 0.0

        self.set_dpi_awareness()
        self.build_ui()
        self.poll_log_queue()
        self.boot_check()

    def set_dpi_awareness(self):
        if os.name != "nt":
            return
        try:
            import ctypes

            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

    def build_ui(self):
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        self.sidebar = tk.Frame(self.root, bg=SIDEBAR, width=260)
        self.sidebar.grid(row=0, column=0, sticky="ns")
        self.sidebar.grid_propagate(False)

        self.main = tk.Frame(self.root, bg=BG)
        self.main.grid(row=0, column=1, sticky="nsew", padx=34, pady=28)
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(4, weight=1)

        self.build_sidebar()
        self.build_main()

    def build_sidebar(self):
        tk.Label(
            self.sidebar,
            text="Settings",
            bg=SIDEBAR,
            fg=TEXT,
            font=(FONT, 20, "bold"),
            anchor="w",
        ).pack(fill="x", padx=24, pady=(26, 14))

        search = tk.Label(
            self.sidebar,
            text="Search settings",
            bg="#ffffff",
            fg="#777777",
            font=FONT_BODY,
            anchor="w",
            padx=14,
            pady=8,
            highlightbackground="#d7d7d7",
            highlightthickness=1,
        )
        search.pack(fill="x", padx=20, pady=(0, 20))

        self.nav_status = tk.Label(
            self.sidebar,
            text="● Ready",
            bg=SIDEBAR,
            fg=GREEN,
            font=(FONT, 10, "bold"),
            anchor="w",
        )
        self.nav_status.pack(fill="x", padx=24, pady=(0, 12))

        self.nav_button("🏠  Home", self.show_home)
        self.nav_button("🔄  Windows Update", self.show_home, selected=True)
        self.nav_button("📦  App updates", self.scan_updates)
        self.nav_button("🧰  Health tools", self.run_health_check)
        self.nav_button("⚙  Advanced options", self.show_advanced)
        self.nav_button("ℹ  About", self.show_about)

        tk.Label(
            self.sidebar,
            text="Custom shell only.\nOpen the real Windows Update\npage for OS updates.",
            bg=SIDEBAR,
            fg=MUTED,
            font=FONT_SMALL,
            justify="left",
        ).pack(side="bottom", anchor="w", padx=24, pady=24)

    def nav_button(self, text, command, selected=False):
        bg = "#e8f1fb" if selected else SIDEBAR
        fg = BLUE if selected else TEXT
        btn = tk.Button(
            self.sidebar,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            activebackground="#e8f1fb",
            activeforeground=BLUE,
            relief="flat",
            bd=0,
            anchor="w",
            padx=22,
            pady=10,
            font=(FONT, 10, "bold" if selected else "normal"),
            cursor="hand2",
        )
        btn.pack(fill="x", padx=14, pady=2)
        return btn

    def build_main(self):
        top = tk.Frame(self.main, bg=BG)
        top.grid(row=0, column=0, sticky="ew")
        top.grid_columnconfigure(0, weight=1)

        tk.Label(top, text="Windows Update", bg=BG, fg=TEXT, font=FONT_TITLE).grid(row=0, column=0, sticky="w")
        tk.Label(top, text=APP_TITLE, bg=BG, fg=MUTED, font=FONT_SMALL).grid(row=1, column=0, sticky="w", pady=(2, 0))

        self.refresh_btn = self.action_button(top, "↻", self.scan_updates, width=3)
        self.refresh_btn.grid(row=0, column=1, rowspan=2, sticky="e", padx=(14, 0))

        self.status_card = self.card(self.main)
        self.status_card.grid(row=1, column=0, sticky="ew", pady=(24, 16))
        self.status_card.grid_columnconfigure(1, weight=1)

        icon = tk.Label(
            self.status_card,
            text="✓",
            bg=BLUE,
            fg="#ffffff",
            font=(FONT, 28, "bold"),
            width=2,
            height=1,
        )
        icon.grid(row=0, column=0, rowspan=4, sticky="n", padx=(24, 18), pady=26)

        self.status_title = tk.Label(
            self.status_card,
            text="You're up to date",
            bg=PANEL,
            fg=TEXT,
            font=FONT_H1,
            anchor="w",
        )
        self.status_title.grid(row=0, column=1, sticky="ew", padx=(0, 24), pady=(24, 3))

        self.status_text = tk.Label(
            self.status_card,
            text=f"{WINDOWS_VERSION_LABEL} style dashboard. Scan apps with winget or open the real Windows Update Settings page.",
            bg=PANEL,
            fg=MUTED,
            font=FONT_BODY,
            anchor="w",
            justify="left",
            wraplength=720,
        )
        self.status_text.grid(row=1, column=1, sticky="ew", padx=(0, 24))

        self.progress = Win11ProgressBar(self.status_card)
        self.progress.grid(row=2, column=1, sticky="ew", padx=(0, 24), pady=(18, 6))

        self.progress_label = tk.Label(
            self.status_card,
            text="0%",
            bg=PANEL,
            fg=MUTED,
            font=FONT_SMALL,
            anchor="w",
        )
        self.progress_label.grid(row=3, column=1, sticky="w", padx=(0, 24), pady=(0, 10))

        controls = tk.Frame(self.status_card, bg=PANEL)
        controls.grid(row=4, column=1, sticky="w", padx=(0, 24), pady=(2, 24))

        self.check_btn = self.action_button(controls, "Check for updates", self.scan_updates)
        self.check_btn.pack(side="left", padx=(0, 10))

        self.install_btn = self.action_button(controls, "Download & install", self.install_updates)
        self.install_btn.pack(side="left", padx=(0, 10))

        self.real_update_btn = self.action_button(controls, "Open real Windows Update", self.open_real_windows_update)
        self.real_update_btn.pack(side="left")

        self.info_grid = tk.Frame(self.main, bg=BG)
        self.info_grid.grid(row=2, column=0, sticky="ew", pady=(0, 16))
        self.info_grid.grid_columnconfigure(0, weight=1)
        self.info_grid.grid_columnconfigure(1, weight=1)
        self.info_grid.grid_columnconfigure(2, weight=1)

        self.last_card, self.last_value = self.small_card(self.info_grid, "Last checked", self.last_checked)
        self.last_card.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        self.version_card, self.version_value = self.small_card(self.info_grid, "Target style", WINDOWS_VERSION_LABEL)
        self.version_card.grid(row=0, column=1, sticky="ew", padx=8)

        self.backend_card, self.backend_value = self.small_card(self.info_grid, "Backend", "winget + Settings shortcut")
        self.backend_card.grid(row=0, column=2, sticky="ew", padx=(8, 0))

        self.options = tk.Frame(self.main, bg=BG)
        self.options.grid(row=3, column=0, sticky="ew", pady=(0, 16))
        self.options.grid_columnconfigure(0, weight=1)
        self.options.grid_columnconfigure(1, weight=1)

        self.option_tile(self.options, "Pause updates", "Visual-only tile for the custom shell", "Not enabled").grid(
            row=0, column=0, sticky="ew", padx=(0, 8)
        )
        self.option_tile(self.options, "Update history", "Shows app-scan results in the log below", "View log").grid(
            row=0, column=1, sticky="ew", padx=(8, 0)
        )

        self.log_box = tk.Text(
            self.main,
            bg="#0c0c0c",
            fg="#d7d7d7",
            insertbackground="#ffffff",
            selectbackground=BLUE,
            font=FONT_MONO,
            wrap="word",
            relief="flat",
            bd=0,
            padx=14,
            pady=12,
        )
        self.log_box.grid(row=4, column=0, sticky="nsew")
        self.log("ac's windows update 0.1 started.")
        self.log("This is a Windows 11-style shell. It does not replace Microsoft Windows Update.")

    def card(self, parent):
        return tk.Frame(parent, bg=PANEL, highlightbackground=CARD_BORDER, highlightthickness=1)

    def action_button(self, parent, text, command, width=None):
        btn = tk.Button(
            parent,
            text=text,
            command=command,
            bg=BLACK,
            fg=BLUE,
            activebackground="#111111",
            activeforeground=BLUE_LIGHT,
            disabledforeground="#315777",
            relief="flat",
            bd=0,
            padx=16,
            pady=9,
            font=(FONT, 10, "bold"),
            cursor="hand2",
            width=width,
        )
        self.buttons.append(btn)
        return btn

    def small_card(self, parent, title, value):
        frame = self.card(parent)
        tk.Label(frame, text=title, bg=PANEL, fg=MUTED, font=FONT_SMALL, anchor="w").pack(
            fill="x", padx=16, pady=(14, 2)
        )
        label = tk.Label(frame, text=value, bg=PANEL, fg=TEXT, font=FONT_H2, anchor="w", wraplength=260)
        label.pack(fill="x", padx=16, pady=(0, 14))
        return frame, label

    def option_tile(self, parent, title, desc, action_text):
        frame = self.card(parent)
        frame.grid_columnconfigure(0, weight=1)
        tk.Label(frame, text=title, bg=PANEL, fg=TEXT, font=FONT_H2, anchor="w").grid(
            row=0, column=0, sticky="ew", padx=16, pady=(14, 2)
        )
        tk.Label(frame, text=desc, bg=PANEL, fg=MUTED, font=FONT_BODY, anchor="w").grid(
            row=1, column=0, sticky="ew", padx=16
        )
        tk.Label(frame, text=action_text, bg=PANEL, fg=BLUE, font=(FONT, 10, "bold"), anchor="w").grid(
            row=2, column=0, sticky="ew", padx=16, pady=(8, 14)
        )
        return frame

    def boot_check(self):
        if os.name != "nt":
            self.nav("● Windows only", RED)
            self.set_status(
                "Windows required",
                "This UI can open on many systems, but winget and real Windows Update actions are Windows-only.",
            )
            self.log("NOTICE: Non-Windows OS detected. Windows-specific buttons may not work.")
            return

        if shutil.which("winget"):
            self.log("winget found. App update scanning is available.")
        else:
            self.backend_value.config(text="Settings shortcut only")
            self.log("winget was not found. Install App Installer from Microsoft Store to scan app updates.")

    def set_status(self, title, text):
        self.status_title.config(text=title)
        self.status_text.config(text=text)

    def set_progress(self, value):
        self.progress_value = max(0.0, min(100.0, float(value)))
        self.progress.set_value(self.progress_value)
        self.progress_label.config(text=f"{round(self.progress_value):d}%")

    def animate_progress(self, target, duration_ms=500, message=None):
        if message:
            self.status_text.config(text=message)
        start = self.progress_value
        target = max(0.0, min(100.0, float(target)))
        started = time.perf_counter()
        duration = max(1, duration_ms) / 1000.0

        def step():
            elapsed = time.perf_counter() - started
            x = min(1.0, elapsed / duration)
            eased = UpdateProgress25H2.ease(x)
            self.set_progress(start + (target - start) * eased)
            if x < 1.0 and self.busy:
                self.root.after(16, step)

        step()

    def run_intro_algorithm(self):
        self.set_progress(0)
        delay = 0
        for message, target, duration in UpdateProgress25H2.phase_plan()[:3]:
            self.root.after(delay, lambda m=message, t=target, d=duration: self.animate_progress(t, d, m))
            delay += duration + 80

    def set_busy(self, value: bool):
        self.busy = value
        for button in self.buttons:
            try:
                button.config(state="disabled" if value else "normal")
            except tk.TclError:
                pass

    def nav(self, text, color):
        self.nav_status.config(text=text, fg=color)

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

    def run_thread(self, target):
        if self.busy:
            messagebox.showinfo(APP_TITLE, "Already working. Let the current task finish first.")
            return
        self.set_busy(True)
        threading.Thread(target=target, daemon=True).start()

    def run_cmd(self, args):
        self.log_from_thread("> " + " ".join(args))
        try:
            proc = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                shell=False,
            )
            lines = []
            if proc.stdout:
                for line in proc.stdout:
                    clean = line.rstrip()
                    if clean:
                        lines.append(clean)
                        self.log_from_thread(clean)
            proc.wait()
            return proc.returncode, "\n".join(lines)
        except Exception as exc:
            self.log_from_thread(f"ERROR: {exc}")
            return 1, str(exc)

    def show_home(self):
        self.set_status(
            "You're up to date",
            f"{WINDOWS_VERSION_LABEL} style dashboard. Scan apps with winget or open the real Windows Update Settings page.",
        )
        self.nav("● Ready", GREEN)
        self.log("Windows Update home opened.")

    def show_advanced(self):
        self.set_status(
            "Advanced options",
            "Use the real Settings app for delivery optimization, optional updates, recovery, and Windows Update policies.",
        )
        self.log("Advanced options opened.")

    def show_about(self):
        messagebox.showinfo(
            APP_TITLE,
            f"{APP_TITLE}\n\n"
            "Windows 11-style updater shell.\n\n"
            "Black buttons with blue text are enabled.\n"
            "Uses math-based staged progress animation.\n\n"
            "Backend actions:\n"
            "• winget upgrade scan/install for apps\n"
            "• sfc /scannow health check\n"
            "• ms-settings:windowsupdate shortcut\n\n"
            "This is not Microsoft Windows Update.",
        )

    def open_real_windows_update(self):
        if os.name != "nt":
            messagebox.showinfo(APP_TITLE, "The real Windows Update Settings page can only be opened on Windows.")
            return
        try:
            os.startfile("ms-settings:windowsupdate")
            self.log("Opened real Windows Update Settings page.")
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"Could not open Windows Update Settings:\n{exc}")
            self.log(f"ERROR opening Windows Update Settings: {exc}")

    def scan_updates(self):
        self.run_thread(self._scan_updates)

    def _scan_updates(self):
        self.root.after(0, lambda: self.nav("● Checking", BLUE))
        self.root.after(0, lambda: self.set_status("Checking for updates...", "Looking for app updates through winget."))
        self.root.after(0, self.run_intro_algorithm)
        self.log_from_thread("Starting Windows 11-style app update scan.")

        if os.name != "nt":
            self.finish_with_error("Windows required", "winget scanning is only available on Windows.")
            return

        if not shutil.which("winget"):
            self.finish_with_error("winget not found", "Install App Installer / winget first, or use the real Windows Update Settings button.")
            return

        time.sleep(0.8)
        self.root.after(0, lambda: self.animate_progress(42, 500, "Checking installed packages..."))
        code, output = self.run_cmd(["winget", "upgrade", "--accept-source-agreements"])

        self.root.after(0, lambda: self.animate_progress(88, 650, "Verifying scan results..."))
        updates = self.parse_winget_upgrade(output)
        self.available_updates = updates

        now = datetime.datetime.now().strftime("%b %d, %Y %I:%M %p")
        self.last_checked = now
        self.root.after(0, lambda: self.last_value.config(text=now))

        if code == 0 and updates:
            self.root.after(0, lambda: self.set_status(f"{len(updates)} app update(s) found", "Select Download & install to update apps with winget."))
            for app in updates:
                self.log_from_thread(f"FOUND: {app}")
        elif code == 0:
            self.root.after(0, lambda: self.set_status("You're up to date", "No winget app updates were found."))
            self.log_from_thread("No app updates found by winget.")
        else:
            self.root.after(0, lambda: self.set_status("Scan finished with warnings", "Check the log. winget may need repair, agreements, or admin permission."))
            self.log_from_thread(f"winget exited with code {code}.")

        self.root.after(0, lambda: self.animate_progress(100, 450, "Done."))
        self.root.after(600, lambda: self.nav("● Ready", GREEN))
        self.root.after(600, lambda: self.set_busy(False))

    def install_updates(self):
        if self.busy:
            messagebox.showinfo(APP_TITLE, "Already working. Let the current task finish first.")
            return

        if not self.available_updates:
            proceed = messagebox.askyesno(
                APP_TITLE,
                "No scan results are loaded.\n\nRun winget upgrade --all anyway?",
            )
            if not proceed:
                return

        confirm = messagebox.askyesno(
            APP_TITLE,
            "Download and install all available winget app updates?\n\n"
            "This updates apps/packages, not Windows itself.",
        )
        if confirm:
            self.run_thread(self._install_updates)

    def _install_updates(self):
        self.root.after(0, lambda: self.nav("● Installing", BLUE))
        self.root.after(0, lambda: self.set_status("Downloading & installing...", "Using winget upgrade --all."))
        self.root.after(0, lambda: self.set_progress(0))
        self.log_from_thread("Starting app updates.")

        if os.name != "nt":
            self.finish_with_error("Windows required", "winget installation is only available on Windows.")
            return

        if not shutil.which("winget"):
            self.finish_with_error("winget not found", "Install App Installer / winget first.")
            return

        # 25H2-style staged progress: move to the downloading/installing range,
        # let winget do the real work, then verify and finish.
        self.root.after(0, lambda: self.animate_progress(18, 600, "Preparing download..."))
        time.sleep(0.7)
        self.root.after(0, lambda: self.animate_progress(62, 1600, "Downloading app updates..."))

        code, _output = self.run_cmd([
            "winget",
            "upgrade",
            "--all",
            "--accept-package-agreements",
            "--accept-source-agreements",
        ])

        self.root.after(0, lambda: self.animate_progress(92, 900, "Installing and verifying..."))
        time.sleep(1.0)

        if code == 0:
            self.available_updates = []
            self.root.after(0, lambda: self.set_status("Updates installed", "Restart apps or reboot if any installer asks for it."))
            self.log_from_thread("Install process finished successfully.")
        else:
            self.root.after(0, lambda: self.set_status("Install finished with warnings", "Some apps may need manual update or administrator permission."))
            self.log_from_thread(f"winget exited with code {code}.")

        self.root.after(0, lambda: self.animate_progress(100, 500, "Done."))
        self.root.after(650, lambda: self.nav("● Ready", GREEN))
        self.root.after(650, lambda: self.set_busy(False))

    def run_health_check(self):
        if self.busy:
            messagebox.showinfo(APP_TITLE, "Already working. Let the current task finish first.")
            return

        confirm = messagebox.askyesno(
            APP_TITLE,
            "Run Windows health check?\n\n"
            "This runs sfc /scannow. Administrator mode is recommended.",
        )
        if confirm:
            self.run_thread(self._run_health_check)

    def _run_health_check(self):
        self.root.after(0, lambda: self.nav("● Checking", YELLOW))
        self.root.after(0, lambda: self.set_status("Running health check...", "System File Checker is running."))
        self.root.after(0, lambda: self.set_progress(0))
        self.log_from_thread("Starting sfc /scannow.")

        if os.name != "nt":
            self.finish_with_error("Windows required", "SFC is only available on Windows.")
            return

        self.root.after(0, lambda: self.animate_progress(35, 800, "Scanning protected system files..."))
        code, _output = self.run_cmd(["sfc", "/scannow"])
        self.root.after(0, lambda: self.animate_progress(100, 700, "Finishing health check..."))

        if code == 0:
            self.root.after(0, lambda: self.set_status("Health check complete", "SFC finished. Check the log for details."))
        else:
            self.root.after(0, lambda: self.set_status("Health check returned warnings", "Try running this app as Administrator."))
            self.log_from_thread(f"sfc exited with code {code}.")

        self.root.after(850, lambda: self.nav("● Ready", GREEN))
        self.root.after(850, lambda: self.set_busy(False))

    def finish_with_error(self, title, text):
        self.log_from_thread(f"ERROR: {title} - {text}")
        self.root.after(0, lambda: self.set_status(title, text))
        self.root.after(0, lambda: self.nav("● Error", RED))
        self.root.after(0, lambda: self.animate_progress(100, 450, "Stopped."))
        self.root.after(550, lambda: self.set_busy(False))

    @staticmethod
    def parse_winget_upgrade(output: str):
        updates = []
        in_table = False
        ignored_starts = (
            "name",
            "----",
            "source agreements",
            "the following",
            "no installed package",
            "no available upgrade",
            "upgrades available",
            "msstore",
            "winget",
        )

        for line in output.splitlines():
            clean = line.strip()
            lower = clean.lower()
            if not clean:
                continue
            if lower.startswith("name") and " id " in f" {lower} ":
                in_table = True
                continue
            if any(lower.startswith(prefix) for prefix in ignored_starts):
                continue
            if clean.startswith("-") or clean.startswith("\\") or clean.startswith("|"):
                continue
            if in_table and "  " in clean:
                updates.append(clean)

        return updates[:75]


def main():
    root = tk.Tk()
    ACSWindowsUpdate(root)
    root.mainloop()


if __name__ == "__main__":
    main()
