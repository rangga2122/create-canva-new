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

FONT_TITLE = ("Segoe UI", 22, "bold")
FONT_SUBTITLE = ("Segoe UI", 12)
FONT_BODY = ("Segoe UI", 11)
FONT_SMALL = ("Segoe UI", 9)
FONT_MONO = ("Consolas", 10)

# ════════════════════════════════════════════════════════════
# MAIN GUI
# ════════════════════════════════════════════════════════════

class LeonardoGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("Leonardo Auto Create + Auth Capture")
        self.geometry("900x700")
        self.minsize(800, 600)
        self.configure(fg_color=COLOR_BG)
        
        # State
        self.running = False
        self.log_thread = None
        self.captured_data = None
        
        # Build UI
        self._build_header()
        self._build_mode_panel()
        self._build_config_panel()
        self._build_progress_panel()
        self._build_log_panel()
        self._build_footer()
        
        # Start with mode "auto"
        self.mode_var.set("auto")
        
    def _build_header(self):
        """Header dengan judul + subtitle"""
        header_frame = ctk.CTkFrame(self, fg_color=COLOR_CARD, corner_radius=12)
        header_frame.pack(fill="x", padx=20, pady=(20, 10))
        
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
        mode_frame = ctk.CTkFrame(self, fg_color=COLOR_CARD, corner_radius=12)
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
        
        for value, text in modes:
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
            rb.pack(side="left", padx=(0, 20))
            
    def _build_config_panel(self):
        """Panel konfigurasi"""
        config_frame = ctk.CTkFrame(self, fg_color=COLOR_CARD, corner_radius=12)
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
            height=32
        )
        self.email_entry.pack(fill="x", pady=(2, 0))
        
    def _build_progress_panel(self):
        """Panel progress + step indicator"""
        progress_frame = ctk.CTkFrame(self, fg_color=COLOR_CARD, corner_radius=12)
        progress_frame.pack(fill="x", padx=20, pady=5)
        
        # Step label
        self.step_label = ctk.CTkLabel(
            progress_frame,
            text="⏳ Siap menjalankan",
            font=FONT_BODY,
            text_color=COLOR_TEXT_DIM
        )
        self.step_label.pack(anchor="w", padx=15, pady=(10, 5))
        
        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(
            progress_frame,
            progress_color=COLOR_HIGHLIGHT,
            fg_color=COLOR_ENTRY,
            height=12
        )
        self.progress_bar.pack(fill="x", padx=15, pady=(0, 5))
        self.progress_bar.set(0)
        
        # Step indicators (7 steps)
        steps_frame = ctk.CTkFrame(progress_frame, fg_color="transparent")
        steps_frame.pack(fill="x", padx=15, pady=(0, 10))
        
        self.step_indicators = []
        step_names = ["Relay", "Canva", "OTP", "Verify", "Invite", "Login", "Capture"]
        
        for i, name in enumerate(step_names):
            indicator = ctk.CTkLabel(
                steps_frame,
                text=f"  {i+1}. {name}  ",
                font=FONT_SMALL,
                text_color=COLOR_TEXT_DIM,
                fg_color=COLOR_ENTRY,
                corner_radius=6,
                padx=5,
                pady=2
            )
            indicator.pack(side="left", padx=2)
            self.step_indicators.append(indicator)
            
    def _build_log_panel(self):
        """Panel log output"""
        log_frame = ctk.CTkFrame(self, fg_color=COLOR_CARD, corner_radius=12)
        log_frame.pack(fill="both", expand=True, padx=20, pady=5)
        
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
            wrap="word"
        )
        self.log_text.pack(fill="both", expand=True, padx=15, pady=(0, 10))
        self.log_text.configure(state="disabled")
        
    def _build_footer(self):
        """Footer dengan tombol action"""
        footer_frame = ctk.CTkFrame(self, fg_color="transparent")
        footer_frame.pack(fill="x", padx=20, pady=(5, 20))
        
        self.start_btn = ctk.CTkButton(
            footer_frame,
            text="▶  MULAI",
            font=("Segoe UI", 14, "bold"),
            fg_color=COLOR_HIGHLIGHT,
            hover_color=COLOR_ERROR,
            text_color=COLOR_TEXT,
            height=45,
            corner_radius=12,
            command=self.on_start
        )
        self.start_btn.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        self.stop_btn = ctk.CTkButton(
            footer_frame,
            text="⏹  STOP",
            font=("Segoe UI", 14, "bold"),
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_HIGHLIGHT,
            text_color=COLOR_TEXT,
            height=45,
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
        
    def update_step(self, step_num, title, total=7):
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
        """Mark step as done"""
        indicator = self.step_indicators[step_num - 1]
        if success:
            indicator.configure(text_color=COLOR_SUCCESS, fg_color="#0a3d2a")
        else:
            indicator.configure(text_color=COLOR_ERROR, fg_color="#3d0a1a")
            
    def on_start(self):
        """Start the automation"""
        if self.running:
            return
            
        self.running = True
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        
        mode = self.mode_var.get()
        relay_email = self.email_entry.get().strip() or None
        
        self.log("=" * 50, "info")
        self.log(f"Memulai mode: {mode.upper()}", "step")
        if relay_email:
            self.log(f"Email: {relay_email}", "info")
        self.log("=" * 50, "info")
        
        # Run in background thread
        self.log_thread = threading.Thread(
            target=self._run_automation,
            args=(mode, relay_email),
            daemon=True
        )
        self.log_thread.start()
        
    def on_stop(self):
        """Stop the automation"""
        self.running = False
        self.log("Dihentikan oleh user", "warn")
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.step_label.configure(text="⏹ Dihentikan", text_color=COLOR_WARN)
        
    def _run_automation(self, mode, relay_email):
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
                
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                captured, results = loop.run_until_complete(
                    lac.auto_create_account(headless=headless, relay_email=relay_email)
                )
                loop.close()
                
                self.captured_data = captured
                
                # Update step indicators based on results
                for i, r in enumerate(results, 1):
                    success = r.get("status") in ("OK", "SKIP", "PARTIAL")
                    self.after(0, lambda n=i, s=success: self.mark_step_done(n, s))
                
                # Show final result
                self.after(0, lambda: self._show_result(captured))
                
        except Exception as e:
            self.after(0, lambda: self.log(f"ERROR: {e}", "error"))
            import traceback
            self.after(0, lambda: self.log(traceback.format_exc(), "error"))
        finally:
            self.after(0, self._on_complete)
            
    def _show_result(self, captured):
        """Show final capture result in log"""
        self.log("", "info")
        self.log("╔═══════════════════════════════════════╗", "step")
        self.log("║       AUTH CAPTURE RESULT             ║", "step")
        self.log("╠═══════════════════════════════════════╣", "step")
        
        email = captured.get("email", "N/A")
        token = captured.get("access_token")
        credits = captured.get("credit_balance", "N/A")
        cookies = len(captured.get("all_cookies", []))
        
        self.log(f"║  Email:   {str(email)[:35]:<35} ║", "info")
        
        if token:
            self.log(f"║  Token:   ✓ CAPTURED ({len(token)} chars)         ║", "ok")
        else:
            self.log(f"║  Token:   ✗ NOT FOUND                    ║", "error")
            
        self.log(f"║  Credits: {str(credits)[:35]:<35} ║", "info")
        self.log(f"║  Cookies: {str(cookies) + ' cookies':<35} ║", "info")
        self.log("╚═══════════════════════════════════════╝", "step")
        self.log("", "info")
        
        if token:
            self.log("✅ Token berhasil di-capture dan dikirim ke VPS!", "ok")
        else:
            self.log("❌ Token tidak ditemukan. Cek log untuk detail.", "error")
            
    def _on_complete(self):
        """Called when automation completes"""
        self.running = False
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.progress_bar.set(1.0)
        self.step_label.configure(text="✅ Selesai", text_color=COLOR_SUCCESS)
        
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
