#!/usr/bin/env python3
"""
Leonardo Auto Create — GUI Desktop (CustomTkinter)
====================================================
Modern dark-themed GUI for leonardo_auto_create.py

Requirements:
  pip install customtkinter playwright httpx rich
  playwright install chromium
"""

import asyncio
import threading
import json
import os
import sys
from pathlib import Path
from datetime import datetime

try:
    import customtkinter as ctk
except ImportError:
    print("Install: pip install customtkinter")
    sys.exit(1)

# Import dari leonardo_auto_create
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

# ════════════════════════════════════════════════════════════
# THEME CONFIG
# ════════════════════════════════════════════════════════════

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Colors
COLOR_BG = "#1a1a2e"
COLOR_CARD = "#16213e"
COLOR_ACCENT = "#0f3460"
COLOR_HIGHLIGHT = "#e94560"
COLOR_SUCCESS = "#00d68f"
COLOR_WARN = "#ffaa00"
COLOR_ERROR = "#ff3d71"
COLOR_TEXT = "#ffffff"
COLOR_TEXT_DIM = "#8888aa"
COLOR_ENTRY = "#0d1b2a"

FONT_TITLE = ("Segoe UI", 24, "bold")
FONT_SUBTITLE = ("Segoe UI", 13)
FONT_BODY = ("Segoe UI", 13)
FONT_SMALL = ("Segoe UI", 11)
FONT_MONO = ("Segoe UI", 11)

# ════════════════════════════════════════════════════════════
# MAIN GUI
# ════════════════════════════════════════════════════════════

class LeonardoGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("Leonardo Auto Create + Auth Capture")
        self.geometry("1040x760")
        self.minsize(760, 520)
        self.configure(fg_color=COLOR_BG)
        
        # State
        self.running = False
        self.browser_running = False
        self.installing = False
        self.log_thread = None
        self.refreshing_accounts = False
        self.captured_data = None
        self.account_select_vars = {}
        
        # Build UI. Footer stays visible; everything else scrolls when the window is small.
        self._build_footer()
        self.content_frame = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            corner_radius=0
        )
        self.content_frame.pack(fill="both", expand=True, padx=0, pady=(0, 0))

        self._build_header()
        self._build_mode_panel()
        self._build_config_panel()
        self._build_progress_panel()
        self._build_accounts_panel()
        self._build_log_panel()
        
        # Start with mode "auto"
        self.mode_var.set("auto")
        self._refresh_accounts_table()
        self.after(60000, self._refresh_scheduler_tick)
        
    def _build_header(self):
        """Header dengan judul + subtitle"""
        header_frame = ctk.CTkFrame(self.content_frame, fg_color=COLOR_CARD, corner_radius=12)
        header_frame.pack(fill="x", padx=20, pady=(18, 10))
        
        title = ctk.CTkLabel(
            header_frame,
            text="🎨  Leonardo Auto Create + Auth Capture",
            font=FONT_TITLE,
            text_color=COLOR_TEXT
        )
        title.pack(pady=(15, 2))
        
        subtitle = ctk.CTkLabel(
            header_frame,
            text="Firefox Relay → Canva → OTP → Leonardo → Token Capture",
            font=FONT_SUBTITLE,
            text_color=COLOR_TEXT_DIM
        )
        subtitle.pack(pady=(0, 15))
        
    def _build_mode_panel(self):
        """Panel pilih mode"""
        mode_frame = ctk.CTkFrame(self.content_frame, fg_color=COLOR_CARD, corner_radius=12)
        mode_frame.pack(fill="x", padx=20, pady=5)
        
        label = ctk.CTkLabel(
            mode_frame,
            text="⚡ Mode Operasi",
            font=FONT_BODY,
            text_color=COLOR_TEXT
        )
        label.pack(anchor="w", padx=15, pady=(10, 5))
        
        radio_frame = ctk.CTkFrame(mode_frame, fg_color="transparent")
        radio_frame.pack(fill="x", padx=15, pady=(0, 10))
        
        self.mode_var = ctk.StringVar(value="auto")
        
        modes = [
            ("auto", "🚀 Auto Create (Full Flow)"),
            ("capture", "📸 Capture Only (Login Manual)"),
            ("auto_headless", "🔄 Auto Create (Headless)"),
        ]
        
        for col in range(3):
            radio_frame.grid_columnconfigure(col, weight=1)

        for col, (value, text) in enumerate(modes):
            rb = ctk.CTkRadioButton(
                radio_frame,
                text=text,
                variable=self.mode_var,
                value=value,
                font=FONT_BODY,
                text_color=COLOR_TEXT,
                fg_color=COLOR_HIGHLIGHT,
                hover_color=COLOR_ACCENT
            )
            rb.grid(row=0, column=col, sticky="w", padx=(0, 10), pady=6)
            
    def _build_config_panel(self):
        """Panel konfigurasi"""
        config_frame = ctk.CTkFrame(self.content_frame, fg_color=COLOR_CARD, corner_radius=12)
        config_frame.pack(fill="x", padx=20, pady=5)
        
        label = ctk.CTkLabel(
            config_frame,
            text="⚙️ Konfigurasi",
            font=FONT_BODY,
            text_color=COLOR_TEXT
        )
        label.pack(anchor="w", padx=15, pady=(10, 5))
        
        input_frame = ctk.CTkFrame(config_frame, fg_color="transparent")
        input_frame.pack(fill="x", padx=15, pady=(0, 10))
        
        # Relay email (optional)
        ctk.CTkLabel(
            input_frame,
            text="Relay Email (opsional):",
            font=FONT_SMALL,
            text_color=COLOR_TEXT_DIM
        ).pack(anchor="w")
        
        self.email_entry = ctk.CTkEntry(
            input_frame,
            placeholder_text="kosongkan untuk auto-generate dari Firefox Relay",
            font=FONT_BODY,
            fg_color=COLOR_ENTRY,
            border_color=COLOR_ACCENT,
            text_color=COLOR_TEXT,
            height=40
        )
        self.email_entry.pack(fill="x", pady=(2, 0))

        target_row = ctk.CTkFrame(input_frame, fg_color="transparent")
        target_row.pack(fill="x", pady=(10, 0))

        ctk.CTkLabel(
            target_row,
            text="Target akun dibuat:",
            font=FONT_SMALL,
            text_color=COLOR_TEXT_DIM
        ).pack(side="left", padx=(0, 10))

        self.target_entry = ctk.CTkEntry(
            target_row,
            placeholder_text="1",
            font=FONT_BODY,
            fg_color=COLOR_ENTRY,
            border_color=COLOR_ACCENT,
            text_color=COLOR_TEXT,
            height=38,
            width=90
        )
        self.target_entry.insert(0, "1")
        self.target_entry.pack(side="left")
        
    def _build_progress_panel(self):
        """Panel progress + step indicator"""
        progress_frame = ctk.CTkFrame(self.content_frame, fg_color=COLOR_CARD, corner_radius=12)
        progress_frame.pack(fill="x", padx=20, pady=5)
        
        # Step label
        self.step_label = ctk.CTkLabel(
            progress_frame,
            text="⏳ Siap menjalankan",
            font=FONT_BODY,
            text_color=COLOR_TEXT_DIM
        )
        self.step_label.pack(anchor="w", padx=15, pady=(10, 5))

        self.batch_label = ctk.CTkLabel(
            progress_frame,
            text="Akun jadi: 0 / 0",
            font=FONT_SMALL,
            text_color=COLOR_TEXT_DIM
        )
        self.batch_label.pack(anchor="w", padx=15, pady=(0, 6))
        
        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(
            progress_frame,
            progress_color=COLOR_HIGHLIGHT,
            fg_color=COLOR_ENTRY,
            height=14
        )
        self.progress_bar.pack(fill="x", padx=15, pady=(0, 5))
        self.progress_bar.set(0)
        
        # Step indicators (8 steps)
        steps_frame = ctk.CTkFrame(progress_frame, fg_color="transparent")
        steps_frame.pack(fill="x", padx=15, pady=(0, 10))
        
        self.step_indicators = []
        step_names = ["Relay", "RelayDel", "Canva", "OTP", "Verify", "Invite", "Login", "Cleanup"]
        for col in range(4):
            steps_frame.grid_columnconfigure(col, weight=1)
        
        for i, name in enumerate(step_names):
            indicator = ctk.CTkLabel(
                steps_frame,
                text=f"  {i+1}. {name}  ",
                font=FONT_SMALL,
                text_color=COLOR_TEXT_DIM,
                fg_color=COLOR_ENTRY,
                corner_radius=6,
                padx=5,
                pady=4
            )
            indicator.grid(row=i // 4, column=i % 4, sticky="ew", padx=3, pady=3)
            self.step_indicators.append(indicator)

    def _build_accounts_panel(self):
        """Panel daftar akun Leonardo yang berhasil dicapture."""
        accounts_frame = ctk.CTkFrame(self.content_frame, fg_color=COLOR_CARD, corner_radius=12)
        accounts_frame.pack(fill="x", padx=20, pady=5)

        top_frame = ctk.CTkFrame(accounts_frame, fg_color="transparent")
        top_frame.pack(fill="x", padx=15, pady=(10, 5))

        label = ctk.CTkLabel(
            top_frame,
            text="Daftar Akun Leonardo",
            font=FONT_BODY,
            text_color=COLOR_TEXT
        )
        label.pack(side="left")

        self.refresh_accounts_btn = ctk.CTkButton(
            top_frame,
            text="Refresh Dipilih",
            font=FONT_SMALL,
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_HIGHLIGHT,
            width=132,
            height=32,
            command=self.on_refresh_accounts
        )
        self.refresh_accounts_btn.pack(side="right")

        self.accounts_table = ctk.CTkScrollableFrame(
            accounts_frame,
            fg_color=COLOR_ENTRY,
            corner_radius=8,
            height=150
        )
        self.accounts_table.pack(fill="x", padx=15, pady=(0, 10))

        self.account_headers = ["Pilih", "No", "Email", "Auth", "Credits", "Cookies", "Last Refresh", "Next Refresh", "Status", "File JSON"]
        self.account_widths = [52, 42, 150, 78, 62, 58, 108, 108, 88, 180]
            
    def _build_log_panel(self):
        """Panel log output"""
        log_frame = ctk.CTkFrame(self.content_frame, fg_color=COLOR_CARD, corner_radius=12)
        log_frame.pack(fill="x", padx=20, pady=(5, 16))
        
        label = ctk.CTkLabel(
            log_frame,
            text="📋 Log Output",
            font=FONT_BODY,
            text_color=COLOR_TEXT
        )
        label.pack(anchor="w", padx=15, pady=(10, 5))
        
        self.log_text = ctk.CTkTextbox(
            log_frame,
            font=FONT_MONO,
            fg_color=COLOR_ENTRY,
            text_color=COLOR_TEXT,
            corner_radius=8,
            wrap="word",
            height=180
        )
        self.log_text.pack(fill="x", padx=15, pady=(0, 10))
        self.log_text.configure(state="disabled")
        
    def _build_footer(self):
        """Footer dengan tombol action"""
        footer_frame = ctk.CTkFrame(self, fg_color=COLOR_BG)
        footer_frame.pack(fill="x", side="bottom", padx=16, pady=(6, 12))

        self.install_btn = ctk.CTkButton(
            footer_frame,
            text="📦  INSTALL",
            font=("Segoe UI", 15, "bold"),
            fg_color="#2d4a22",
            hover_color="#3d6a2e",
            text_color=COLOR_TEXT,
            height=48,
            corner_radius=12,
            command=self.on_install
        )
        self.install_btn.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.browser_btn = ctk.CTkButton(
            footer_frame,
            text="\U0001F310  BUKA BROWSER",
            font=("Segoe UI", 15, "bold"),
            fg_color="#1b6b3a",
            hover_color="#28a745",
            text_color=COLOR_TEXT,
            height=48,
            corner_radius=12,
            command=self.on_open_browser
        )
        self.browser_btn.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        self.start_btn = ctk.CTkButton(
            footer_frame,
            text="\u25b6  MULAI",
            font=("Segoe UI", 15, "bold"),
            fg_color=COLOR_HIGHLIGHT,
            hover_color=COLOR_ERROR,
            text_color=COLOR_TEXT,
            height=48,
            corner_radius=12,
            command=self.on_start
        )
        self.start_btn.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        self.stop_btn = ctk.CTkButton(
            footer_frame,
            text="\u23f9  STOP",
            font=("Segoe UI", 15, "bold"),
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_HIGHLIGHT,
            text_color=COLOR_TEXT,
            height=48,
            corner_radius=12,
            command=self.on_stop,
            state="disabled"
        )
        self.stop_btn.pack(side="left", fill="x", expand=True)
        
    # ════════════════════════════════════════════════════════
    # LOGIC
    # ════════════════════════════════════════════════════════
    
    def log(self, msg, level="info"):
        """Append log message to textbox"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        color_map = {
            "info": COLOR_TEXT,
            "ok": COLOR_SUCCESS,
            "warn": COLOR_WARN,
            "error": COLOR_ERROR,
            "step": "#4488ff"
        }
        color = color_map.get(level, COLOR_TEXT)
        
        icon_map = {
            "info": "▸",
            "ok": "✓",
            "warn": "⚠",
            "error": "✗",
            "step": "▶"
        }
        icon = icon_map.get(level, "•")
        
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{timestamp}] {icon} {msg}\n", color)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _format_account_time(self, value):
        if not value:
            return "-"
        try:
            return datetime.fromisoformat(value).strftime("%m-%d %H:%M")
        except Exception:
            return str(value)[:14]

    def _account_select_key(self, account):
        return account.get("id") or (account.get("email") or "").strip().lower()

    def _refresh_accounts_table(self):
        """Reload account registry into the GUI table."""
        selected_before = {
            key for key, var in self.account_select_vars.items()
            if key and var.get()
        }
        self.account_select_vars = {}

        for widget in self.accounts_table.winfo_children():
            widget.destroy()

        for col, header in enumerate(self.account_headers):
            label = ctk.CTkLabel(
                self.accounts_table,
                text=header,
                font=("Segoe UI", 12, "bold"),
                text_color=COLOR_TEXT,
                width=self.account_widths[col],
                anchor="w"
            )
            label.grid(row=0, column=col, sticky="w", padx=4, pady=(2, 4))

        try:
            import leonardo_auto_create as lac
            accounts = lac.load_accounts()
        except Exception as e:
            accounts = []
            self.log(f"Gagal membaca list akun: {e}", "warn")

        if not accounts:
            empty = ctk.CTkLabel(
                self.accounts_table,
                text="Belum ada akun Leonardo yang berhasil dicapture.",
                font=FONT_SMALL,
                text_color=COLOR_TEXT_DIM,
                anchor="w"
            )
            empty.grid(row=1, column=0, columnspan=len(self.account_headers), sticky="w", padx=4, pady=8)
            return

        for row, account in enumerate(accounts, start=1):
            account_key = self._account_select_key(account)
            select_var = ctk.BooleanVar(value=account_key in selected_before)
            self.account_select_vars[account_key] = select_var
            checkbox = ctk.CTkCheckBox(
                self.accounts_table,
                text="",
                variable=select_var,
                width=self.account_widths[0],
                fg_color=COLOR_HIGHLIGHT,
                hover_color=COLOR_ACCENT,
                border_color=COLOR_TEXT_DIM,
                checkmark_color=COLOR_TEXT,
            )
            checkbox.grid(row=row, column=0, sticky="w", padx=8, pady=2)

            values = [
                str(row),
                str(account.get("email") or "N/A")[:34],
                str(account.get("auth_mode") or "-")[:18],
                str(account.get("credit_balance") if account.get("credit_balance") is not None else "-"),
                str(len(account.get("all_cookies") or [])),
                self._format_account_time(account.get("last_refresh_at") or account.get("last_capture_at")),
                self._format_account_time(account.get("next_refresh_at")),
                str(account.get("status") or "-")[:20],
                Path(account.get("auth_file") or "").name if account.get("auth_file") else "-",
            ]
            status_col = len(values) - 2
            for col, value in enumerate(values):
                color = COLOR_SUCCESS if col == status_col and "fail" not in value.lower() else COLOR_TEXT
                if col == status_col and "fail" in value.lower():
                    color = COLOR_ERROR
                label = ctk.CTkLabel(
                    self.accounts_table,
                    text=value,
                    font=("Segoe UI", 11),
                    text_color=color,
                    width=self.account_widths[col + 1],
                    anchor="w"
                )
                label.grid(row=row, column=col + 1, sticky="w", padx=4, pady=2)

    def on_refresh_accounts(self):
        """Manual refresh for selected saved accounts."""
        if self.refreshing_accounts:
            self.log("Refresh akun masih berjalan...", "warn")
            return
        selected_keys = [
            key for key, var in self.account_select_vars.items()
            if key and var.get()
        ]
        if not selected_keys:
            self.log("Centang akun yang mau di-refresh manual dulu.", "warn")
            return
        self.log(f"Manual refresh bearer token untuk {len(selected_keys)} akun dimulai...", "step")
        self.refresh_accounts_btn.configure(state="disabled")
        thread = threading.Thread(target=self._run_refresh_accounts, args=(True, selected_keys), daemon=True)
        thread.start()

    def _refresh_scheduler_tick(self):
        """Refresh due accounts every 2 hours without blocking the GUI."""
        try:
            if not self.running and not self.browser_running and not self.refreshing_accounts:
                import leonardo_auto_create as lac
                now = datetime.now()
                due = []
                for account in lac.load_accounts():
                    due_text = account.get("next_refresh_at")
                    due_at = None
                    if due_text:
                        try:
                            due_at = datetime.fromisoformat(due_text)
                        except Exception:
                            due_at = None
                    if not due_at or due_at <= now:
                        due.append(account)
                if due:
                    self.log(f"Auto refresh token untuk {len(due)} akun due...", "step")
                    thread = threading.Thread(target=self._run_refresh_accounts, args=(False, None), daemon=True)
                    thread.start()
        finally:
            self.after(60000, self._refresh_scheduler_tick)

    def _run_refresh_accounts(self, force=False, selected_keys=None):
        """Run account token refresh in a background thread."""
        self.refreshing_accounts = True
        try:
            import leonardo_auto_create as lac
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            if selected_keys:
                accounts = lac.load_accounts()
                selected_set = set(selected_keys)
                updated = []
                for index, account in enumerate(accounts):
                    account_key = self._account_select_key(account)
                    if account_key not in selected_set:
                        continue
                    email = account.get("email") or account_key
                    self.after(0, lambda e=email: self.log(f"Refresh manual: {e}", "info"))
                    refreshed = loop.run_until_complete(lac.refresh_account_bearer(account, headless=True))
                    accounts[index] = refreshed
                    updated.append(refreshed)
                    lac.save_account_auth_file(refreshed)
                if updated:
                    lac.save_accounts(accounts)
            else:
                updated = loop.run_until_complete(lac.refresh_due_accounts(headless=True, force=force))

            loop.close()
            count = len(updated or [])
            self.after(0, lambda c=count: self.log(f"Refresh akun selesai: {c} akun diproses", "ok"))
        except Exception as e:
            err_msg = str(e)
            self.after(0, lambda msg=err_msg: self.log(f"Refresh akun gagal: {msg}", "error"))
        finally:
            self.refreshing_accounts = False
            self.after(0, self._refresh_accounts_table)
            self.after(0, lambda: self.refresh_accounts_btn.configure(state="normal"))
        
    def update_step(self, step_num, title, total=8):
        """Update progress bar + step indicator"""
        progress = step_num / total
        self.progress_bar.set(progress)
        self.step_label.configure(
            text=f"🔧 Step {step_num}/{total}: {title}",
            text_color=COLOR_TEXT
        )
        
        # Highlight current step
        for i, indicator in enumerate(self.step_indicators):
            if i < step_num - 1:
                # Completed
                indicator.configure(text_color=COLOR_SUCCESS, fg_color="#0a3d2a")
            elif i == step_num - 1:
                # Current
                indicator.configure(text_color=COLOR_HIGHLIGHT, fg_color="#3d1a2a")
            else:
                # Pending
                indicator.configure(text_color=COLOR_TEXT_DIM, fg_color=COLOR_ENTRY)
                
    def mark_step_done(self, step_num, success=True):
        """Update step indicator untuk step yang selesai."""
        if step_num < 1 or step_num > len(self.step_indicators):
            return  # Guard: step_num di luar range, skip
        indicator = self.step_indicators[step_num - 1]
        if success:
            indicator.configure(text_color=COLOR_SUCCESS, fg_color="#0a3d2a")
        else:
            indicator.configure(text_color=COLOR_ERROR, fg_color="#3d0a1a")
            
    def on_install(self):
        """Install semua dependencies yang dibutuhkan"""
        if self.installing or self.running or self.browser_running:
            self.log("Tunggu proses lain selesai dulu!", "warn")
            return

        self.installing = True
        self.install_btn.configure(state="disabled", text="⏳  INSTALLING...")
        self.browser_btn.configure(state="disabled")
        self.start_btn.configure(state="disabled")
        self.log("Memulai instalasi dependencies...", "step")
        self.log("Install: playwright, httpx, rich, customtkinter, requests", "info")
        self.log("Plus download Chromium browser untuk Playwright", "info")
        self.log("Mohon tunggu, proses ini bisa 2-5 menit...", "info")

        thread = threading.Thread(target=self._run_install, daemon=True)
        thread.start()

    def _run_install(self):
        """Run installation in background thread"""
        import subprocess
        import sys
        import os

        def run_cmd(cmd, desc):
            self.after(0, lambda d=desc: self.log(f"▶ {d}", "step"))
            try:
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    cwd=str(SCRIPT_DIR),
                )
                for line in process.stdout:
                    line = line.strip()
                    if line:
                        self.after(0, lambda l=line: self.log(f"  {l}", "info"))
                process.wait()
                if process.returncode == 0:
                    self.after(0, lambda d=desc: self.log(f"✅ {d} - OK", "ok"))
                    return True
                else:
                    self.after(0, lambda d=desc, rc=process.returncode: self.log(f"❌ {d} - FAIL (exit {rc})", "error"))
                    return False
            except Exception as e:
                self.after(0, lambda d=desc, e=str(e): self.log(f"❌ {d} - ERROR: {e}", "error"))
                return False

        # Step 1: Upgrade pip
        run_cmd([sys.executable, "-m", "pip", "install", "--upgrade", "pip"], "Upgrade pip")

        # Step 2: Install requirements.txt
        req_file = SCRIPT_DIR / "requirements.txt"
        if req_file.exists():
            ok = run_cmd([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], "Install requirements.txt")
            if not ok:
                self.after(0, lambda: self.log("Fallback: install manual package...", "warn"))
                run_cmd([sys.executable, "-m", "pip", "install", "playwright>=1.40", "httpx>=0.25", "rich>=13.0", "customtkinter>=5.2", "requests>=2.28"], "Install packages manual")
        else:
            run_cmd([sys.executable, "-m", "pip", "install", "playwright>=1.40", "httpx>=0.25", "rich>=13.0", "customtkinter>=5.2", "requests>=2.28"], "Install packages")

        # Step 3: Install Chromium
        run_cmd([sys.executable, "-m", "playwright", "install", "chromium"], "Download Chromium browser")

        # Step 4: Install deps sistem (Linux only)
        if os.name != "nt":
            run_cmd([sys.executable, "-m", "playwright", "install-deps", "chromium"], "Install system deps (Linux)")

        # Step 5: Verify
        self.after(0, lambda: self.log("Verifikasi install...", "step"))
        verify_ok = True
        for pkg in ["playwright", "httpx", "rich", "customtkinter", "requests"]:
            try:
                __import__(pkg)
                self.after(0, lambda p=pkg: self.log(f"  ✅ {p}", "ok"))
            except ImportError:
                self.after(0, lambda p=pkg: self.log(f"  ❌ {p} - TIDAK TERINSTALL", "error"))
                verify_ok = False

        if verify_ok:
            self.after(0, lambda: self.log("\n🎉 INSTALL SELESAI! Semua siap dipakai.", "ok"))
            self.after(0, lambda: self.log("Klik BUKA BROWSER untuk login, lalu MULAI.", "info"))
        else:
            self.after(0, lambda: self.log("\n⚠️ Beberapa package gagal. Coba install manual.", "warn"))

        self.after(0, self._on_install_complete)

    def _on_install_complete(self):
        """Called when install completes"""
        self.installing = False
        self.install_btn.configure(state="normal", text="📦  INSTALL")
        self.browser_btn.configure(state="normal")
        self.start_btn.configure(state="normal")

    def on_open_browser(self):
        """Open browser for manual login (Gmail, Firefox Relay, Canva, dll)"""
        if self.running or self.browser_running:
            self.log("Browser sudah terbuka atau automation sedang berjalan!", "warn")
            return

        self.browser_running = True
        self.browser_btn.configure(state="disabled", text="⏳  BROWSER TERBUKA...")
        self.start_btn.configure(state="disabled")
        self.log("Membuka browser untuk login manual...", "step")
        self.log("Silakan login ke: Gmail, Firefox Relay, Canva, Leonardo, dll.", "info")
        self.log("Tutup browser jika sudah selesai login.", "info")

        thread = threading.Thread(target=self._run_browser, daemon=True)
        thread.start()

    def _run_browser(self):
        """Run browser in background thread for manual login"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._open_browser_async())
            loop.close()
        except Exception as e:
            err_msg = str(e)
            self.after(0, lambda msg=err_msg: self.log(f"Browser error: {msg}", "error"))
        finally:
            self.after(0, self._on_browser_closed)

    async def _open_browser_async(self):
        """Open Chromium with persistent profile for manual login"""
        from playwright.async_api import async_playwright

        browser_data = SCRIPT_DIR / "browser_profile"

        async with async_playwright() as p:
            self.after(0, lambda: self.log("Browser Chromium terbuka!", "ok"))

            browser = await p.chromium.launch_persistent_context(
                user_data_dir=str(browser_data),
                headless=False,
                viewport={"width": 1280, "height": 800},
                locale="en-US",
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--lang=en-US",
                ],
            )

            page = browser.pages[0] if browser.pages else await browser.new_page()

            # Buka Gmail untuk login
            await page.goto("https://accounts.google.com/", wait_until="domcontentloaded", timeout=30000)

            self.after(0, lambda: self.log("Login ke Gmail dulu, lalu buka tab lain jika perlu.", "info"))
            self.after(0, lambda: self.log("Setelah selesai, TUTUP browser untuk kembali ke app.", "info"))

            # Tunggu sampai browser ditutup user
            try:
                await browser.wait_for_event("close", timeout=0)
            except Exception:
                while True:
                    try:
                        pages = browser.pages
                        if not pages:
                            break
                        await asyncio.sleep(1)
                    except Exception:
                        break

            try:
                await browser.close()
            except Exception:
                pass

    def _on_browser_closed(self):
        """Called when manual browser is closed"""
        self.browser_running = False
        self.browser_btn.configure(state="normal", text="🌐  BUKA BROWSER")
        self.start_btn.configure(state="normal")
        self.log("Browser ditutup. Siap menjalankan automation!", "ok")

    def on_start(self):
        """Start the automation"""
        if self.running:
            return
        if self.browser_running:
            self.log("Tutup browser manual dulu sebelum mulai automation!", "warn")
            return
        if self.installing:
            self.log("Tunggu instalasi selesai dulu!", "warn")
            return
        if self.browser_running:
            self.log("Tutup browser manual dulu sebelum mulai bot!", "warn")
            return
            
        self.running = True
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.browser_btn.configure(state="disabled")
        
        mode = self.mode_var.get()
        relay_email = self.email_entry.get().strip() or None
        try:
            target_accounts = int((self.target_entry.get() or "1").strip())
        except ValueError:
            target_accounts = 1
        target_accounts = max(1, target_accounts)
        if mode == "capture":
            target_accounts = 1
        
        self.log("=" * 50, "info")
        self.log(f"Memulai mode: {mode.upper()}", "step")
        self.log(f"Target akun: {target_accounts}", "info")
        self.batch_label.configure(text=f"Akun jadi: 0 / {target_accounts}", text_color=COLOR_TEXT)
        if relay_email:
            self.log(f"Email: {relay_email}", "info")
            if target_accounts > 1:
                self.log("Email manual hanya dipakai untuk akun pertama; akun berikutnya auto-generate Relay.", "warn")
        self.log("=" * 50, "info")
        
        # Run in background thread
        self.log_thread = threading.Thread(
            target=self._run_automation,
            args=(mode, relay_email, target_accounts),
            daemon=True
        )
        self.log_thread.start()
        
    def on_stop(self):
        """Stop the automation"""
        self.running = False
        self.log("Dihentikan oleh user", "warn")
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.browser_btn.configure(state="normal")
        self.step_label.configure(text="\u23f9 Dihentikan", text_color=COLOR_WARN)
        
    def _run_automation(self, mode, relay_email, target_accounts=1):
        """Run automation in background thread"""
        try:
            # Patch logger to send to GUI
            import leonardo_auto_create as lac
            
            original_log = lac.logger.log
            
            def gui_log(msg, level="info"):
                # Call original log (file)
                original_log(msg, level)
                # Send to GUI
                self.after(0, lambda: self.log(msg, level))
                
            def gui_step(num, title):
                lac.logger.current_step = num
                lac.logger.log(f"STEP {num}/{lac.logger.total_steps}: {title}", "step")
                self.after(0, lambda n=num, t=title: self.update_step(n, t))
                
            lac.logger.log = gui_log
            lac.logger.step = gui_step
            lac.logger.ok = lambda m: gui_log(m, "ok")
            lac.logger.warn = lambda m: gui_log(m, "warn")
            lac.logger.error = lambda m: gui_log(m, "error")
            lac.logger.info = lambda m: gui_log(m, "info")
            
            if mode == "capture":
                self.after(0, lambda: self.log("Mode: Capture Only", "info"))
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                from leonardo_auth_capture import capture_auth
                loop.run_until_complete(capture_auth())
                loop.close()
                
            elif mode in ("auto", "auto_headless"):
                headless = (mode == "auto_headless")
                self.after(0, lambda: self.log(f"Headless: {headless}", "info"))

                success_count = 0
                for run_index in range(1, target_accounts + 1):
                    if not self.running:
                        self.after(0, lambda: self.log("Batch dihentikan sebelum target selesai", "warn"))
                        break

                    current_relay_email = relay_email if run_index == 1 else None
                    self.after(0, lambda i=run_index, t=target_accounts: self.log(f"Mulai akun {i}/{t}", "step"))
                    self.after(
                        0,
                        lambda ok=success_count, t=target_accounts: self.batch_label.configure(
                            text=f"Akun jadi: {ok} / {t}",
                            text_color=COLOR_TEXT,
                        )
                    )

                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    captured, results = loop.run_until_complete(
                        lac.auto_create_account(headless=headless, relay_email=current_relay_email)
                    )
                    loop.close()

                    self.captured_data = captured

                    if lac.has_complete_leonardo_auth(captured):
                        success_count += 1
                        self.after(0, lambda c=success_count, t=target_accounts: self.log(f"Akun jadi: {c}/{t}", "ok"))
                    else:
                        self.after(0, lambda i=run_index: self.log(f"Akun {i} belum lengkap bearer/credit", "warn"))

                    self.after(
                        0,
                        lambda ok=success_count, t=target_accounts: self.batch_label.configure(
                            text=f"Akun jadi: {ok} / {t}",
                            text_color=COLOR_SUCCESS if ok >= t else COLOR_TEXT,
                        )
                    )

                    # Update step indicators based on last run results
                    for i, r in enumerate(results, 1):
                        success = r.get("status") in ("OK", "SKIP")
                        self.after(0, lambda n=i, s=success: self.mark_step_done(n, s))

                    self.after(0, lambda data=captured: self._show_result(data))
                    self.after(0, self._refresh_accounts_table)

                self.after(
                    0,
                    lambda c=success_count, t=target_accounts: self.log(
                        f"Batch selesai. Total akun jadi: {c}/{t}",
                        "ok" if c >= t else "warn",
                    )
                )
                
        except Exception as e:
            err_msg = str(e)
            import traceback
            tb_msg = traceback.format_exc()
            self.after(0, lambda msg=err_msg: self.log(f"ERROR: {msg}", "error"))
            self.after(0, lambda msg=tb_msg: self.log(msg, "error"))
        finally:
            self.after(0, self._on_complete)
            self.after(0, self._refresh_accounts_table)
            
    def _show_result(self, captured):
        """Show final capture result in log"""
        self.log("", "info")
        self.log("╔═══════════════════════════════════════╗", "step")
        self.log("║       AUTH CAPTURE RESULT             ║", "step")
        self.log("╠═══════════════════════════════════════╣", "step")
        
        email = captured.get("email", "N/A")
        token = captured.get("access_token")
        auth_ok = bool(
            token
            or captured.get("session_token")
            or captured.get("session_cookie")
            or captured.get("cookie_header")
        )
        auth_mode = captured.get("auth_mode") or ("bearer" if token else "cookie_session")
        credits = captured.get("credit_balance", "N/A")
        cookies = len(captured.get("all_cookies", []))
        
        self.log(f"║  Email:   {str(email)[:35]:<35} ║", "info")
        
        if auth_ok and token:
            self.log(f"║  Auth:    ✓ BEARER ({len(token)} chars)           ║", "ok")
        elif auth_ok:
            self.log(f"║  Auth:    ✓ {str(auth_mode)[:28]:<28} ║", "ok")
        else:
            self.log(f"║  Auth:    ✗ NOT FOUND                    ║", "error")
            
        self.log(f"║  Credits: {str(credits)[:35]:<35} ║", "info")
        self.log(f"║  Cookies: {str(cookies) + ' cookies':<35} ║", "info")
        self.log("╚═══════════════════════════════════════╝", "step")
        self.log("", "info")
        
        if auth_ok:
            self.log("✅ Auth Leonardo berhasil di-capture dan dikirim ke VPS!", "ok")
        else:
            self.log("❌ Auth Leonardo tidak ditemukan. Cek log untuk detail.", "error")
            
    def _on_complete(self):
        """Called when automation completes"""
        self.running = False
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.browser_btn.configure(state="normal")
        self.install_btn.configure(state="normal")
        self.browser_btn.configure(state="normal")
        self.progress_bar.set(1.0)
        self.step_label.configure(text="Selesai", text_color=COLOR_SUCCESS)
        
        # Reset step colors after 3 seconds
        self.after(3000, self._reset_steps)
        
    def _reset_steps(self):
        """Reset step indicators"""
        for indicator in self.step_indicators:
            indicator.configure(text_color=COLOR_TEXT_DIM, fg_color=COLOR_ENTRY)
        self.progress_bar.set(0)
        self.step_label.configure(text="⏳ Siap menjalankan", text_color=COLOR_TEXT_DIM)


# ════════════════════════════════════════════════════════════
# ENTRY POINT
# ════════════════════════════════════════════════════════════

def main():
    app = LeonardoGUI()
    app.mainloop()

if __name__ == "__main__":
    main()
