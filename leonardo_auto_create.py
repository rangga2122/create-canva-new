#!/usr/bin/env python3
"""
Leonardo Auto Create Account + Auth Capture
============================================
Automated flow:
  1. TempMail API → Generate email
  2. Canva signup with temp email
  3. TempMail API → Get OTP from Canva
  4. Canva OTP verification
  5. Accept Canva team invite
  6. Leonardo login via Canva SSO
  7. Capture bearer token + cookies
  8. Send auth to VPS server

Requirements:
  pip install playwright httpx rich
  playwright install chromium

Usage:
  python leonardo_auto_create.py
  python leonardo_auto_create.py --relay-email "manual@email.com"
  python leonardo_auto_create.py --headless
"""

import asyncio
import json
import os
import sys
import re
import time
import base64
import argparse
import subprocess
import tempfile
import secrets
import string
import shutil
from pathlib import Path
from datetime import datetime, timedelta

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("Install: pip install playwright && playwright install chromium")
    sys.exit(1)

try:
    import httpx
except ImportError:
    print("Install: pip install httpx")
    sys.exit(1)

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
    from rich.table import Table
    from rich.prompt import Prompt, Confirm
    from rich.live import Live
    from rich.text import Text
    from rich.align import Align
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("Install: pip install rich (for fancy UI)")

# ════════════════════════════════════════════════════════════
# CONFIG
# ════════════════════════════════════════════════════════════

VPS_IP = "43.133.150.196"
VPS_PORT = 1940
VPS_USER = "ubuntu"
VPS_PASS = os.getenv("VPS_PASS", "")
SERVER_URL_HTTP = f"http://{VPS_IP}:{VPS_PORT}"
SERVER_URL_HTTPS = "https://leonardo.azkazamdigital.com"
SERVER_BEARER_IMPORT_URL = f"{SERVER_URL_HTTPS}/api/bearer/import"

# Eteum Pool — auto-import Canva account
SCRIPT_DIR = Path(__file__).parent
ETTEUM_HOST = os.getenv("ETTEUM_HOST", "43.133.150.196")
ETTEUM_PORT = int(os.getenv("ETTEUM_PORT", "1930"))
ETTEUM_API_KEY = os.getenv("ETTEUM_API_KEY", "Nr201105")
ETTEUM_API_URL = f"http://{ETTEUM_HOST}:{ETTEUM_PORT}/api/accounts"
# HTTPS domain (jika tersedia)
ETTEUM_HTTPS_URL = os.getenv("ETTEUM_HTTPS_URL", f"https://etteum.azkazamdigital.com/api/accounts")

# Canva accounts local file
CANVA_ACCOUNTS_FILE = SCRIPT_DIR / "canva_accounts.json"
DEFAULT_ACCOUNT_SERVER_URL = "https://akunleonardo.azkazamdigital.com/api/accounts/import"
DEFAULT_GOOGLE_SHEET_WEBHOOK_URL = os.getenv("GOOGLE_SHEET_WEBHOOK_URL", "").strip()

# Canva team invite token
CANVA_INVITE_TOKEN = "Efh588Iq4SrbCcHbeWASrw"
CANVA_INVITE_URL = f"https://www.canva.com/brand/join?token={CANVA_INVITE_TOKEN}&referrer=team-invite"

# URLs
FIREFOX_RELAY_URL = "https://relay.firefox.com/"
CANVA_URL = "https://www.canva.com/id_id/"
CANVA_SIGNUP_URL = "https://www.canva.com/id_id/signup/"
GMAIL_SPAM_URL = "https://mail.google.com/mail/u/0/#spam"
LEONARDO_LOGIN_URL = "https://app.leonardo.ai/auth/login"
TEMP_MAIL_BASE_URL = "https://mail.digitalku.store"
TEMP_MAIL_VOUCHER_CODES = [
    code.strip()
    for code in os.getenv("TEMP_MAIL_VOUCHER_CODES", "Z1R4Y7,Z1R4Y7").split(",")
    if code.strip()
]
TEMP_MAIL_PREFERRED_DOMAINS = [
    domain.strip()
    for domain in os.getenv(
        "TEMP_MAIL_DOMAINS",
        "atlaz.tech,redmail.tech,digitalku.tech,mailserver.biz.id,zoro.biz.id,asuraimu.eu.cc",
    ).split(",")
    if domain.strip()
]

# File paths
AUTH_FILE = SCRIPT_DIR / "leonardo_auth.json"
ACCOUNTS_FILE = SCRIPT_DIR / "leonardo_accounts.json"
ACCOUNT_AUTH_DIR = SCRIPT_DIR / "auth_accounts"
ACCOUNT_UPLOAD_DIR = SCRIPT_DIR / "account_uploads"
APP_SETTINGS_FILE = SCRIPT_DIR / "leonardo_settings.json"
BROWSER_DATA = SCRIPT_DIR / "browser_profile"
BROWSER_PARALLEL_DATA = SCRIPT_DIR / "browser_profiles"
LOG_FILE = SCRIPT_DIR / "logs" / "auto_create.log"
LOG_FILE.parent.mkdir(exist_ok=True)
ACCOUNT_AUTH_DIR.mkdir(exist_ok=True)
ACCOUNT_UPLOAD_DIR.mkdir(exist_ok=True)
BROWSER_PARALLEL_DATA.mkdir(exist_ok=True)

DEFAULT_APP_SETTINGS = {
    "mode": "auto",
    "relay_email": "",
    "target_accounts": 1,
    "parallel_browsers": 1,
    "capture_auth": True,
    "send_bearer_to_vps": True,
    "upload_account_json": False,
    "account_server_url": DEFAULT_ACCOUNT_SERVER_URL,
    "send_google_sheet": False,
    "google_sheet_url": DEFAULT_GOOGLE_SHEET_WEBHOOK_URL,
    "refresh_headless": True,
    "refresh_show_chrome": False,
}


def load_app_settings():
    """Load shared GUI/terminal settings."""
    settings = dict(DEFAULT_APP_SETTINGS)
    try:
        if APP_SETTINGS_FILE.exists():
            data = json.loads(APP_SETTINGS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                settings.update(data)
    except Exception as e:
        logger.warn(f"Failed to load settings: {e}") if "logger" in globals() else None
    return settings


def save_app_settings(settings):
    """Save shared GUI/terminal settings."""
    data = dict(load_app_settings())
    data.update({k: v for k, v in (settings or {}).items() if v is not None})
    try:
        APP_SETTINGS_FILE.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        return True
    except Exception as e:
        logger.warn(f"Failed to save settings: {e}") if "logger" in globals() else None
        return False


def clear_browser_profile_files(profile_dir):
    """Remove history/cache/storage files from a bot browser profile before launch."""
    profile_dir = Path(profile_dir)
    if not profile_dir.exists():
        return

    root = profile_dir.resolve()
    targets = [
        "Default/Cache",
        "Default/Code Cache",
        "Default/GPUCache",
        "Default/History",
        "Default/History-journal",
        "Default/Cookies",
        "Default/Cookies-journal",
        "Default/Local Storage",
        "Default/IndexedDB",
        "Default/Service Worker",
        "Default/Session Storage",
        "Default/Sessions",
        "Default/Shared Dictionary",
        "Default/Network",
        "Cache",
        "Code Cache",
        "GPUCache",
    ]

    removed = 0
    for rel_path in targets:
        target = profile_dir / rel_path
        try:
            resolved = target.resolve()
            if root != resolved and root not in resolved.parents:
                continue
            if target.is_dir():
                shutil.rmtree(target, ignore_errors=True)
                removed += 1
            elif target.exists():
                target.unlink()
                removed += 1
        except Exception:
            pass
    if removed:
        logger.info(f"Browser profile history/cache cleared: {removed} item(s)")

# ════════════════════════════════════════════════════════════
# LOGGER + UI
# ════════════════════════════════════════════════════════════

if RICH_AVAILABLE:
    console = Console()
else:
    console = None

class Logger:
    def __init__(self):
        self.steps = []
        self.current_step = 0
        self.total_steps = 8
    
    def log(self, msg, level="info"):
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        self.steps.append(line)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        if console:
            colors = {"info": "cyan", "ok": "bold green", "warn": "bold yellow", "error": "bold red", "step": "bold blue"}
            icons = {"info": "⟢", "ok": "✓", "warn": "⚠", "error": "✗", "step": "▸"}
            try:
                console.print(f"  [{colors.get(level, 'white')}]{icons.get(level, '•')}[/{colors.get(level, 'white')}] {msg}")
            except UnicodeEncodeError:
                pass
        else:
            try:
                print(f"  [{level.upper()}] {msg}")
            except UnicodeEncodeError:
                pass

    def step(self, num, title):
        self.current_step = num
        self.log(f"STEP {num}/{self.total_steps}: {title}", "step")
        if console:
            console.print()

    def ok(self, msg):
        self.log(msg, "ok")

    def warn(self, msg):
        self.log(msg, "warn")

    def error(self, msg):
        self.log(msg, "error")

    def info(self, msg):
        self.log(msg, "info")

logger = Logger()

def print_banner():
    try:
        _print_banner_impl()
    except UnicodeEncodeError:
        pass

def _print_banner_impl():
    if console:
        # Animated gradient banner
        console.print()
        title = Text()
        title.append("╔" + "═" * 61 + "╗\n", style="bold blue")
        title.append("║" + " " * 61 + "║\n", style="bold blue")
        title.append("║  ", style="bold blue")
        title.append("🎨 Leonardo Auto Create + Auth Capture", style="bold white on blue")
        title.append("           ║\n", style="bold blue")
        title.append("║  ", style="bold blue")
        title.append("TempMail → Canva → OTP → Leonardo → Token", style="bold cyan")
        title.append("       ║\n", style="bold blue")
        title.append("║" + " " * 61 + "║\n", style="bold blue")
        title.append("╚" + "═" * 61 + "╝", style="bold blue")
        console.print(Align.center(title))
        
        # Version info
        info = Text()
        info.append("  v1.0  ", style="bold magenta")
        info.append("│  ", style="dim")
        info.append("Playwright + Rich UI  ", style="cyan")
        info.append("│  ", style="dim")
        info.append(f"{datetime.now().strftime('%Y-%m-%d %H:%M')}", style="dim white")
        console.print(Align.center(info))
        console.print()
        
        # Flow diagram
        flow = Text()
        flow.append("  ", style="")
        flow.append("[1]", style="bold yellow on dark_magenta")
        flow.append(" TempMail  ", style="magenta")
        flow.append("→", style="dim")
        flow.append(" [2]", style="bold yellow on dark_magenta")
        flow.append(" Canva Signup  ", style="magenta")
        flow.append("→", style="dim")
        flow.append(" [3]", style="bold yellow on dark_magenta")
        flow.append(" Temp OTP  ", style="magenta")
        flow.append("→", style="dim")
        flow.append(" [4]", style="bold yellow on dark_magenta")
        flow.append(" Verify  ", style="magenta")
        flow.append("→", style="dim")
        flow.append(" [5]", style="bold yellow on dark_magenta")
        flow.append(" Team Invite  ", style="magenta")
        flow.append("→", style="dim")
        flow.append(" [6]", style="bold yellow on dark_magenta")
        flow.append(" Leonardo  ", style="magenta")
        flow.append("→", style="dim")
        flow.append(" [7]", style="bold yellow on dark_magenta")
        flow.append(" Capture", style="magenta")
        console.print(Align.center(flow))
        console.print()
        
    else:
        print("\n╔═══════════════════════════════════════════════════════════╗")
        print("║  Leonardo Auto Create Account + Auth Capture              ║")
        print("║  TempMail → Canva → OTP → Leonardo → Capture              ║")
        print("╚═══════════════════════════════════════════════════════════╝\n")


def print_step_header(num, title, total=8):
    """Print a styled step header panel"""
    try:
        _print_step_header_impl(num, title, total)
    except UnicodeEncodeError:
        pass

def _print_step_header_impl(num, title, total=8):
    if console:
        progress_pct = int((num - 1) / total * 100)
        bar_filled = int(progress_pct / 5)
        bar_empty = 20 - bar_filled
        progress_bar = "█" * bar_filled + "░" * bar_empty
        
        header = Text()
        header.append(f"  STEP {num}/{total}  ", style="bold white on blue")
        header.append(f" {title}", style="bold cyan")
        header.append(f"\n  [{progress_bar}] {progress_pct}%", style="bold green")
        
        console.print()
        console.print(Panel(header, border_style="blue", padding=(0, 1), expand=False))
        console.print()
    else:
        print(f"\n  === STEP {num}/{total}: {title} ===\n")


def print_summary(results):
    try:
        _print_summary_impl(results)
    except UnicodeEncodeError:
        pass

def _print_summary_impl(results):
    if console:
        console.print()
        console.print(Panel(Text("AUTO CREATE SUMMARY", style="bold white on magenta", justify="center"), 
                           border_style="magenta", expand=True))
        console.print()
        
        table = Table(box=box.DOUBLE_EDGE, show_header=True, header_style="bold magenta on dark_magenta", 
                     title_style="bold", show_lines=True)
        table.add_column("#", style="bold cyan", width=4, justify="center")
        table.add_column("Step", style="bold white", width=35)
        table.add_column("Status", justify="center", width=10)
        table.add_column("Details", style="yellow", width=30)
        
        for i, r in enumerate(results, 1):
            status = r.get("status", "?")
            if status == "OK":
                status_text = "[bold green]✓ PASS[/bold green]"
            elif status == "FAIL":
                status_text = "[bold red]✗ FAIL[/bold red]"
            elif status == "SKIP":
                status_text = "[dim]→ SKIP[/dim]"
            elif status == "PARTIAL":
                status_text = "[bold yellow]◐ PARTIAL[/bold yellow]"
            else:
                status_text = f"[yellow]{status}[/yellow]"
            
            table.add_row(str(i), r.get("desc", ""), status_text, r.get("data", ""))
        
        console.print(table)
        console.print()
        
        # Final result banner
        all_ok = all(r.get("status") in ("OK", "SKIP") for r in results)
        if all_ok:
            console.print(Panel(Text("✅ ALL STEPS COMPLETED SUCCESSFULLY!", style="bold white on green", justify="center"),
                               border_style="green", expand=True))
        else:
            failed = [r for r in results if r.get("status") == "FAIL"]
            console.print(Panel(Text(f"⚠️  {len(failed)} STEP(S) FAILED — Check logs", style="bold white on red", justify="center"),
                               border_style="red", expand=True))
        console.print()
    else:
        print("\n--- Summary ---")
        for i, r in enumerate(results, 1):
            print(f"  {i}. {r.get('desc', '')}: {r.get('status', '?')}")


def print_final_result(captured):
    """Print final capture result in a nice box"""
    try:
        _print_final_result_impl(captured)
    except UnicodeEncodeError:
        pass


def has_captured_auth(captured):
    """Return True when either bearer token or cookie-based Leonardo session exists."""
    return bool(
        captured.get("access_token")
        or captured.get("session_token")
        or captured.get("session_cookie")
        or captured.get("cookie_header")
    )


def has_complete_leonardo_auth(captured):
    """Return True only when bearer token and credit balance are both captured."""
    return bool(captured.get("access_token") and captured.get("credit_balance") is not None)


def has_google_sheet_ready_account(captured, minimum_credit=8500):
    """Return True when an account is ready to be sent to Google Sheet only."""
    if not captured.get("email"):
        return False
    credits = captured.get("credit_balance")
    try:
        return credits is not None and float(credits) >= float(minimum_credit)
    except Exception:
        return False


def has_credit_spend_verified(captured, full_credit=8500):
    """Return True only after a new account has spent at least some Leonardo credit."""
    credits = captured.get("credit_balance")
    try:
        return credits is not None and float(credits) < float(full_credit)
    except Exception:
        return False


def has_export_ready_account(captured, full_credit=8500):
    """Return True when captured auth is complete and the initial full credit has decreased."""
    return has_complete_leonardo_auth(captured) and has_credit_spend_verified(captured, full_credit=full_credit)


def extract_credit_balance(payload):
    """Find a Leonardo credit balance value in nested API payloads."""
    candidates = []

    def as_number(value):
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str):
            try:
                number = float(value)
                return int(number) if number.is_integer() else number
            except Exception:
                return None
        return None

    def walk(value, key_path=""):
        if isinstance(value, dict):
            user_details = value.get("user_details")
            if isinstance(user_details, list):
                for detail in user_details:
                    if not isinstance(detail, dict):
                        continue
                    total = 0
                    found_token_field = False
                    for token_key in ["subscriptionTokens", "paidTokens", "rolloverTokens"]:
                        number = as_number(detail.get(token_key))
                        if number is not None:
                            total += number
                            found_token_field = True
                    if found_token_field:
                        candidates.append((10, f"{key_path}.user_details.tokens", total))

            for key, child in value.items():
                child_path = f"{key_path}.{key}" if key_path else str(key)
                key_lower = str(key).lower()
                if "credit" in key_lower and isinstance(child, (int, float)):
                    score = 1
                    if any(word in key_lower for word in ["balance", "remaining", "available", "current"]):
                        score += 3
                    if any(word in key_lower for word in ["cost", "used", "spent", "price"]):
                        score -= 2
                    candidates.append((score, child_path, child))
                elif "credit" in key_lower and isinstance(child, str):
                    number = as_number(child)
                    if number is not None:
                        candidates.append((1, child_path, number))
                walk(child, child_path)
        elif isinstance(value, list):
            for index, child in enumerate(value[:20]):
                walk(child, f"{key_path}[{index}]")

    walk(payload)
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][2]


def extract_access_token(payload):
    """Find Leonardo bearer access token in nested session/API payloads."""
    found = []

    def walk(value, key_path=""):
        if isinstance(value, dict):
            for key, child in value.items():
                child_path = f"{key_path}.{key}" if key_path else str(key)
                key_lower = str(key).lower()
                if key_lower in {"accesstoken", "access_token"} and isinstance(child, str) and len(child) > 80:
                    score = 5 if child.startswith("eyJ") else 1
                    found.append((score, child_path, child))
                walk(child, child_path)
        elif isinstance(value, list):
            for index, child in enumerate(value[:20]):
                walk(child, f"{key_path}[{index}]")

    walk(payload)
    if not found:
        return None
    found.sort(key=lambda item: item[0], reverse=True)
    return found[0][2]


def merge_captured_api_payload(captured, payload, source="API response"):
    """Merge bearer token and credit data from a Leonardo API response."""
    if not isinstance(payload, dict):
        return False

    changed = False

    token = extract_access_token(payload)
    if token and (not captured.get("access_token") or len(token) >= len(captured.get("access_token") or "")):
        captured["access_token"] = token
        captured["auth_mode"] = "bearer"
        logger.ok(f"Token from {source} ({len(token)} chars)")
        changed = True

    credits = extract_credit_balance(payload)
    if credits is not None:
        captured["credit_balance"] = credits
        captured["user_info"] = payload
        logger.ok(f"Credits from {source}: {credits}")
        changed = True
    elif "user" in payload or "email" in payload or "credit" in json.dumps(payload, default=str).lower():
        captured["user_info"] = payload

    return changed


def normalize_captured_auth(captured):
    """Promote Leonardo cookies into explicit auth fields for current Better Auth sessions."""
    all_cookies = captured.get("all_cookies") or []
    leonardo_cookies = captured.get("leonardo_cookies") or [
        c for c in all_cookies
        if "leonardo" in c.get("domain", "").lower()
        or "app.leonardo.ai" in c.get("domain", "").lower()
    ]

    if leonardo_cookies:
        captured["leonardo_cookies"] = leonardo_cookies
        captured["cookie_header"] = captured.get("cookie_header") or "; ".join(
            f"{c.get('name')}={c.get('value')}"
            for c in leonardo_cookies
            if c.get("name") and c.get("value")
        )

    for c in leonardo_cookies:
        name = c.get("name", "")
        name_lower = name.lower()
        if name == "__Secure-better-auth.session_token" or "session_token" in name_lower:
            captured["session_token"] = captured.get("session_token") or c.get("value")
            captured["session_cookie"] = captured.get("session_cookie") or c
            if not captured.get("access_token"):
                captured["auth_mode"] = "better_auth_cookie"
        elif not captured.get("session_cookie") and ("session" in name_lower or "auth" in name_lower):
            captured["session_cookie"] = c
            captured["auth_mode"] = captured.get("auth_mode") or "cookie_session"

    if captured.get("access_token"):
        captured["auth_mode"] = "bearer"
    elif has_captured_auth(captured):
        captured["auth_mode"] = captured.get("auth_mode") or "cookie_session"

    return captured


def build_server_auth_payload(captured):
    """Build payload expected by the current VPS /api/bearer/import endpoint."""
    normalize_captured_auth(captured)
    return {
        "bearer": captured.get("access_token") or "",
        "email": captured.get("email") or "",
        "credits": captured.get("credit_balance"),
    }


def load_accounts():
    """Load captured Leonardo accounts from the local registry."""
    if not ACCOUNTS_FILE.exists():
        return []
    try:
        data = json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data.get("accounts", [])
        if isinstance(data, list):
            return data
    except Exception as e:
        logger.warn(f"Could not read accounts registry: {e}")
    return []


def save_accounts(accounts):
    """Save the local account registry."""
    ACCOUNTS_FILE.write_text(
        json.dumps({"accounts": accounts}, indent=2, default=str),
        encoding="utf-8",
    )


def safe_account_filename(email):
    """Create a Windows-safe auth filename from an account email."""
    raw = (email or "unknown_account").strip().lower()
    safe = re.sub(r"[^a-z0-9._@+-]+", "_", raw)
    safe = safe.strip("._ ") or "unknown_account"
    return f"{safe}.json"


def generate_account_code():
    """Create a short sale/redeem code for an account."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    raw = base64.b32encode(os.urandom(10)).decode("ascii").rstrip("=")
    cleaned = "".join(ch for ch in raw if ch in alphabet)
    while len(cleaned) < 12:
        cleaned += alphabet[int.from_bytes(os.urandom(1), "big") % len(alphabet)]
    return f"LEO-{cleaned[:4]}-{cleaned[4:8]}-{cleaned[8:12]}"


def save_account_auth_file(record):
    """Write full auth JSON for one account into auth_accounts/<email>.json."""
    ACCOUNT_AUTH_DIR.mkdir(exist_ok=True)
    email = record.get("email") or "unknown_account"
    auth_path = ACCOUNT_AUTH_DIR / safe_account_filename(email)
    payload = dict(record)
    payload["auth_file"] = str(auth_path)
    auth_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return auth_path


def build_safe_account_export(record):
    """Build non-sensitive JSON for account server upload."""
    return {
        "code": record.get("account_code"),
        "name": record.get("display_name") or "Akun Leonardo",
        "email_hint": record.get("email_hint") or "",
        "credits": record.get("credit_balance"),
        "auth_mode": record.get("auth_mode"),
        "status": record.get("sale_status") or "available",
        "created_at": record.get("created_at"),
        "last_capture_at": record.get("last_capture_at"),
        "last_refresh_at": record.get("last_refresh_at"),
        "next_refresh_at": record.get("next_refresh_at"),
        "source": record.get("source") or "auto_create",
        "sensitive_fields_removed": True,
    }


def save_account_upload_file(record):
    """Write safe JSON for account server upload into account_uploads/."""
    ACCOUNT_UPLOAD_DIR.mkdir(exist_ok=True)
    code = record.get("account_code") or generate_account_code()
    record["account_code"] = code
    record["display_name"] = record.get("display_name") or "Akun Leonardo"
    record["sale_status"] = record.get("sale_status") or "available"
    upload_path = ACCOUNT_UPLOAD_DIR / f"{code}.json"
    payload = build_safe_account_export(record)
    upload_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return upload_path


def _account_key(captured):
    email = (captured.get("email") or "").strip().lower()
    if email:
        return f"email:{email}"
    session = captured.get("session_token") or captured.get("access_token") or ""
    if session:
        return f"session:{session[:24]}"
    cookie_header = captured.get("cookie_header") or ""
    return f"cookie:{cookie_header[:24]}"


def save_success_account(captured):
    """Store a successfully captured account with full cookies for future refresh."""
    normalize_captured_auth(captured)
    if not has_complete_leonardo_auth(captured):
        return None

    now = datetime.now()
    key = _account_key(captured)
    accounts = load_accounts()
    existing = next((a for a in accounts if a.get("id") == key), None)

    record = existing or {"id": key, "created_at": now.isoformat()}
    display_index = accounts.index(existing) + 1 if existing else len(accounts) + 1
    record.update({
        "email": captured.get("email") or record.get("email") or "N/A",
        "account_code": record.get("account_code") or generate_account_code(),
        "display_name": record.get("display_name") or f"Akun {display_index}",
        "sale_status": record.get("sale_status") or "available",
        "auth_mode": captured.get("auth_mode"),
        "access_token": captured.get("access_token"),
        "session_token": captured.get("session_token"),
        "session_cookie": captured.get("session_cookie"),
        "cookie_header": captured.get("cookie_header"),
        "all_cookies": captured.get("all_cookies") or [],
        "leonardo_cookies": captured.get("leonardo_cookies") or [],
        "localStorage": captured.get("localStorage") or {},
        "sessionStorage": captured.get("sessionStorage") or {},
        "credit_balance": captured.get("credit_balance") if captured.get("credit_balance") is not None else record.get("credit_balance"),
        "last_capture_at": captured.get("captured_at") or now.isoformat(),
        "last_refresh_at": record.get("last_refresh_at"),
        "next_refresh_at": record.get("next_refresh_at") or (now + timedelta(hours=2)).isoformat(),
        "refresh_count": record.get("refresh_count", 0),
        "status": "captured",
        "last_error": None,
        "source": captured.get("source") or "auto_create",
    })
    auth_path = save_account_auth_file(record)
    record["auth_file"] = str(auth_path)
    upload_path = save_account_upload_file(record)
    record["upload_file"] = str(upload_path)

    if existing:
        accounts[accounts.index(existing)] = record
    else:
        accounts.append(record)

    save_accounts(accounts)
    logger.ok(f"Account saved to registry: {record.get('email')}")
    logger.ok(f"Account auth JSON: {auth_path}")
    logger.ok(f"Account upload JSON: {upload_path}")
    return record


def _sanitize_playwright_cookies(cookies):
    allowed = {"name", "value", "domain", "path", "expires", "httpOnly", "secure", "sameSite"}
    sanitized = []
    for cookie in cookies or []:
        if not cookie.get("name") or cookie.get("value") is None:
            continue
        item = {k: v for k, v in cookie.items() if k in allowed and v is not None}
        item.setdefault("path", "/")
        if item.get("expires", -1) in (-1, None):
            item.pop("expires", None)
        sanitized.append(item)
    return sanitized


async def refresh_account_bearer(account, headless=True):
    """Use stored cookies to trigger Leonardo requests and refresh the bearer token when available."""
    account = dict(account)
    normalize_captured_auth(account)
    cookies = _sanitize_playwright_cookies(account.get("all_cookies") or account.get("leonardo_cookies") or [])
    if not cookies:
        raise RuntimeError("No cookies saved for this account")

    refreshed_token = None
    refreshed_credits = account.get("credit_balance")
    refreshed_user_info = account.get("user_info")
    now = datetime.now()

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--lang=en-US",
            ],
        )
        context = await browser.new_context(locale="en-US", viewport={"width": 1280, "height": 800})
        await context.add_cookies(cookies)
        page = await context.new_page()

        async def on_request(request):
            nonlocal refreshed_token
            auth_header = request.headers.get("authorization", "")
            if auth_header.startswith("Bearer ") and "leonardo" in request.url.lower():
                token = auth_header.replace("Bearer ", "")
                if len(token) > 40 and (not refreshed_token or len(token) >= len(refreshed_token)):
                    refreshed_token = token

        async def on_response(response):
            nonlocal refreshed_token, refreshed_credits, refreshed_user_info
            if "leonardo" not in response.url.lower():
                return
            try:
                body = await response.json()
            except Exception:
                return
            if not isinstance(body, dict):
                return
            temp = {
                "access_token": refreshed_token,
                "credit_balance": refreshed_credits,
                "user_info": refreshed_user_info,
            }
            merge_captured_api_payload(temp, body, "refresh response")
            refreshed_token = temp.get("access_token")
            refreshed_credits = temp.get("credit_balance")
            refreshed_user_info = temp.get("user_info")

        context.on("request", on_request)
        context.on("response", on_response)

        for url in [
            "https://app.leonardo.ai/",
            "https://app.leonardo.ai/ai-images",
            "https://app.leonardo.ai/image-generation",
        ]:
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(5)
            except Exception:
                pass

        temp_account = {
            "access_token": refreshed_token,
            "credit_balance": refreshed_credits,
            "user_info": refreshed_user_info,
        }
        await wait_for_leonardo_auth_details(page, temp_account, timeout=45)
        refreshed_token = temp_account.get("access_token")
        refreshed_credits = temp_account.get("credit_balance")
        refreshed_user_info = temp_account.get("user_info")

        new_cookies = await context.cookies()
        await browser.close()

    account["all_cookies"] = new_cookies or account.get("all_cookies") or []
    normalize_captured_auth(account)
    if refreshed_token:
        account["access_token"] = refreshed_token
        account["auth_mode"] = "bearer"
    if refreshed_credits is not None:
        account["credit_balance"] = refreshed_credits
    if refreshed_user_info:
        account["user_info"] = refreshed_user_info

    account["last_refresh_at"] = now.isoformat()
    account["next_refresh_at"] = (now + timedelta(hours=2)).isoformat()
    account["refresh_count"] = int(account.get("refresh_count") or 0) + 1
    account["status"] = "refreshed" if refreshed_token else "cookie_session"
    account["last_error"] = None if has_captured_auth(account) else "No auth after refresh"

    if has_captured_auth(account):
        await send_to_server(account)

    return account


async def refresh_due_accounts(headless=True, force=False):
    """Refresh accounts whose next refresh time has arrived."""
    accounts = load_accounts()
    if not accounts:
        return []

    now = datetime.now()
    updated = []
    changed = False

    for index, account in enumerate(accounts):
        due_text = account.get("next_refresh_at")
        due_at = None
        if due_text:
            try:
                due_at = datetime.fromisoformat(due_text)
            except Exception:
                due_at = None
        if not force and due_at and due_at > now:
            continue

        try:
            refreshed = await refresh_account_bearer(account, headless=headless)
            refreshed_path = save_account_auth_file(refreshed)
            refreshed["auth_file"] = str(refreshed_path)
            accounts[index] = refreshed
            updated.append(refreshed)
            changed = True
        except Exception as e:
            account["status"] = "refresh_failed"
            account["last_error"] = str(e)[:200]
            account["last_refresh_at"] = now.isoformat()
            account["next_refresh_at"] = (now + timedelta(minutes=15)).isoformat()
            accounts[index] = account
            updated.append(account)
            changed = True

    if changed:
        save_accounts(accounts)
    return updated


def _print_final_result_impl(captured):
    if console:
        console.print()
        token_status = "CAPTURED" if has_captured_auth(captured) else "NOT FOUND"
        auth_mode = captured.get("auth_mode") or ("bearer" if captured.get("access_token") else "cookie_session")
        token_len = len(captured.get("access_token", "")) if captured.get("access_token") else 0
        
        content = Text()
        content.append("┌─────────────────────────────────────────┐\n", style="bold cyan")
        content.append("│       AUTH CAPTURE RESULT               │\n", style="bold cyan")
        content.append("├─────────────────────────────────────────┤\n", style="bold cyan")
        content.append(f"│  Email:      {str(captured.get('email', 'N/A'))[:30]:<30} │\n", style="white")
        content.append(f"│  Auth:       {token_status:<30} │\n", style="green" if has_captured_auth(captured) else "red")
        content.append(f"│  Mode:       {str(auth_mode)[:30]:<30} │\n", style="white")
        if token_len:
            content.append(f"│  Token len:  {str(token_len) + ' chars':<30} │\n", style="white")
        content.append(f"│  Credits:    {str(captured.get('credit_balance', 'N/A')):<30} │\n", style="yellow")
        content.append(f"│  Cookies:    {str(len(captured.get('all_cookies', []))) + ' cookies':<30} │\n", style="white")
        content.append(f"│  User info:  {'Yes' if captured.get('user_info') else 'No':<30} │\n", style="white")
        content.append("└─────────────────────────────────────────┘", style="bold cyan")
        console.print(Align.center(content))
        console.print()
    else:
        print("\n=== AUTH CAPTURE RESULT ===")
        print(f"  Email:   {captured.get('email', 'N/A')}")
        print(f"  Auth:    {'Yes' if has_captured_auth(captured) else 'No'}")
        print(f"  Credits: {captured.get('credit_balance', 'N/A')}")


def show_interactive_menu():
    """Show interactive menu for choosing mode"""
    if not console:
        return "auto"
    
    console.print()
    menu = Text()
    menu.append("  ┌────────────────────────────────────────┐\n", style="bold yellow")
    menu.append("  │        PILIH MODE OPERASI              │\n", style="bold yellow")
    menu.append("  ├────────────────────────────────────────┤\n", style="bold yellow")
    menu.append("  │  [1] 🚀 Auto Create (Full Flow)        │\n", style="white")
    menu.append("  │  [2] 📸 Capture Only (Login Manual)    │\n", style="white")
    menu.append("  │  [3] 🔄 Auto Create (Headless)         │\n", style="white")
    menu.append("  │  [4] ❌ Exit                           │\n", style="white")
    menu.append("  └────────────────────────────────────────┘", style="bold yellow")
    console.print(menu)
    console.print()
    
    choice = Prompt.ask("[bold cyan]Pilihan[/bold cyan]", choices=["1", "2", "3", "4"], default="1")
    
    mode_map = {
        "1": "auto",
        "2": "capture",
        "3": "auto_headless",
        "4": "exit",
    }
    return mode_map.get(choice, "auto")

# ════════════════════════════════════════════════════════════
# MAIN AUTO CREATE FLOW
# ════════════════════════════════════════════════════════════

async def delay_ms(ms):
    await asyncio.sleep(ms / 1000)


def locator_for(page, selector):
    if selector.startswith("/") or selector.startswith("("):
        return page.locator(f"xpath={selector}")
    return page.locator(selector)


async def click_selector(page, selector, timeout=10000, nth=0):
    loc = locator_for(page, selector).nth(nth)
    await loc.wait_for(state="visible", timeout=timeout)
    await loc.click()
    return loc


async def click_workflow_selector(page, selector, timeout=5000, nth=0):
    loc = locator_for(page, selector)
    target_loc = loc.nth(nth)
    await target_loc.wait_for(state="attached", timeout=timeout)

    count = await loc.count()
    ordered_indexes = [nth] + [idx for idx in range(count) if idx != nth]
    for idx in ordered_indexes:
        item = loc.nth(idx)
        try:
            if await item.is_visible():
                await item.click(timeout=timeout)
                return item
        except Exception:
            continue

    handle = await target_loc.element_handle()
    if not handle:
        raise RuntimeError(f"Selector found but no element handle: {selector}")

    await page.evaluate(
        """(el) => {
            const target = el.closest('tr, [role="row"], .zA, .asa, button, a') || el;
            target.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, view: window }));
            target.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true, view: window }));
            target.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
            if (typeof target.click === 'function') target.click();
        }""",
        handle,
    )
    return target_loc


async def try_click_workflow_selector(page, selector, timeout=5000, nth=0):
    try:
        await click_workflow_selector(page, selector, timeout=timeout, nth=nth)
        return True
    except Exception as e:
        logger.warn(f"Optional click skipped for {selector}: {e}")
        return False


async def click_gmail_canva_row(page, expected_email=None, timeout=15000):
    rows = page.locator("tr.zA")
    await rows.first.wait_for(state="attached", timeout=timeout)

    row_count = await rows.count()
    selected_index = 0
    selected_text = ""

    for idx in range(row_count):
        row = rows.nth(idx)
        text = ((await row.text_content()) or "").strip()
        lower_text = text.lower()
        if expected_email and expected_email.lower() in lower_text:
            selected_index = idx
            selected_text = text
            break
        if "kode canva" in lower_text or "canva" in lower_text:
            selected_index = idx
            selected_text = text
            break
        if not selected_text:
            selected_text = text

    target = rows.nth(selected_index)
    logger.info(f"Clicking Gmail row tr.zA index {selected_index}")
    handle = await target.element_handle()
    if not handle:
        raise RuntimeError("Gmail row tr.zA found but no element handle")

    await page.evaluate(
        """(row) => {
            const target = row.querySelector('td.xY.a4W div[role="link"], td[role="gridcell"] div[role="link"]') || row;
            target.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, view: window }));
            target.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true, view: window }));
            target.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
            if (typeof target.click === 'function') target.click();
        }""",
        handle,
    )
    return selected_text


def _random_temp_username(prefix="leo"):
    suffix = "".join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(9))
    return f"{prefix}{suffix}"


def _extract_strings(value):
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        out = []
        for item in value.values():
            out.extend(_extract_strings(item))
        return out
    if isinstance(value, list):
        out = []
        for item in value:
            out.extend(_extract_strings(item))
        return out
    return [str(value)]


def extract_otp_from_temp_mail_response(payload):
    """Extract a 6-digit Canva OTP from TempMail mailbox payload."""
    emails = []
    if isinstance(payload, dict):
        raw_emails = payload.get("emails") or payload.get("data") or payload.get("messages") or []
        if isinstance(raw_emails, list):
            emails = raw_emails
    elif isinstance(payload, list):
        emails = payload

    def item_time(item):
        if not isinstance(item, dict):
            return ""
        for key in ("createdAt", "created_at", "receivedAt", "received_at", "date", "time", "timestamp"):
            value = item.get(key)
            if value:
                return str(value)
        return str(item.get("id") or item.get("_id") or "")

    def extract_canva_code(text):
        patterns = [
            r"kode\s+canva(?:\s+anda)?\s+(?:adalah|:)?\s*(\d{6})",
            r"masukkan\s+(\d{6})",
            r"(?:verification|security|login)\s+code\s+(?:is|:)?\s*(\d{6})",
            r"\b(\d{6})\b(?=[^\n\r]{0,80}(?:menit|minute|canva))",
        ]
        lower_text = text.lower()
        for pattern in patterns:
            match = re.search(pattern, lower_text, flags=re.IGNORECASE)
            if match:
                return match.group(1)
        return None

    search_items = sorted(emails, key=item_time, reverse=True) if emails else [payload]
    for item in search_items:
        text = "\n".join(_extract_strings(item))
        lower = text.lower()
        if "canva" not in lower and "kode" not in lower and "code" not in lower:
            continue
        otp = extract_canva_code(text)
        if otp:
            return otp, item

    all_text = "\n".join(_extract_strings(payload))
    otp = extract_canva_code(all_text)
    if otp:
        return otp, None
    return None, None


async def fetch_temp_mail_domains(client):
    response = await client.get(f"{TEMP_MAIL_BASE_URL}/api/domains")
    response.raise_for_status()
    data = response.json()
    domains = data.get("domains") if isinstance(data, dict) else data
    if not isinstance(domains, list):
        raise RuntimeError("TempMail domains response invalid")
    return domains


async def generate_temp_mail_email():
    """Generate a TempMail address through mail.digitalku.store REST API."""
    async with httpx.AsyncClient(timeout=30, verify=False) as client:
        domains = await fetch_temp_mail_domains(client)
        by_name = {str(domain.get("name")): domain for domain in domains if domain.get("name")}
        ordered = [by_name[name] for name in TEMP_MAIL_PREFERRED_DOMAINS if name in by_name]
        ordered.extend(
            domain for domain in domains
            if domain.get("status") == "active" and domain not in ordered and not domain.get("is_hidden")
        )

        if not ordered:
            raise RuntimeError("Tidak ada domain TempMail aktif")

        last_error = None
        for domain_info in ordered:
            domain = domain_info.get("name")
            zone_id = domain_info.get("id") or ""
            is_premium = bool(domain_info.get("is_premium"))
            voucher_candidates = TEMP_MAIL_VOUCHER_CODES if is_premium else [""]
            if not voucher_candidates:
                continue

            for voucher_code in voucher_candidates:
                username = _random_temp_username()
                email_domain = domain
                base_payload = {
                    "username": username,
                    "domain": domain,
                    "zoneId": zone_id,
                    "emailDomain": email_domain,
                }
                try:
                    check_res = await client.post(
                        f"{TEMP_MAIL_BASE_URL}/api/check-username",
                        json=base_payload,
                    )
                    if check_res.status_code == 200:
                        check_data = check_res.json()
                        if isinstance(check_data, dict) and check_data.get("available") is False:
                            logger.warn(f"TempMail username unavailable: {username}@{email_domain}")
                            continue

                    generate_payload = {
                        **base_payload,
                        "password": None,
                        "voucherCode": voucher_code,
                    }
                    generate_res = await client.post(
                        f"{TEMP_MAIL_BASE_URL}/api/generate",
                        json=generate_payload,
                    )
                    data = generate_res.json()
                    if generate_res.status_code == 200 and isinstance(data, dict) and data.get("success") and data.get("email"):
                        email = data["email"]
                        logger.ok(f"TempMail generated: {email}")
                        return {
                            "email": email,
                            "domain": domain,
                            "zone_id": zone_id,
                            "is_premium": is_premium,
                            "voucher_used": bool(voucher_code),
                            "raw": data,
                        }
                    last_error = data.get("error") if isinstance(data, dict) else str(data)
                    logger.warn(f"TempMail generate failed for {domain}: {last_error}")
                except Exception as e:
                    last_error = str(e)
                    logger.warn(f"TempMail generate skipped for {domain}: {e}")

        raise RuntimeError(f"TempMail generate failed: {last_error or 'no usable domain'}")


async def wait_for_temp_mail_otp(email, timeout=150, interval=5, since_timestamp=None):
    """Poll TempMail inbox until a Canva OTP is found.

    Args:
        since_timestamp: Epoch seconds. Only accept emails with timestamp >= this.
                         If None, accept all (legacy behavior).
    """
    deadline = time.time() + timeout
    last_payload = None

    # If since_timestamp set, purge old emails first so they don't get picked up
    if since_timestamp is not None:
        try:
            async with httpx.AsyncClient(timeout=30, verify=False) as purge_client:
                purge_resp = await purge_client.post(
                    f"{TEMP_MAIL_BASE_URL}/api/mailbox/fetch",
                    json={"email": email},
                )
                purge_data = purge_resp.json()
                old_emails = purge_data.get("emails") if isinstance(purge_data, dict) else None
                if isinstance(old_emails, list):
                    for old_email in old_emails:
                        if not isinstance(old_email, dict):
                            continue
                        email_ts = old_email.get("timestamp")
                        # timestamp is epoch ms; compare with since_timestamp (epoch s)
                        if email_ts and email_ts / 1000 < since_timestamp:
                            msg_id = old_email.get("id") or old_email.get("_id") or old_email.get("uid")
                            if msg_id:
                                try:
                                    await purge_client.post(
                                        f"{TEMP_MAIL_BASE_URL}/api/mailbox/delete",
                                        json={"email": email, "id": msg_id},
                                    )
                                except Exception:
                                    pass
                    logger.info(f"TempMail: purged old emails before {since_timestamp}")
        except Exception as e:
            logger.warn(f"TempMail: purge old emails skipped: {e}")

    async with httpx.AsyncClient(timeout=30, verify=False) as client:
        while time.time() < deadline:
            response = await client.post(
                f"{TEMP_MAIL_BASE_URL}/api/mailbox/fetch",
                json={"email": email},
            )
            data = response.json()
            last_payload = data

            # Filter emails by timestamp if since_timestamp is set
            if since_timestamp is not None and isinstance(data, dict):
                all_emails = data.get("emails") or data.get("data") or data.get("messages") or []
                if isinstance(all_emails, list):
                    filtered_emails = []
                    for email_item in all_emails:
                        if not isinstance(email_item, dict):
                            filtered_emails.append(email_item)
                            continue
                        email_ts_ms = email_item.get("timestamp")
                        if email_ts_ms and email_ts_ms / 1000 >= since_timestamp:
                            filtered_emails.append(email_item)
                        # else: skip old email
                    # Create filtered payload
                    data = {**data, "emails": filtered_emails}

            otp, message = extract_otp_from_temp_mail_response(data)
            if otp:
                await asyncio.sleep(4)
                try:
                    confirm_response = await client.post(
                        f"{TEMP_MAIL_BASE_URL}/api/mailbox/fetch",
                        json={"email": email},
                    )
                    confirm_data = confirm_response.json()
                    confirm_otp, confirm_message = extract_otp_from_temp_mail_response(confirm_data)
                    if confirm_otp and confirm_otp != otp:
                        logger.warn(f"TempMail OTP updated from {otp} to {confirm_otp}; using latest code")
                        otp = confirm_otp
                        data = confirm_data
                        message = confirm_message
                except Exception as e:
                    logger.warn(f"TempMail OTP confirm fetch skipped: {e}")

                message_id = None
                if isinstance(message, dict):
                    message_id = message.get("id") or message.get("_id") or message.get("uid")
                if message_id:
                    try:
                        await client.post(
                            f"{TEMP_MAIL_BASE_URL}/api/mailbox/delete",
                            json={"email": email, "id": message_id},
                        )
                    except Exception as e:
                        logger.warn(f"TempMail delete email skipped: {e}")
                return otp, data

            count = data.get("count") if isinstance(data, dict) else None
            logger.info(f"TempMail inbox belum ada OTP ({count if count is not None else 0} email), retry {interval}s...")
            await asyncio.sleep(interval)

    raise RuntimeError(f"OTP TempMail tidak masuk dalam {timeout}s. Last payload: {str(last_payload)[:200]}")


async def wait_for_leonardo_canva_authorization(browser, leo_page, timeout=180):
    """Wait for Canva authorization ("Izinkan") or Leonardo dashboard after SSO."""
    logger.info(f"Waiting up to {timeout}s for Canva authorization / Leonardo dashboard...")
    deadline = time.time() + timeout
    allow_selectors = [
        'button:has-text("Izinkan")',
        '[role="button"]:has-text("Izinkan")',
        'text="Izinkan"',
        'button:has-text("Allow")',
        '[role="button"]:has-text("Allow")',
        'button:has-text("Lanjutkan")',
        '[role="button"]:has-text("Lanjutkan")',
    ]

    while time.time() < deadline:
        for p_tab in list(browser.pages):
            try:
                url = p_tab.url
                if "leonardo.ai" in url and "login" not in url.lower() and "auth" not in url.lower():
                    await p_tab.bring_to_front()
                    logger.ok(f"Leonardo dashboard reached: {url}")
                    return p_tab

                for selector in allow_selectors:
                    loc = p_tab.locator(selector).first
                    if await loc.count() > 0:
                        try:
                            if await loc.is_visible():
                                await p_tab.bring_to_front()
                                logger.ok(f"Canva authorization element appeared: {selector}")
                                if selector.startswith("button") or selector.startswith("[role"):
                                    await loc.click(timeout=5000)
                                    logger.ok("Clicked Canva authorization button")
                                await delay_ms(5000)
                                return p_tab
                        except Exception:
                            continue
            except Exception:
                continue

        await asyncio.sleep(1)
        remaining = int(deadline - time.time())
        if remaining > 0 and remaining % 15 == 0:
            logger.info(f"  Still waiting for Izinkan/dashboard... ({remaining}s left)")

    logger.warn("Timed out waiting for Izinkan/dashboard; continuing with current Leonardo page")
    return leo_page


async def wait_for_leonardo_auth_details(page, captured, timeout=90):
    """Trigger Leonardo requests until bearer and credit are captured, without changing the account flow."""
    if not page or page.is_closed():
        return False

    logger.info(f"Waiting up to {timeout}s for Leonardo bearer + credits...")
    deadline = time.time() + timeout
    trigger_urls = [
        "https://app.leonardo.ai/",
        "https://app.leonardo.ai/ai-images",
        "https://app.leonardo.ai/image-generation",
    ]
    trigger_index = 0

    graphql_query = """
        query CurrentUserCredits {
          users {
            id
            username
            user_details {
              auth0Email
              subscriptionTokens
              paidTokens
              rolloverTokens
              apiCredit
              streamTokens
              subscriptionSource
              plan
              tokenRenewalDate
            }
          }
        }
    """

    while time.time() < deadline:
        if captured.get("access_token") and captured.get("credit_balance") is not None:
            return True

        try:
            if trigger_index < len(trigger_urls):
                await page.goto(trigger_urls[trigger_index], wait_until="domcontentloaded", timeout=25000)
                trigger_index += 1
                await asyncio.sleep(4)
        except Exception as e:
            logger.info(f"  Leonardo page trigger skipped: {e}")

        try:
            responses = await page.evaluate(
                """async ({token, query}) => {
                    const calls = [];
                    async function getJson(label, url, options = {}) {
                        try {
                            const response = await fetch(url, {
                                credentials: "include",
                                ...options,
                                headers: {
                                    "accept": "application/json",
                                    ...(options.headers || {})
                                }
                            });
                            const text = await response.text();
                            let body = null;
                            try {
                                body = text ? JSON.parse(text) : {};
                            } catch (e) {
                                body = { text: text.slice(0, 1000) };
                            }
                            calls.push({ label, status: response.status, url: response.url, body });
                        } catch (e) {
                            calls.push({ label, error: String(e) });
                        }
                    }

                    await getJson("auth-get-session", "/api/auth/get-session");
                    await getJson("auth-session", "/api/auth/session");

                    if (token) {
                        await getJson("graphql-credits", "https://api.leonardo.ai/v1/graphql", {
                            method: "POST",
                            headers: {
                                "content-type": "application/json",
                                "authorization": `Bearer ${token}`
                            },
                            body: JSON.stringify({
                                operationName: "CurrentUserCredits",
                                variables: {},
                                query
                            })
                        });
                    }

                    return calls;
                }""",
                {"token": captured.get("access_token"), "query": graphql_query},
            )
        except Exception as e:
            responses = []
            logger.info(f"  Leonardo API fetch trigger skipped: {e}")

        for item in responses or []:
            label = item.get("label", "API")
            body = item.get("body")
            merge_captured_api_payload(captured, body, label)

        await asyncio.sleep(3)

    return bool(captured.get("access_token") and captured.get("credit_balance") is not None)


async def wait_for_leonardo_credit_balance(page, captured, timeout=90, minimum_credit=8500):
    """Trigger Leonardo requests until the credit balance is known, without storing auth data."""
    if not page or page.is_closed():
        return False

    logger.info(f"Waiting up to {timeout}s for Leonardo credits >= {minimum_credit} without auth capture...")
    deadline = time.time() + timeout
    trigger_urls = [
        "https://app.leonardo.ai/",
        "https://app.leonardo.ai/ai-images",
        "https://app.leonardo.ai/image-generation",
    ]
    trigger_index = 0
    ephemeral_token = None

    graphql_query = """
        query CurrentUserCredits {
          users {
            id
            username
            user_details {
              auth0Email
              subscriptionTokens
              paidTokens
              rolloverTokens
              apiCredit
              streamTokens
              subscriptionSource
              plan
              tokenRenewalDate
            }
          }
        }
    """

    while time.time() < deadline:
        if captured.get("credit_balance") is not None:
            return True

        try:
            if trigger_index < len(trigger_urls):
                await page.goto(trigger_urls[trigger_index], wait_until="domcontentloaded", timeout=25000)
                trigger_index += 1
                await asyncio.sleep(4)
        except Exception as e:
            logger.info(f"  Leonardo credit trigger skipped: {e}")

        try:
            responses = await page.evaluate(
                """async ({token, query}) => {
                    const calls = [];
                    async function getJson(label, url, options = {}) {
                        try {
                            const response = await fetch(url, {
                                credentials: "include",
                                ...options,
                                headers: {
                                    "accept": "application/json",
                                    ...(options.headers || {})
                                }
                            });
                            const text = await response.text();
                            let body = null;
                            try {
                                body = text ? JSON.parse(text) : {};
                            } catch (e) {
                                body = { text: text.slice(0, 1000) };
                            }
                            calls.push({ label, status: response.status, url: response.url, body });
                        } catch (e) {
                            calls.push({ label, error: String(e) });
                        }
                    }

                    await getJson("auth-get-session", "/api/auth/get-session");
                    await getJson("auth-session", "/api/auth/session");

                    if (token) {
                        await getJson("graphql-credits", "https://api.leonardo.ai/v1/graphql", {
                            method: "POST",
                            headers: {
                                "content-type": "application/json",
                                "authorization": `Bearer ${token}`
                            },
                            body: JSON.stringify({
                                operationName: "CurrentUserCredits",
                                variables: {},
                                query
                            })
                        });
                    }

                    return calls;
                }""",
                {"token": ephemeral_token, "query": graphql_query},
            )
        except Exception as e:
            responses = []
            logger.info(f"  Leonardo credit fetch skipped: {e}")

        for item in responses or []:
            body = item.get("body")
            token = extract_access_token(body)
            if token and not ephemeral_token:
                ephemeral_token = token
                logger.info("Temporary bearer found for credit check only; not saving auth")

            credits = extract_credit_balance(body)
            if credits is not None:
                captured["credit_balance"] = credits
                logger.ok(f"Credit balance: {credits}")
                return True

        await asyncio.sleep(3)

    return captured.get("credit_balance") is not None


LEONARDO_GRAPHQL_URL = "https://api.leonardo.ai/v1/graphql"
LEONARDO_REST_GENERATIONS_URL = "https://cloud.leonardo.ai/api/rest/v1/generations"

LEONARDO_GENERATION_MODEL_ID = "aa77f04e-3eec-4034-9c07-d0f619684628"

# Model gpt-image-2 terbukti berhasil di test_gptimg.py
# Format: SDGenerationInput!, arg1, width/height 1024x1024, num_images=1
LEONARDO_GPT_IMAGE_MODEL = "gpt-image-2"


def _build_generation_graphql_payload(prompt):
    """Build a Generate GraphQL mutation payload menggunakan format yang TERBUKTI working
    di leonardo.azkazamdigital.com (server.py).

    Format: mutation Generate($request: CreateGenerationRequest!)
    - Model: flux-dev (default, ~1.5 credit)
    - width/height: 1024
    - quality: MEDIUM
    - quantity: 1
    - style_ids: 111dc692-d470-4eec-b791-3475abac4c46
    - prompt_enhance: AUTO
    """
    return {
        "operationName": "Generate",
        "variables": {
            "request": {
                "model": "flux-dev",
                "public": True,
                "parameters": {
                    "height": 1024,
                    "width": 1024,
                    "prompt_enhance": "AUTO",
                    "quality": "MEDIUM",
                    "quantity": 1,
                    "style_ids": ["111dc692-d470-4eec-b791-3475abac4c46"],
                    "prompt": prompt,
                },
            }
        },
        "query": "mutation Generate($request: CreateGenerationRequest!) {\n  generate(request: $request) {\n    apiCreditCost\n    generationId\n    __typename\n  }\n}",
    }


def _build_generation_rest_payload(prompt):
    """Build a REST generation payload fallback menggunakan gpt-image-2."""
    return {
        "prompt": prompt,
        "modelId": LEONARDO_GPT_IMAGE_MODEL,
        "num_images": 1,
        "width": 1024,
        "height": 1024,
    }


async def trigger_leonardo_generation_via_api(captured):
    """Generate 1x gambar via httpx langsung ke API Leonardo (tanpa browser).

    Menggunakan format yang terbukti berhasil di leonardo.azkazamdigital.com (server.py):
    flux-dev, 1024x1024, CreateGenerationRequest!, generate mutation.
    """
    token = captured.get("access_token")
    if not token:
        logger.warn("Bearer token belum tersedia, tidak bisa generate via API")
        return False

    prompt = f"simple color icon {int(time.time())}"
    logger.info("Menjalankan 1x generate gambar via API langsung (gpt-image-2 1024x1024)...")

    headers = {
        "accept": "*/*",
        "content-type": "application/json",
        "authorization": f"Bearer {token}",
        "origin": "https://app.leonardo.ai",
        "referer": "https://app.leonardo.ai/",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
        "x-leo-schema-version": "1.185.11",
        "sec-ch-ua-platform": '"Windows"',
    }

    graphql_payload = _build_generation_graphql_payload(prompt)

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(LEONARDO_GRAPHQL_URL, json=graphql_payload, headers=headers)
            body = resp.text
            logger.info(f"Response generate API: {resp.status_code} | {body[:300]}")

            if resp.status_code == 200:
                try:
                    data = resp.json()
                    gen_data = (data.get("data") or {}).get("generate")
                    errors = data.get("errors")
                    if gen_data and gen_data.get("generationId"):
                        logger.ok(f"Generate berhasil! generationId: {gen_data['generationId']}, credit cost: {gen_data.get('apiCreditCost', '?')}")
                        return True
                    elif errors:
                        logger.warn(f"Generate gagal (GraphQL errors): {errors[0].get('message', '')[:200]}")
                    else:
                        logger.warn(f"Generate response tidak ada generationId: {body[:300]}")
                except Exception:
                    logger.warn(f"Generate response bukan JSON valid: {body[:200]}")
            else:
                logger.warn(f"Generate gagal: HTTP {resp.status_code}")

            # Fallback: REST endpoint
            rest_payload = _build_generation_rest_payload(prompt)
            resp2 = await client.post(LEONARDO_REST_GENERATIONS_URL, json=rest_payload, headers=headers)
            logger.info(f"Response REST fallback: {resp2.status_code} | {resp2.text[:300]}")
            if resp2.status_code == 200:
                logger.ok("Generate via REST fallback berhasil!")
                return True

    except Exception as e:
        logger.warn(f"Generate via API gagal: {e}")

    return False


async def refresh_credit_via_api(captured):
    """Cek saldo credit Leonardo via httpx langsung (tanpa browser)."""
    token = captured.get("access_token")
    if not token:
        return

    headers = {
        "accept": "*/*",
        "content-type": "application/json",
        "authorization": f"Bearer {token}",
        "origin": "https://app.leonardo.ai",
        "referer": "https://app.leonardo.ai/",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
        "x-leo-schema-version": "1.185.11",
        "sec-ch-ua-platform": '"Windows"',
    }

    credit_query = {
        "operationName": "CurrentUserCredits",
        "variables": {},
        "query": """query CurrentUserCredits {
  users {
    id
    user_details {
      subscriptionTokens
      paidTokens
      rolloverTokens
      apiCredit
      streamTokens
    }
  }
}""",
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(LEONARDO_GRAPHQL_URL, json=credit_query, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                credits = extract_credit_balance(data)
                if credits is not None:
                    captured["credit_balance"] = credits
                    logger.ok(f"Saldo credit: {credits}")
                    return credits
                token_found = extract_access_token(data)
                if token_found:
                    captured["access_token"] = token_found
                    captured["auth_mode"] = "bearer"
    except Exception as e:
        logger.info(f"Cek credit via API gagal: {e}")

    return None


async def trigger_leonardo_generation_request(page, captured):
    """Generate 1x gambar Leonardo. Prioritas: API langsung (httpx), fallback: browser UI."""

    # Prioritas 1: Langsung via API httpx (terbukti berhasil di test_gptimg.py)
    if captured.get("access_token"):
        api_ok = await trigger_leonardo_generation_via_api(captured)
        if api_ok:
            return True

    # Fallback: Via browser UI (jika API gagal atau token belum ada)
    if not page or page.is_closed():
        return False

    prompt = f"simple color icon {int(time.time())}"
    logger.info("Fallback: generate via UI browser Leonardo...")

    try:
        await page.goto("https://app.leonardo.ai/image-generation", wait_until="domcontentloaded", timeout=25000)
        await asyncio.sleep(6)
        ui_result = await page.evaluate(
            """async ({prompt}) => {
                const fields = [
                    ...document.querySelectorAll('textarea'),
                    ...document.querySelectorAll('input[type="text"]'),
                    ...document.querySelectorAll('[contenteditable="true"]')
                ];
                const field = fields.find((el) => {
                    const rect = el.getBoundingClientRect();
                    return rect.width > 150 && rect.height > 20 && !el.disabled;
                });
                if (!field) return { ok: false, reason: "prompt field not found" };
                field.focus();
                if (field.isContentEditable) {
                    field.textContent = prompt;
                } else {
                    field.value = prompt;
                }
                field.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: prompt }));
                field.dispatchEvent(new Event("change", { bubbles: true }));
                await new Promise((resolve) => setTimeout(resolve, 1200));

                const buttons = [...document.querySelectorAll('button,[role="button"]')];
                const button = buttons.find((el) => {
                    const text = (el.innerText || el.textContent || "").trim().toLowerCase();
                    const rect = el.getBoundingClientRect();
                    const disabled = el.disabled || el.getAttribute("aria-disabled") === "true";
                    return rect.width > 60 && rect.height > 25 && !disabled
                        && (text.includes("generate") || text.includes("create") || text.includes("buat"));
                });
                if (!button) return { ok: false, reason: "generate button not found" };
                button.click();
                return { ok: true, button: (button.innerText || button.textContent || "").trim().slice(0, 80) };
            }""",
            {"prompt": prompt},
        )
        if isinstance(ui_result, dict) and ui_result.get("ok"):
            logger.ok(f"Tombol generate Leonardo berhasil diklik: {ui_result.get('button')}")
            return True
        logger.info(f"Generate via UI Leonardo dilewati: {ui_result}")
    except Exception as e:
        logger.info(f"Request generate via UI dilewati: {e}")

    return False


async def refresh_leonardo_credit_once(page, captured, ephemeral_token=None):
    """Cek credit Leonardo. Prioritas: httpx langsung, fallback: browser."""

    # Prioritas 1: API langsung via httpx (lebih cepat & reliable)
    token = captured.get("access_token") or ephemeral_token
    if token:
        credits = await refresh_credit_via_api(captured)
        if credits is not None:
            return token

    # Fallback: via browser page.evaluate
    if not page or page.is_closed():
        return ephemeral_token

    graphql_query = """
        query CurrentUserCredits {
          users {
            id
            user_details {
              subscriptionTokens
              paidTokens
              rolloverTokens
              apiCredit
              streamTokens
            }
          }
        }
    """

    try:
        responses = await page.evaluate(
            """async ({token, query}) => {
                const calls = [];
                async function getJson(label, url, options = {}) {
                    try {
                        const response = await fetch(url, {
                            credentials: "include",
                            ...options,
                            headers: {
                                "accept": "application/json",
                                ...(options.headers || {})
                            }
                        });
                        const text = await response.text();
                        let body = null;
                        try { body = text ? JSON.parse(text) : {}; }
                        catch (e) { body = { text: text.slice(0, 1000) }; }
                        calls.push({ label, status: response.status, url: response.url, body });
                    } catch (e) {
                        calls.push({ label, error: String(e) });
                    }
                }

                await getJson("auth-get-session", "/api/auth/get-session");
                await getJson("auth-session", "/api/auth/session");

                if (token) {
                    await getJson("graphql-credits", "https://api.leonardo.ai/v1/graphql", {
                        method: "POST",
                        headers: {
                            "content-type": "application/json",
                            "authorization": `Bearer ${token}`
                        },
                        body: JSON.stringify({ operationName: "CurrentUserCredits", variables: {}, query })
                    });
                }
                return calls;
            }""",
            {"token": ephemeral_token or captured.get("access_token"), "query": graphql_query},
        )
    except Exception as e:
        logger.info(f"Refresh credit via browser dilewati: {e}")
        return ephemeral_token

    for item in responses or []:
        body = item.get("body")
        token = extract_access_token(body)
        if token and not ephemeral_token:
            ephemeral_token = token
            if not captured.get("capture_skipped"):
                captured["access_token"] = captured.get("access_token") or token
                captured["auth_mode"] = "bearer"

        credits = extract_credit_balance(body)
        if credits is not None:
            captured["credit_balance"] = credits
            logger.ok(f"Saldo credit (browser): {credits}")

    return ephemeral_token


async def generate_via_browser_ui(page, prompt="pemandangan indah", timeout=30):
    """Generate image via Leonardo browser UI dengan selector spesifik.

    Selector:
    - Input prompt: #prompt-textarea
    - Tombol Generate: [aria-label="Generate"]

    Returns True jika prompt diisi + tombol Generate diklik.
    """
    if not page or page.is_closed():
        logger.warn("Page tertutup, tidak bisa generate via UI")
        return False

    try:
        logger.info(f"Navigasi ke Leonardo image-generation...")
        await page.goto("https://app.leonardo.ai/image-generation", wait_until="domcontentloaded", timeout=25000)
        await asyncio.sleep(5)

        # === INPUT PROMPT ===
        logger.info(f"Mencari selector #prompt-textarea...")
        prompt_selector = "#prompt-textarea"
        try:
            prompt_loc = page.locator(prompt_selector).first
            await prompt_loc.wait_for(state="visible", timeout=15000)
            logger.ok(f"Selector #prompt-textarea ditemukan")

            # Click + clear + type
            await prompt_loc.click()
            await asyncio.sleep(0.5)
            await prompt_loc.fill("")
            await asyncio.sleep(0.3)
            await prompt_loc.type(prompt, delay=30)
            await asyncio.sleep(1)
            logger.ok(f"Prompt diisi: '{prompt}'")
        except Exception as e:
            logger.warn(f"Selector #prompt-textarea tidak ditemukan: {e}")
            # Fallback: cari textarea visible lain
            try:
                fallback = page.locator("textarea").first
                await fallback.wait_for(state="visible", timeout=5000)
                await fallback.click()
                await fallback.fill("")
                await fallback.type(prompt, delay=30)
                await asyncio.sleep(1)
                logger.ok(f"Prompt diisi via fallback textarea: '{prompt}'")
            except Exception as e2:
                logger.error(f"Fallback textarea juga gagal: {e2}")
                return False

        # === KLIK GENERATE ===
        logger.info(f"Mencari tombol [aria-label='Generate']...")
        generate_selector = '[aria-label="Generate"]'
        try:
            gen_btn = page.locator(generate_selector).first
            await gen_btn.wait_for(state="visible", timeout=10000)

            # Cek disabled
            is_disabled = await gen_btn.get_attribute("disabled")
            aria_disabled = await gen_btn.get_attribute("aria-disabled")
            if is_disabled is not None or aria_disabled == "true":
                logger.warn(f"Tombol Generate disabled, tunggu 3s lalu retry...")
                await asyncio.sleep(3)
                # Coba klik pakai force
                try:
                    await gen_btn.click(force=True, timeout=5000)
                    logger.ok("Tombol Generate diklik (force)")
                    await asyncio.sleep(3)
                    return True
                except Exception:
                    logger.error("Tombol Generate masih disabled")
                    return False

            await gen_btn.click(timeout=5000)
            logger.ok("Tombol Generate diklik!")
            await asyncio.sleep(3)
            return True

        except Exception as e:
            logger.warn(f"Selector [aria-label='Generate'] tidak ditemukan: {e}")
            # Fallback: cari button dengan text "Generate"
            try:
                buttons = page.locator('button, [role="button"]')
                count = await buttons.count()
                for i in range(count):
                    btn = buttons.nth(i)
                    text = (await btn.inner_text() or "").strip().lower()
                    if "generate" in text or "buat" in text:
                        rect = await btn.bounding_box()
                        if rect and rect["width"] > 60 and rect["height"] > 25:
                            await btn.click(timeout=5000)
                            logger.ok(f"Tombol Generate diklik via fallback text: '{text}'")
                            await asyncio.sleep(3)
                            return True
                logger.error("Tombol Generate tidak ditemukan di semua fallback")
                return False
            except Exception as e2:
                logger.error(f"Fallback button text juga gagal: {e2}")
                return False

    except Exception as e:
        logger.error(f"Generate via browser UI gagal: {type(e).__name__}: {e}")
        return False


async def ensure_leonardo_credit_spent(page, captured, full_credit=8500, timeout=120):
    """Generate 1x gambar lalu tunggu credit berkurang. Pakai API langsung."""
    if has_credit_spend_verified(captured, full_credit=full_credit):
        captured["credit_spend_verified"] = True
        logger.ok(f"Credit sudah berkurang: {captured.get('credit_balance')}")
        return True

    logger.warn(f"Credit masih full ({captured.get('credit_balance')}); menjalankan generate via BROWSER UI...")
    ui_ok = await generate_via_browser_ui(page, prompt="pemandangan indah")
    if not ui_ok:
        logger.warn("Generate via browser UI gagal, fallback ke API...")
        await trigger_leonardo_generation_request(page, captured)

    # Tunggu credit berkurang dengan interval lebih cepat
    deadline = time.time() + timeout
    retry_interval = 15  # retry generate setiap 15s
    last_retry = time.time()
    while time.time() < deadline:
        # Cek credit via API langsung (lebih cepat dari browser)
        await refresh_credit_via_api(captured)

        if has_credit_spend_verified(captured, full_credit=full_credit):
            captured["credit_spend_verified"] = True
            logger.ok(f"Credit berkurang, export diizinkan: {captured.get('credit_balance')}")
            return True

        if time.time() - last_retry >= retry_interval:
            logger.info(f"Credit belum berkurang ({captured.get('credit_balance')}), retry generate via browser UI...")
            ui_ok = await generate_via_browser_ui(page, prompt="pemandangan indah")
            if not ui_ok:
                logger.info("Retry via API fallback...")
                await trigger_leonardo_generation_request(page, captured)
            last_retry = time.time()
        else:
            logger.info(f"Credit belum berkurang ({captured.get('credit_balance')}), tunggu 5s...")
        await asyncio.sleep(5)
        await asyncio.sleep(3)  # tunggu 3s (bukan 5s)

    captured["credit_spend_verified"] = False
    logger.warn(f"Credit belum berkurang dari {full_credit}; export dibatalkan")
    return False


async def visible_locator(page, selectors, timeout=10000):
    last_error = None
    for selector in selectors:
        try:
            loc = locator_for(page, selector).first
            await loc.wait_for(state="visible", timeout=timeout)
            return loc, selector
        except Exception as e:
            last_error = e
    raise last_error or RuntimeError("No selector matched")


async def delete_oldest_relay_mask(page):
    """Run the Firefox Relay delete flow with selectors from the saved workflow."""
    await click_selector(page, 'svg[aria-label="Show mask details"]', timeout=5000)
    await delay_ms(2000)

    await click_workflow_selector(
        page,
        'button[class="AliasDeletionButtonPermanent-module-scss-module__WujWwG__deletion-button"]',
        timeout=5000,
    )

    await delay_ms(2000)
    try:
        await click_workflow_selector(page, "/html/body/div[5]/div/div/div[3]/div/button[2]", timeout=5000, nth=0)
    except Exception as e:
        logger.warn(f"Relay confirm XPath failed, clicking overlay confirm fallback: {e}")
        overlay_buttons = page.locator('div[data-overlay-container="true"] button')
        button_count = await overlay_buttons.count()
        if button_count < 1:
            raise
        await click_workflow_selector(
            page,
            'div[data-overlay-container="true"] button',
            timeout=5000,
            nth=button_count - 1,
        )

    try:
        await page.locator('div[class*="underlay"]').first.wait_for(state="detached", timeout=5000)
    except Exception:
        pass

    await delay_ms(2000)
    return True


async def remove_canva_cookies(browser):
    try:
        await browser.clear_cookies(domain="www.canva.com", path="/id_id/")
    except Exception as e:
        logger.info(f"Failed clear_cookies for www.canva.com/id_id/: {e}")

    for domain in ["canva.com", ".canva.com", "www.canva.com"]:
        try:
            await browser.clear_cookies(domain=domain)
        except Exception as e:
            logger.info(f"Failed clear_cookies for {domain}: {e}")


async def reset_canva_session(browser):
    """Clear Canva cookies and browser storage before starting a fresh signup."""
    logger.info("Resetting Canva session before starting flow...")
    await remove_canva_cookies(browser)

    reset_page = None
    try:
        reset_page = await browser.new_page()

        for origin in ["https://www.canva.com", "https://canva.com"]:
            try:
                cdp = await browser.new_cdp_session(reset_page)
                await cdp.send(
                    "Storage.clearDataForOrigin",
                    {
                        "origin": origin,
                        "storageTypes": "cookies,local_storage,session_storage,indexeddb,cache_storage,service_workers,websql",
                    },
                )
                await cdp.detach()
                logger.info(f"Cleared Canva storage origin: {origin}")
            except Exception as e:
                logger.info(f"CDP clear storage skipped for {origin}: {e}")

        try:
            await reset_page.goto(CANVA_URL, wait_until="domcontentloaded", timeout=20000)
            await reset_page.evaluate(
                """() => {
                    try { localStorage.clear(); } catch (e) {}
                    try { sessionStorage.clear(); } catch (e) {}
                    try {
                        if (window.indexedDB && indexedDB.databases) {
                            indexedDB.databases().then((dbs) => {
                                for (const db of dbs) {
                                    if (db && db.name) indexedDB.deleteDatabase(db.name);
                                }
                            });
                        }
                    } catch (e) {}
                }"""
            )
        except Exception as e:
            logger.info(f"Canva page storage clear skipped: {e}")
    finally:
        if reset_page:
            try:
                await reset_page.close()
            except Exception:
                pass

    logger.ok("Canva cookies/storage reset done")


async def remove_leonardo_cookies(browser):
    """Clear Leonardo cookies from the persistent browser context."""
    for domain in ["leonardo.ai", ".leonardo.ai", "app.leonardo.ai", "api.leonardo.ai"]:
        try:
            await browser.clear_cookies(domain=domain)
        except Exception as e:
            logger.info(f"Failed clear_cookies for {domain}: {e}")


async def clear_startup_browser_data(browser):
    """Clear all browser cookies/cache once without visiting Canva or Leonardo."""
    logger.info("Clearing browser cookies/cache once before starting flow...")
    try:
        await browser.clear_cookies()
        logger.ok("All browser cookies cleared")
    except Exception as e:
        logger.warn(f"Failed to clear browser cookies: {e}")

    page = None
    created_page = False
    try:
        if browser.pages:
            page = browser.pages[0]
        else:
            page = await browser.new_page()
            created_page = True
        cdp = await browser.new_cdp_session(page)
        for command in ["Network.clearBrowserCache", "Network.clearBrowserCookies"]:
            try:
                await cdp.send(command)
                logger.info(f"CDP {command} done")
            except Exception as e:
                logger.info(f"CDP {command} skipped: {e}")
        await cdp.detach()
    except Exception as e:
        logger.warn(f"Browser cache clear skipped: {e}")
    finally:
        if created_page and page:
            try:
                await page.close()
            except Exception:
                pass


async def reset_leonardo_session(browser):
    """Clear Leonardo cookies and browser storage before starting a fresh login."""
    logger.info("Resetting Leonardo session before starting flow...")
    await remove_leonardo_cookies(browser)

    reset_page = None
    try:
        reset_page = await browser.new_page()

        for origin in ["https://app.leonardo.ai", "https://leonardo.ai", "https://api.leonardo.ai"]:
            try:
                cdp = await browser.new_cdp_session(reset_page)
                await cdp.send(
                    "Storage.clearDataForOrigin",
                    {
                        "origin": origin,
                        "storageTypes": "cookies,local_storage,session_storage,indexeddb,cache_storage,service_workers,websql",
                    },
                )
                await cdp.detach()
                logger.info(f"Cleared Leonardo storage origin: {origin}")
            except Exception as e:
                logger.info(f"CDP clear storage skipped for {origin}: {e}")

        try:
            await reset_page.goto("https://app.leonardo.ai/", wait_until="domcontentloaded", timeout=20000)
            await reset_page.evaluate(
                """() => {
                    try { localStorage.clear(); } catch (e) {}
                    try { sessionStorage.clear(); } catch (e) {}
                    try {
                        if (window.indexedDB && indexedDB.databases) {
                            indexedDB.databases().then((dbs) => {
                                for (const db of dbs) {
                                    if (db && db.name) indexedDB.deleteDatabase(db.name);
                                }
                            });
                        }
                    } catch (e) {}
                }"""
            )
        except Exception as e:
            logger.info(f"Leonardo page storage clear skipped: {e}")
    finally:
        if reset_page:
            try:
                await reset_page.close()
            except Exception:
                pass

    logger.ok("Leonardo cookies/storage reset done")


async def auto_create_account(
    headless=False,
    relay_email=None,
    gmail_logged_in=True,
    send_bearer_to_vps=True,
    upload_account_json=False,
    account_server_url=None,
    google_sheet_webhook_url=None,
    capture_auth=True,
    browser_profile_dir=None,
    worker_id=None,
):
    """
    Full automated flow:
    1. TempMail API → generate email
    2. Canva signup with temp email
    3. TempMail API → OTP
    4. Canva OTP verify
    5. Accept team invite
    6. Leonardo login via Canva SSO
    7. Capture auth or check credit only
    """
    results = []
    captured = {
        "access_token": None,
        "refresh_token": None,
        "session_token": None,
        "session_cookie": None,
        "auth_mode": None,
        "cookie_header": None,
        "all_cookies": [],
        "leonardo_cookies": [],
        "localStorage": {},
        "sessionStorage": {},
        "user_info": None,
        "email": None,
        "credit_balance": None,
        "canva_tokens": None,
        "canva_password": None,
        "etteum_imported": False,
        "etteum_account_id": None,
    }

    print_banner()

    async with async_playwright() as p:
        # Launch Chromium dengan persistent context
        profile_dir = Path(browser_profile_dir) if browser_profile_dir else BROWSER_DATA
        profile_dir.mkdir(parents=True, exist_ok=True)
        clear_browser_profile_files(profile_dir)
        worker_label = f" worker {worker_id}" if worker_id is not None else ""
        logger.info(f"Launching browser{worker_label} (Chromium, persistent context): {profile_dir}")
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=headless,
            viewport={"width": 1280, "height": 800},
            locale="en-US",
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--lang=en-US",
            ],
        )

        page = browser.pages[0] if browser.pages else await browser.new_page()

        if capture_auth:
            # Network interception untuk capture token
            async def on_request(request):
                url = request.url
                auth_header = request.headers.get("authorization", "")
                if auth_header.startswith("Bearer ") and ("leonardo" in url.lower() or "api.leonardo" in url.lower()):
                    token = auth_header.replace("Bearer ", "")
                    if not captured["access_token"] or len(token) > len(captured["access_token"]):
                        captured["access_token"] = token
                        logger.ok(f"Bearer token captured ({len(token)} chars)")

            async def on_response(response):
                url = response.url
                if "leonardo" in url.lower():
                    try:
                        body = await response.json()
                        if isinstance(body, dict):
                            merge_captured_api_payload(captured, body, "response")
                    except:
                        pass

            browser.on("request", on_request)
            browser.on("response", on_response)
        else:
            logger.info("Capture auth dimatikan: token/cookies tidak akan disimpan")

        try:
            await clear_startup_browser_data(browser)
        except Exception as e:
            logger.warn(f"Browser startup data clear failed, continuing anyway: {e}")

        # ════════════════════════════════════════════════════════
        # STEP 1: TempMail API → Generate email
        # ════════════════════════════════════════════════════════
        logger.step(1, "TempMail API — Generate Email")
        print_step_header(1, "TempMail API — Generate Email")

        if relay_email:
            # Skip temp mail, pakai email yang sudah ada
            captured["email"] = relay_email
            logger.ok(f"Using provided email: {relay_email}")
            results.append({"desc": "TempMail email", "status": "SKIP", "data": relay_email})
            registration_start_time = time.time()  # Set cutoff even for relay emails
        else:
            try:
                registration_start_time = time.time()
                logger.info(f"Registration started at {registration_start_time}")
                logger.info(f"Generating email via {TEMP_MAIL_BASE_URL}...")
                temp_mail = await generate_temp_mail_email()
                captured["email"] = temp_mail["email"]
                captured["temp_mail"] = temp_mail
                logger.ok(f"TempMail email: {captured['email']}")
                logger.info(
                    f"TempMail domain: {temp_mail.get('domain')} "
                    f"({'premium' if temp_mail.get('is_premium') else 'standard'})"
                )
                results.append({"desc": "TempMail email", "status": "OK", "data": captured["email"]})

            except Exception as e:
                logger.error(f"TempMail generate failed: {e}")
                results.append({"desc": "TempMail email", "status": "FAIL", "data": str(e)[:50]})
                # No email available — cannot continue
                logger.error("Tidak ada email! Masukkan email manual di field Email manual atau cek API TempMail.")
                raise RuntimeError("Email tidak tersedia. Isi field Email manual atau cek API TempMail.")

        # ════════════════════════════════════════════════════════
        # STEP 2: TempMail cleanup placeholder
        logger.step(2, "TempMail - Ready Inbox")
        print_step_header(2, "TempMail - Ready Inbox")

        logger.info("TempMail tidak perlu cleanup mask lama")
        results.append({"desc": "TempMail ready", "status": "OK", "data": captured.get("email")})

        # STEP 3: Canva Signup with temp email
        # ════════════════════════════════════════════════════════
        logger.step(3, "Canva Signup with Temp Email")
        print_step_header(3, "Canva Signup with Temp Email")

        canva_page = None
        try:
            logger.info(f"Opening {CANVA_URL}...")
            canva_page = page if not page.is_closed() else await browser.new_page()
            await canva_page.bring_to_front()
            await canva_page.goto(CANVA_URL, wait_until="domcontentloaded", timeout=30000)
            await delay_ms(3000)

            # Click signup link
            logger.info('Clicking Canva signup link: a[href="/id_id/signup/"]')
            await click_selector(canva_page, 'a[href="/id_id/signup/"]', timeout=5000)
            await delay_ms(3000)

            # Click email signup method
            logger.info('Clicking Canva email method: button[aria-label="Email"]')
            await click_selector(canva_page, 'button[aria-label="Email"]', timeout=5000)
            await delay_ms(3000)

            # Fill email field
            logger.info(f"Filling email: {captured['email']}...")
            email_input = canva_page.locator('input[inputmode="email"]')
            await email_input.wait_for(state="visible", timeout=5000)
            await email_input.fill(captured["email"])

            # Click submit
            logger.info("Submitting signup form...")
            await click_selector(canva_page, 'button[type="submit"]', timeout=5000)
            await delay_ms(2000)
            otp_input_after_first_submit = canva_page.locator('input[inputmode="numeric"]')
            try:
                await otp_input_after_first_submit.first.wait_for(state="visible", timeout=5000)
                otp_ready_after_first_submit = True
            except Exception:
                otp_ready_after_first_submit = False
            if not otp_ready_after_first_submit:
                logger.info("OTP input not visible yet, submitting signup form again...")
                await click_selector(canva_page, 'button[type="submit"]', timeout=5000)
            else:
                logger.info("OTP input appeared after first submit; skipping second submit")
            logger.ok("Signup form submitted — OTP should arrive in TempMail")
            await delay_ms(3000)
            # Generate password untuk Canva account (dipakai saat import ke Eteum)
            import secrets as _secrets
            captured["canva_password"] = f"Az{_secrets.token_urlsafe(12)}#1"
            results.append({"desc": "Canva signup", "status": "OK", "data": captured["email"]})

        except Exception as e:
            logger.error(f"Canva signup failed: {e}")
            results.append({"desc": "Canva signup", "status": "FAIL", "data": str(e)[:50]})

        # ════════════════════════════════════════════════════════
        # STEP 4: TempMail -> Get OTP
        # ════════════════════════════════════════════════════════
        logger.step(4, "TempMail - Get OTP from Canva")
        print_step_header(4, "TempMail - Get OTP from Canva")

        otp_code = None
        try:
            logger.info(f"Polling TempMail inbox: {captured.get('email')}")
            otp_code, otp_payload = await wait_for_temp_mail_otp(captured["email"], timeout=150, interval=5, since_timestamp=registration_start_time)
            logger.ok(f"OTP code: {otp_code}")
            captured["temp_mail_last_inbox"] = otp_payload
            results.append({"desc": "TempMail OTP", "status": "OK", "data": otp_code})

        except Exception as e:
            logger.error(f"TempMail OTP failed: {e}")
            results.append({"desc": "TempMail OTP", "status": "FAIL", "data": str(e)[:50]})
            logger.error("OTP gagal diambil dari TempMail. Cek domain email atau ulang dengan domain lain.")
            raise RuntimeError("OTP gagal dari TempMail.")

        # ════════════════════════════════════════════════════════
        # STEP 5: Canva OTP Verification
        # ════════════════════════════════════════════════════════
        logger.step(5, "Canva OTP Verification")
        print_step_header(5, "Canva OTP Verification")

        try:
            # Switch back to Canva tab
            logger.info("Switching to Canva tab...")
            if canva_page is None or canva_page.is_closed():
                for p_tab in browser.pages:
                    if "canva.com" in p_tab.url:
                        canva_page = p_tab
                        break
            if canva_page is None or canva_page.is_closed():
                raise RuntimeError("Canva tab not available for OTP input")
            await canva_page.bring_to_front()

            # Fill OTP input
            logger.info(f"Entering OTP: {otp_code}...")
            otp_input = canva_page.locator('input[inputmode="numeric"]')
            await otp_input.wait_for(state="attached", timeout=5000)
            await otp_input.fill(otp_code)
            await delay_ms(5000)

            # Click submit
            logger.info("Submitting OTP...")
            await click_selector(canva_page, 'button[type="submit"]', timeout=5000)
            logger.ok("OTP submitted — Canva account created!")
            await delay_ms(10000)
            results.append({"desc": "Canva OTP verify", "status": "OK", "data": otp_code})

        except Exception as e:
            logger.error(f"Canva OTP verification failed: {e}")
            results.append({"desc": "Canva OTP verify", "status": "FAIL", "data": str(e)[:50]})

        # ════════════════════════════════════════════════════════
        # STEP 6: Accept Canva Team Invite
        # ════════════════════════════════════════════════════════
        logger.step(6, "Accept Canva Team Invite")
        print_step_header(6, "Accept Canva Team Invite")

        try:
            logger.info(f"Opening team invite URL...")
            if canva_page is None or canva_page.is_closed():
                canva_page = await browser.new_page()
            invite_page = canva_page
            await invite_page.bring_to_front()
            await invite_page.goto(CANVA_INVITE_URL, wait_until="domcontentloaded", timeout=30000)
            await delay_ms(10000)

            # Look for accept button
            logger.info("Looking for accept button...")
            # Try multiple selectors
            accept_selectors = []
            
            accepted = True
            for sel in accept_selectors:
                try:
                    btn = invite_page.locator(sel).first
                    if await btn.is_visible():
                        await btn.click()
                        logger.ok(f"Clicked accept button ({sel})")
                        accepted = True
                        break
                except:
                    continue

            if not accepted:
                logger.warn("No accept button found — may have auto-joined")
            
            logger.ok("Team invite processed")
            results.append({"desc": "Canva team invite", "status": "OK" if accepted else "PARTIAL", "data": CANVA_INVITE_TOKEN})

        except Exception as e:
            logger.error(f"Team invite failed: {e}")
            results.append({"desc": "Canva team invite", "status": "FAIL", "data": str(e)[:50]})

        # ════════════════════════════════════════════════════════
        # STEP 7: Leonardo Login via Canva SSO
        # ════════════════════════════════════════════════════════
        logger.step(7, "Leonardo Login via Canva SSO")
        print_step_header(7, "Leonardo Login via Canva SSO")

        try:
            logger.info(f"Opening {LEONARDO_LOGIN_URL}...")
            if canva_page is None or canva_page.is_closed():
                canva_page = await browser.new_page()
            leo_page = canva_page
            await leo_page.bring_to_front()
            await leo_page.goto(LEONARDO_LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
            await delay_ms(5000)

            # First, check if Canva button is directly visible
            canva_sso_btn = None
            canva_sso_selectors = []
            for sel in canva_sso_selectors:
                try:
                    btn = leo_page.locator(sel).first
                    if await btn.is_visible():
                        canva_sso_btn = btn
                        logger.info(f"Found Canva SSO button directly using: {sel}")
                        break
                except:
                    continue

            if not canva_sso_btn:
                logger.info("Canva button not visible, looking for reveal/options login button...")
                reveal_btn = None
                reveal_selectors = ['button[type="button"]']
                for sel in reveal_selectors:
                    try:
                        btn = leo_page.locator(sel).first
                        if await btn.is_visible():
                            reveal_btn = btn
                            logger.info(f"Found reveal/login button using: {sel}")
                            break
                    except:
                        continue
                
                if reveal_btn:
                    await reveal_btn.click()
                    logger.ok("Clicked reveal/login options button")
                    await delay_ms(5000)
                
                # Check for Canva SSO button again after clicking reveal
                for sel in canva_sso_selectors:
                    try:
                        btn = leo_page.locator(sel).first
                        if await btn.is_visible():
                            canva_sso_btn = btn
                            logger.info(f"Found Canva SSO button after reveal using: {sel}")
                            break
                    except:
                        continue

            if not canva_sso_btn:
                # Fallback: wait for the locator
                logger.warn("Canva SSO button not found/visible yet. Waiting for default text locator...")
                canva_sso_btn = leo_page.locator("button.hw3gKA").first
                await canva_sso_btn.wait_for(state="visible", timeout=5000)
            
            await canva_sso_btn.click()
            logger.ok("Clicked Canva SSO — redirecting...")
            
            await delay_ms(5000)
            leo_page = await wait_for_leonardo_canva_authorization(browser, leo_page, timeout=180)

            # Wait for Leonardo dashboard to load
            logger.info("Waiting for Leonardo dashboard...")
            for i in range(60):  # 60 seconds
                url = leo_page.url
                if "leonardo.ai" in url and "login" not in url.lower() and "auth" not in url.lower():
                    logger.ok(f"Leonardo dashboard reached! URL: {url}")
                    break
                await asyncio.sleep(1)
                if i % 10 == 0 and i > 0:
                    logger.info(f"  Still waiting... ({i}s)")

            # Navigate to trigger API calls
            logger.info("Triggering API calls...")
            for nav_url in [
                "https://app.leonardo.ai/",
                "https://app.leonardo.ai/ai-images",
                "https://app.leonardo.ai/image-generation",
            ]:
                try:
                    await leo_page.goto(nav_url, wait_until="domcontentloaded", timeout=20000)
                    await asyncio.sleep(3)
                except:
                    pass

            results.append({"desc": "Leonardo login", "status": "OK", "data": leo_page.url[:40]})

        except Exception as e:
            logger.error(f"Leonardo login failed: {e}")
            results.append({"desc": "Leonardo login", "status": "FAIL", "data": str(e)[:50]})

        # ════════════════════════════════════════════════════════
        # STEP 8: Capture Auth
        # ════════════════════════════════════════════════════════
        if not capture_auth:
            logger.step(8, "Check Leonardo Credits (No Capture)")
            print_step_header(8, "Check Leonardo Credits (No Capture)")
            captured["capture_skipped"] = True
            captured["captured_at"] = datetime.now().isoformat()
            captured["source"] = "auto_create_no_capture"

            try:
                credit_ok = await wait_for_leonardo_credit_balance(
                    leo_page,
                    captured,
                    timeout=90,
                    minimum_credit=8500,
                )
                if credit_ok:
                    results.append({"desc": "Leonardo credit", "status": "OK", "data": str(captured.get("credit_balance"))})
                else:
                    results.append({"desc": "Leonardo credit", "status": "PARTIAL", "data": str(captured.get("credit_balance"))})

                spend_ok = await ensure_leonardo_credit_spent(leo_page, captured, full_credit=8500, timeout=120)
                results.append({
                    "desc": "Leonardo credit spent",
                    "status": "OK" if spend_ok else "FAIL",
                    "data": str(captured.get("credit_balance")),
                })

                logger.info("Site-specific Canva cleanup skipped; startup browser clear already done")
            except Exception as e:
                logger.error(f"Credit check failed: {e}")
                results.append({"desc": "Leonardo credit", "status": "FAIL", "data": str(e)[:50]})

            try:
                await browser.close()
            except:
                pass

            print_summary(results)

            # Google Sheet dikirim via Eteum Pool (tidak perlu kirim terpisah)
            logger.info("Akun akan disimpan ke Eteum Pool + lokal PC")

            return captured, results

        logger.step(8, "Capture Auth")
        print_step_header(8, "Capture Auth")

        try:
            logger.info("Site-specific Canva cleanup skipped; startup browser clear already done")

            # Capture Canva cookies SEBELUM dihapus
            logger.info("Capturing Canva cookies for Eteum import...")
            all_browser_cookies = await browser.cookies()
            canva_tokens = extract_canva_cookies(all_browser_cookies)
            if has_canva_auth(canva_tokens):
                captured["canva_tokens"] = canva_tokens
                logger.ok(f"Canva cookies captured: caz={len(canva_tokens.get('caz',''))} chars, cb={canva_tokens.get('cb','')[:10]}...")
            else:
                logger.warn("Canva cookies tidak lengkap — Eteum import akan di-skip")

            # Capture cookies
            cookies = await browser.cookies()
            captured["all_cookies"] = cookies

            # Cari session cookie Leonardo
            leonardo_cookies = [
                c for c in cookies
                if "leonardo" in c.get("domain", "").lower()
                or "app.leonardo.ai" in c.get("domain", "").lower()
            ]
            captured["leonardo_cookies"] = leonardo_cookies
            captured["cookie_header"] = "; ".join(
                f"{c.get('name')}={c.get('value')}"
                for c in leonardo_cookies
                if c.get("name") and c.get("value")
            ) or None

            for c in leonardo_cookies:
                name = c.get("name", "")
                name_lower = name.lower()
                if "session" in name_lower or "auth" in name_lower:
                    logger.ok(f"Session cookie: {name}")

                if name == "__Secure-better-auth.session_token" or "session_token" in name_lower:
                    captured["session_token"] = captured["session_token"] or c.get("value")
                    captured["session_cookie"] = captured["session_cookie"] or c
                    if not captured.get("access_token"):
                        captured["auth_mode"] = "better_auth_cookie"
                elif not captured["session_cookie"] and ("session" in name_lower or "auth" in name_lower):
                    captured["session_cookie"] = c
                    captured["auth_mode"] = captured["auth_mode"] or "cookie_session"

            # Coba ambil token dari localStorage
            try:
                local_data = await leo_page.evaluate("""() => {
                    const data = {};
                    for (let i = 0; i < localStorage.length; i++) {
                        const key = localStorage.key(i);
                        data[key] = localStorage.getItem(key);
                    }
                    return data;
                }""")
                if local_data:
                    captured["localStorage"] = local_data
                    for key, val in local_data.items():
                        if "token" in key.lower() or "auth" in key.lower() or "session" in key.lower():
                            try:
                                parsed = json.loads(val)
                                if isinstance(parsed, dict):
                                    for k in ["access_token", "accessToken", "token"]:
                                        if k in parsed:
                                            captured["access_token"] = captured["access_token"] or parsed[k]
                                            logger.ok(f"Token from localStorage.{key}.{k}")
                                    for k in ["session", "session_token", "sessionToken"]:
                                        if k in parsed:
                                            captured["session_token"] = captured["session_token"] or parsed[k]
                                            captured["auth_mode"] = captured["auth_mode"] or "storage_session"
                            except:
                                if len(val) > 50 and not captured["access_token"]:
                                    captured["access_token"] = val
            except:
                pass

            # Coba ambil session dari sessionStorage juga
            try:
                session_data = await leo_page.evaluate("""() => {
                    const data = {};
                    for (let i = 0; i < sessionStorage.length; i++) {
                        const key = sessionStorage.key(i);
                        data[key] = sessionStorage.getItem(key);
                    }
                    return data;
                }""")
                if session_data:
                    captured["sessionStorage"] = session_data
                    for key, val in session_data.items():
                        if "token" in key.lower() or "auth" in key.lower() or "session" in key.lower():
                            try:
                                parsed = json.loads(val)
                                if isinstance(parsed, dict):
                                    for k in ["access_token", "accessToken", "token"]:
                                        if k in parsed:
                                            captured["access_token"] = captured["access_token"] or parsed[k]
                                            logger.ok(f"Token from sessionStorage.{key}.{k}")
                                    for k in ["session", "session_token", "sessionToken"]:
                                        if k in parsed:
                                            captured["session_token"] = captured["session_token"] or parsed[k]
                                            captured["auth_mode"] = captured["auth_mode"] or "storage_session"
                            except:
                                if len(val) > 50 and not captured["session_token"]:
                                    captured["session_token"] = val
                                    captured["auth_mode"] = captured["auth_mode"] or "storage_session"
            except:
                pass

            if not captured.get("access_token") or captured.get("credit_balance") is None:
                await wait_for_leonardo_auth_details(leo_page, captured, timeout=90)

            try:
                cookies = await browser.cookies()
                captured["all_cookies"] = cookies
                leonardo_cookies = [
                    c for c in cookies
                    if "leonardo" in c.get("domain", "").lower()
                    or "app.leonardo.ai" in c.get("domain", "").lower()
                ]
                captured["leonardo_cookies"] = leonardo_cookies
                captured["cookie_header"] = "; ".join(
                    f"{c.get('name')}={c.get('value')}"
                    for c in leonardo_cookies
                    if c.get("name") and c.get("value")
                ) or None
                normalize_captured_auth(captured)
            except Exception as e:
                logger.info(f"  Leonardo cookies recapture skipped: {e}")

            # Screenshot
            screenshot_path = SCRIPT_DIR / "leonardo_dashboard.png"
            try:
                await leo_page.screenshot(path=str(screenshot_path), timeout=10000)
                logger.info(f"Screenshot: {screenshot_path}")
            except Exception as e:
                logger.warn(f"Screenshot skipped: {e}")

            # Cek credit balance via API
            if False and captured["access_token"]:
                logger.info("Checking credit balance via API...")
                try:
                    import urllib.request
                    req = urllib.request.Request(
                        "https://api.leonardo.ai/v1/me",
                        headers={"Authorization": f"Bearer {captured['access_token']}"}
                    )
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        profile = json.loads(resp.read())
                        credits = profile.get("credit_balance") or profile.get("credits") or profile.get("user", {}).get("credit_balance")
                        captured["credit_balance"] = credits
                        if credits is not None:
                            if credits >= 850:
                                logger.ok(f"Credit balance: {credits} ✅ (≥ 850)")
                            else:
                                logger.warn(f"Credit balance: {credits} ⚠️ (< 850)")
                except Exception as e:
                    logger.warn(f"Could not check credits via API: {e}")
            if captured.get("credit_balance") is not None:
                logger.ok(f"Credit balance: {captured['credit_balance']}")
            else:
                logger.warn("Credit balance not found in Leonardo API responses")

            spend_ok = await ensure_leonardo_credit_spent(leo_page, captured, full_credit=8500, timeout=120)
            results.append({
                "desc": "Leonardo credit spent",
                "status": "OK" if spend_ok else "FAIL",
                "data": str(captured.get("credit_balance")),
            })

            if not captured["access_token"] and has_captured_auth(captured):
                logger.info("Bearer token not found, using Leonardo cookie session auth")

            logger.info("Final Canva cookie cleanup skipped; startup browser clear already done")

            normalize_captured_auth(captured)

            if not captured.get("access_token"):
                logger.warn("Bearer token not captured yet; account will not be counted as complete")
            if captured.get("credit_balance") is None:
                logger.warn("Credit balance not captured yet; account will not be counted as complete")

            auth_status = "OK" if has_complete_leonardo_auth(captured) else "PARTIAL"
            auth_label = captured.get("auth_mode") or "none"
            credit_label = captured.get("credit_balance") if captured.get("credit_balance") is not None else "None"
            results.append({"desc": "Capture auth", "status": auth_status, "data": f"Auth: {auth_label}, Credits: {credit_label}"})

        except Exception as e:
            logger.error(f"Capture failed: {e}")
            results.append({"desc": "Capture auth", "status": "FAIL", "data": str(e)[:50]})

        # Close browser
        try:
            await browser.close()
        except:
            pass

    # Save auth
    normalize_captured_auth(captured)
    captured["captured_at"] = datetime.now().isoformat()
    captured["source"] = "auto_create"
    AUTH_FILE.write_text(json.dumps(captured, indent=2, default=str))
    logger.ok(f"Auth saved: {AUTH_FILE}")
    saved_record = None
    export_ready = has_export_ready_account(captured, full_credit=8500)
    if export_ready:
        saved_record = save_success_account(captured)
    elif has_complete_leonardo_auth(captured):
        logger.warn("Auth complete, but credit has not decreased from 8500; account not exported/saved as success")
    elif has_captured_auth(captured):
        logger.warn("Partial Leonardo auth saved for debug only; not added to successful account list")

    # Print summary
    print_summary(results)

    # Send to server
    if export_ready and send_bearer_to_vps:
        logger.info("Sending bearer to VPS server...")
        sent = await send_to_server(captured)
        if sent:
            logger.ok("Auth sent to server! 🎉")
        else:
            logger.warn("Could not send to server - auth saved locally")
    elif export_ready:
        logger.info("Kirim bearer ke VPS dimatikan dari GUI")
    elif has_complete_leonardo_auth(captured):
        logger.warn("Skipping VPS send because credit has not decreased from 8500")
    elif has_captured_auth(captured):
        logger.warn("Skipping VPS send because bearer/credit capture is incomplete")
    else:
        logger.warn("No Leonardo auth captured - check screenshots + logs")

    if export_ready and upload_account_json and saved_record:
        await upload_account_json_to_server(saved_record, account_server_url or DEFAULT_ACCOUNT_SERVER_URL)

    # Google Sheet dikirim via Eteum Pool (tidak perlu kirim terpisah)
    # if export_ready and saved_record and google_sheet_webhook_url:
    #     await send_account_to_google_sheet(saved_record, google_sheet_webhook_url)

    # ══════════════════════════════════════════════════════════
    # ETTEUM POOL: Import akun Canva + simpan lokal PC
    # ══════════════════════════════════════════════════════════
    canva_tokens = captured.get("canva_tokens")
    if has_canva_auth(canva_tokens):
        logger.info("Importing Canva account to Eteum Pool...")
        etteum_result = await send_to_etteum(captured)
        if etteum_result:
            logger.ok(f"Canva account imported to Eteum! 🎉 (id={etteum_result.get('id', '?')})")
            captured["etteum_imported"] = True
            captured["etteum_account_id"] = etteum_result.get("id")
        else:
            logger.warn("Eteum import gagal — Canva account tetap disimpan lokal")
            captured["etteum_imported"] = False

        # Simpan ke lokal PC
        local_record = save_canva_account_local(captured)
        if local_record:
            logger.ok("Canva account saved to local PC (canva_accounts.json)")
    else:
        logger.warn("Canva cookies tidak lengkap — skip Eteum import + local save")

    return captured, results


def extract_canva_cookies(browser_cookies):
    """Extract Canva cookies dari browser context cookies.
    
    Mengembalikan dict dengan keys: caz, cb, cau, user_id, cl, cs, cdi, cid, cui, cul, cf_clearance, all_cookies
    """
    canva_cookies = {}
    all_cookies_dict = {}
    
    for c in browser_cookies or []:
        domain = c.get("domain", "").lower()
        name = c.get("name", "")
        value = c.get("value", "")
        
        if "canva.com" not in domain:
            continue
        
        all_cookies_dict[name] = value
        
        name_upper = name.upper()
        if name_upper == "CAZ" and not canva_cookies.get("caz"):
            canva_cookies["caz"] = value
        elif name_upper == "CB" and not canva_cookies.get("cb"):
            canva_cookies["cb"] = value
        elif name_upper == "CAU" and not canva_cookies.get("cau"):
            canva_cookies["cau"] = value
        elif name_upper == "CID" and not canva_cookies.get("cid"):
            canva_cookies["cid"] = value
        elif name_upper == "CUI" and not canva_cookies.get("cui"):
            canva_cookies["cui"] = value
        elif name_upper == "CUL" and not canva_cookies.get("cul"):
            canva_cookies["cul"] = value
        elif name_upper == "CDI" and not canva_cookies.get("cdi"):
            canva_cookies["cdi"] = value
        elif name_upper == "CS" and not canva_cookies.get("cs"):
            canva_cookies["cs"] = value
        elif name_upper == "CL" and not canva_cookies.get("cl"):
            canva_cookies["cl"] = value
        elif name == "cf_clearance" and not canva_cookies.get("cf_clearance"):
            canva_cookies["cf_clearance"] = value
    
    # user_id dari CAU (decode JWT) atau dari cookie CUI
    if not canva_cookies.get("user_id"):
        cau = canva_cookies.get("cau", "")
        if cau and cau.startswith("eyJ"):
            try:
                import base64 as b64
                parts = cau.split(".")
                if len(parts) >= 2:
                    payload = parts[1]
                    padding = 4 - len(payload) % 4
                    payload += "=" * padding
                    decoded = json.loads(b64.urlsafe_b64decode(payload))
                    canva_cookies["user_id"] = decoded.get("sub") or decoded.get("user_id") or ""
            except Exception:
                pass
    
    if all_cookies_dict:
        canva_cookies["all_cookies"] = json.dumps(all_cookies_dict)
    
    return canva_cookies


def has_canva_auth(canva_tokens):
    """Cek apakah Canva tokens cukup untuk import ke Eteum."""
    return bool(canva_tokens and canva_tokens.get("caz") and canva_tokens.get("cb"))


def save_canva_account_local(captured):
    """Simpan akun Canva ke canva_accounts.json di lokal PC."""
    canva_tokens = captured.get("canva_tokens")
    if not has_canva_auth(canva_tokens):
        return None
    
    now = datetime.now()
    email = captured.get("email") or "unknown"
    
    # Load existing
    accounts = []
    if CANVA_ACCOUNTS_FILE.exists():
        try:
            data = json.loads(CANVA_ACCOUNTS_FILE.read_text(encoding="utf-8"))
            accounts = data.get("accounts", []) if isinstance(data, dict) else data
        except Exception:
            pass
    
    # Cek existing
    existing = None
    for a in accounts:
        if a.get("email") == email:
            existing = a
            break
    
    record = existing or {"email": email, "created_at": now.isoformat()}
    record.update({
        "email": email,
        "provider": "canva",
        "canva_tokens": canva_tokens,
        "leonardo_access_token": captured.get("access_token"),
        "leonardo_credit_balance": captured.get("credit_balance"),
        "leonardo_auth_mode": captured.get("auth_mode"),
        "last_capture_at": captured.get("captured_at") or now.isoformat(),
        "updated_at": now.isoformat(),
        "status": "active",
        "etteum_imported": record.get("etteum_imported", False),
        "etteum_account_id": record.get("etteum_account_id"),
    })
    
    if existing:
        accounts[accounts.index(existing)] = record
    else:
        accounts.append(record)
    
    CANVA_ACCOUNTS_FILE.write_text(
        json.dumps({"accounts": accounts}, indent=2, default=str),
        encoding="utf-8",
    )
    logger.ok(f"Canva account saved locally: {CANVA_ACCOUNTS_FILE}")
    return record


async def send_to_etteum(captured):
    """Kirim akun Canva ke Eteum Pool via POST /api/accounts."""
    canva_tokens = captured.get("canva_tokens")
    if not has_canva_auth(canva_tokens):
        logger.warn("Canva cookies tidak lengkap (caz/cb missing), skip import ke Eteum")
        return None
    
    email = captured.get("email") or f"canva-{int(time.time())}@auto-create"
    password = captured.get("canva_password") or f"auto-{int(time.time())}"
    
    payload = {
        "provider": "canva",
        "email": email,
        "password": password,
        "tokens": canva_tokens,
        "status": "active",
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {ETTEUM_API_KEY}",
    }
    
    # Coba HTTP direct dulu, fallback HTTPS
    urls_to_try = [ETTEUM_API_URL]
    if ETTEUM_HTTPS_URL and ETTEUM_HTTPS_URL != ETTEUM_API_URL:
        urls_to_try.append(ETTEUM_HTTPS_URL)
    
    for url in urls_to_try:
        try:
            logger.info(f"POST {url} (provider=canva)...")
            async with httpx.AsyncClient(timeout=20, verify=False) as client:
                resp = await client.post(url, json=payload, headers=headers)
            
            if 200 <= resp.status_code < 300:
                result = resp.json()
                logger.ok(f"Eteum import OK: {result}")
                return result
            elif resp.status_code == 409:
                logger.warn(f"Eteum: account sudah ada (409): {email}")
                return {"updated": False, "existing": True, "email": email}
            else:
                logger.warn(f"Eteum import error {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            logger.warn(f"Eteum import gagal ({url}): {type(e).__name__}: {e}")
    
    return None


async def send_to_server(captured):
    """Send bearer token to the current VPS bearer import endpoint."""
    if not has_credit_spend_verified(captured, full_credit=8500):
        logger.warn("Bearer import dibatalkan: credit belum turun dari 8500")
        return False

    payload = build_server_auth_payload(captured)
    if not payload.get("bearer"):
        logger.warn("Bearer kosong, batal kirim ke VPS")
        return False

    logger.info(f"POST {SERVER_BEARER_IMPORT_URL}...")
    try:
        async with httpx.AsyncClient(timeout=20, verify=False) as client:
            resp = await client.post(
                SERVER_BEARER_IMPORT_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
        if 200 <= resp.status_code < 300:
            try:
                result = resp.json()
            except Exception:
                result = resp.text[:300]
            logger.ok(f"Bearer import: {result}")
            return True
        logger.warn(f"Bearer import error: {resp.status_code} {resp.text[:300]}")
    except Exception as e:
        logger.warn(f"Bearer import gagal: {type(e).__name__}: {e}")

    return False


# ════════════════════════════════════════════════════════════
async def upload_account_json_to_server(record, account_server_url):
    """Upload the safe account JSON payload to an account server endpoint."""
    if not account_server_url:
        logger.info("Server akun kosong, upload JSON akun dilewati")
        return False

    upload_path = Path(record.get("upload_file") or "")
    if not upload_path.exists():
        upload_path = save_account_upload_file(record)
        record["upload_file"] = str(upload_path)

    payload = build_safe_account_export(record)
    logger.info(f"POST account JSON to {account_server_url}...")

    try:
        async with httpx.AsyncClient(timeout=30, verify=False) as client:
            resp = await client.post(
                account_server_url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
        if 200 <= resp.status_code < 300:
            try:
                result = resp.json()
            except Exception:
                result = resp.text[:300]
            logger.ok(f"Account JSON uploaded: {result}")
            return True
        logger.warn(f"Account JSON upload error: {resp.status_code} {resp.text[:300]}")
    except Exception as e:
        logger.warn(f"Account JSON upload failed: {type(e).__name__}: {e}")

    return False


def build_google_sheet_payload(record):
    """Build the minimal row payload for a Google Apps Script webhook."""
    email = record.get("email") or ""
    mailbox_url = f"{TEMP_MAIL_BASE_URL}/mailbox.html?email={email}" if email else ""
    return {
        "email": f"Email {email}" if email else "Email",
        "akses_otp": f"Akses Otp {mailbox_url}" if mailbox_url else "Akses Otp",
    }


async def send_account_to_google_sheet(record, webhook_url):
    """Append a successful account to Google Sheet through Apps Script Web App."""
    webhook_url = (webhook_url or "").strip()
    if not webhook_url:
        return False
    if not has_credit_spend_verified(record, full_credit=8500):
        logger.warn("Google Sheet dibatalkan: credit belum turun dari 8500")
        return False

    payload = build_google_sheet_payload(record)
    logger.info(f"POST Google Sheet webhook: {webhook_url[:80]}...")
    try:
        async with httpx.AsyncClient(timeout=30, verify=False, follow_redirects=True) as client:
            resp = await client.post(
                webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
        if 200 <= resp.status_code < 300:
            logger.ok(f"Google Sheet updated: {resp.text[:200]}")
            return True
        logger.warn(f"Google Sheet webhook error: {resp.status_code} {resp.text[:300]}")
    except Exception as e:
        logger.warn(f"Google Sheet webhook failed: {type(e).__name__}: {e}")

    return False


# MAIN MENU
# ════════════════════════════════════════════════════════════

def _terminal_bool(prompt, default=False):
    if console:
        return Confirm.ask(prompt, default=default)
    suffix = "Y/n" if default else "y/N"
    value = input(f"{prompt} ({suffix}): ").strip().lower()
    if not value:
        return default
    return value in {"y", "yes", "ya", "1", "true"}


def _terminal_text(prompt, default=""):
    if console:
        return Prompt.ask(prompt, default=str(default or ""))
    value = input(f"{prompt} [{default}]: ").strip()
    return value if value else default


def _terminal_int(prompt, default=1):
    while True:
        value = _terminal_text(prompt, str(default))
        try:
            return max(1, int(value))
        except Exception:
            print("Masukkan angka yang valid.")


def collect_terminal_options(mode, settings):
    """Ask for the same feature options available in the desktop GUI."""
    settings = dict(settings or {})
    if mode == "capture":
        return {
            "target_accounts": 1,
            "parallel_browsers": 1,
            "relay_email": "",
            "capture_auth": True,
            "send_bearer_to_vps": settings.get("send_bearer_to_vps", True),
            "upload_account_json": settings.get("upload_account_json", False),
            "account_server_url": settings.get("account_server_url") or DEFAULT_ACCOUNT_SERVER_URL,
            "send_google_sheet": settings.get("send_google_sheet", False),
            "google_sheet_url": settings.get("google_sheet_url") or "",
        }

    relay_email = _terminal_text("Email manual opsional, kosongkan untuk TempMail", settings.get("relay_email") or "")
    target_accounts = _terminal_int("Target akun dibuat", settings.get("target_accounts") or 1)
    parallel_browsers = min(4, _terminal_int("Jumlah browser paralel, maksimal 4", settings.get("parallel_browsers") or 1))
    capture_auth = _terminal_bool("Capture auth/token + cookies?", bool(settings.get("capture_auth", True)))

    send_bearer_to_vps = False
    upload_account_json = False
    account_server_url = settings.get("account_server_url") or DEFAULT_ACCOUNT_SERVER_URL
    if capture_auth:
        send_bearer_to_vps = _terminal_bool("Kirim bearer ke VPS sekarang?", bool(settings.get("send_bearer_to_vps", True)))
        upload_account_json = _terminal_bool("Upload JSON akun aman ke server akun?", bool(settings.get("upload_account_json", False)))
        account_server_url = _terminal_text("Server akun upload URL", account_server_url)

    send_google_sheet = _terminal_bool("Kirim akun jadi ke Google Sheet?", bool(settings.get("send_google_sheet", False)))
    google_sheet_url = _terminal_text("Google Sheet Web App URL", settings.get("google_sheet_url") or DEFAULT_GOOGLE_SHEET_WEBHOOK_URL)

    return {
        "target_accounts": target_accounts,
        "parallel_browsers": parallel_browsers,
        "relay_email": relay_email,
        "capture_auth": capture_auth,
        "send_bearer_to_vps": send_bearer_to_vps,
        "upload_account_json": upload_account_json,
        "account_server_url": account_server_url,
        "send_google_sheet": send_google_sheet,
        "google_sheet_url": google_sheet_url,
    }


async def run_auto_batch(
    headless=False,
    relay_email=None,
    target_accounts=1,
    parallel_browsers=1,
    capture_auth=True,
    send_bearer_to_vps=True,
    upload_account_json=False,
    account_server_url=None,
    send_google_sheet=False,
    google_sheet_url=None,
):
    success_count = 0
    last_captured = None
    last_results = []
    target_accounts = max(1, int(target_accounts or 1))
    parallel_browsers = max(1, min(4, int(parallel_browsers or 1), target_accounts))
    queue = asyncio.Queue()
    lock = asyncio.Lock()

    for run_index in range(1, target_accounts + 1):
        queue.put_nowait(run_index)

    logger.info(f"Menjalankan batch dengan {parallel_browsers} browser paralel")

    async def worker(worker_id):
        nonlocal success_count, last_captured, last_results
        profile_dir = BROWSER_PARALLEL_DATA / f"worker_{worker_id}"
        while not queue.empty():
            try:
                run_index = queue.get_nowait()
            except asyncio.QueueEmpty:
                return

            current_relay_email = relay_email if run_index == 1 else None
            logger.step(1, f"Worker {worker_id}: account {run_index}/{target_accounts}")
            try:
                captured, results = await auto_create_account(
                    headless=headless,
                    relay_email=current_relay_email,
                    send_bearer_to_vps=send_bearer_to_vps if capture_auth else False,
                    upload_account_json=upload_account_json if capture_auth else False,
                    account_server_url=account_server_url,
                    google_sheet_webhook_url=google_sheet_url if send_google_sheet else None,
                    capture_auth=capture_auth,
                    browser_profile_dir=profile_dir,
                    worker_id=worker_id,
                )
            except Exception as e:
                logger.error(f"Worker {worker_id} account {run_index} failed: {type(e).__name__}: {e}")
                captured = {"email": current_relay_email, "credit_balance": None}
                results = [{"desc": f"Worker {worker_id} account {run_index}", "status": "FAIL", "data": str(e)[:50]}]

            account_ok = (
                has_export_ready_account(captured, full_credit=8500)
                if capture_auth
                else bool(captured.get("email") and has_credit_spend_verified(captured, full_credit=8500))
            )
            async with lock:
                last_captured = captured
                last_results = results
                if account_ok:
                    success_count += 1
                    logger.ok(f"Akun jadi: {success_count}/{target_accounts}")
                else:
                    logger.warn(f"Akun {run_index} belum memenuhi syarat selesai")
            queue.task_done()

    await asyncio.gather(*(worker(worker_id) for worker_id in range(1, parallel_browsers + 1)))

    logger.ok(f"Batch selesai. Total akun jadi: {success_count}/{target_accounts}")
    if last_captured is None:
        last_captured = {}
    last_captured["batch_success_count"] = success_count
    last_captured["batch_target_accounts"] = target_accounts
    last_captured["parallel_browsers"] = parallel_browsers
    return last_captured, last_results


def main():
    parser = argparse.ArgumentParser(description="Leonardo Auto Create Account + Auth Capture")
    parser.add_argument("--relay-email", help="Skip TempMail API, use provided email")
    parser.add_argument("--headless", action="store_true", help="Run headless (no browser window)")
    parser.add_argument("--capture-only", action="store_true", help="Only capture auth (skip account creation)")
    parser.add_argument("--no-menu", action="store_true", help="Skip interactive menu, run directly")
    parser.add_argument("--target-accounts", type=int, help="Jumlah akun yang dibuat")
    parser.add_argument("--parallel-browsers", type=int, help="Jumlah browser paralel, maksimal 4")
    parser.add_argument("--capture-auth", dest="capture_auth", action="store_true", default=None, help="Capture bearer/cookies")
    parser.add_argument("--no-capture-auth", dest="capture_auth", action="store_false", help="Hanya cek credit + kirim Google Sheet")
    parser.add_argument("--send-bearer-to-vps", dest="send_bearer_to_vps", action="store_true", default=None)
    parser.add_argument("--no-send-bearer-to-vps", dest="send_bearer_to_vps", action="store_false")
    parser.add_argument("--upload-account-json", dest="upload_account_json", action="store_true", default=None)
    parser.add_argument("--no-upload-account-json", dest="upload_account_json", action="store_false")
    parser.add_argument("--account-server-url", help="URL server upload JSON akun")
    parser.add_argument("--send-google-sheet", dest="send_google_sheet", action="store_true", default=None)
    parser.add_argument("--no-send-google-sheet", dest="send_google_sheet", action="store_false")
    parser.add_argument("--google-sheet-url", help="Google Apps Script Web App URL")
    args = parser.parse_args()
    settings = load_app_settings()

    # If CLI args provided, skip menu
    if args.capture_only:
        from leonardo_auth_capture import capture_auth
        asyncio.run(capture_auth())
        return

    cli_values = {
        "relay_email": args.relay_email if args.relay_email is not None else settings.get("relay_email", ""),
        "target_accounts": args.target_accounts if args.target_accounts is not None else settings.get("target_accounts", 1),
        "parallel_browsers": args.parallel_browsers if args.parallel_browsers is not None else settings.get("parallel_browsers", 1),
        "capture_auth": args.capture_auth if args.capture_auth is not None else settings.get("capture_auth", True),
        "send_bearer_to_vps": args.send_bearer_to_vps if args.send_bearer_to_vps is not None else settings.get("send_bearer_to_vps", True),
        "upload_account_json": args.upload_account_json if args.upload_account_json is not None else settings.get("upload_account_json", False),
        "account_server_url": args.account_server_url if args.account_server_url is not None else settings.get("account_server_url", DEFAULT_ACCOUNT_SERVER_URL),
        "send_google_sheet": args.send_google_sheet if args.send_google_sheet is not None else settings.get("send_google_sheet", False),
        "google_sheet_url": args.google_sheet_url if args.google_sheet_url is not None else settings.get("google_sheet_url", DEFAULT_GOOGLE_SHEET_WEBHOOK_URL),
    }
    if args.google_sheet_url:
        cli_values["send_google_sheet"] = True
    try:
        cli_values["parallel_browsers"] = max(1, min(4, int(cli_values.get("parallel_browsers") or 1)))
    except Exception:
        cli_values["parallel_browsers"] = 1
    if not cli_values["capture_auth"]:
        cli_values["send_bearer_to_vps"] = False
        cli_values["upload_account_json"] = False

    if args.relay_email or args.headless or args.no_menu or args.target_accounts is not None or args.parallel_browsers is not None:
        headless = bool(args.headless or settings.get("mode") == "auto_headless")
        save_app_settings({"mode": "auto_headless" if headless else "auto", **cli_values})
        captured, results = asyncio.run(run_auto_batch(
            headless=headless,
            relay_email=cli_values["relay_email"] or None,
            target_accounts=cli_values["target_accounts"],
            parallel_browsers=cli_values["parallel_browsers"],
            capture_auth=cli_values["capture_auth"],
            send_bearer_to_vps=cli_values["send_bearer_to_vps"],
            upload_account_json=cli_values["upload_account_json"],
            account_server_url=cli_values["account_server_url"],
            send_google_sheet=cli_values["send_google_sheet"],
            google_sheet_url=cli_values["google_sheet_url"],
        ))
        if captured:
            print_final_result(captured)
        return

    # Interactive menu
    print_banner()
    mode = show_interactive_menu()
    
    if mode == "exit":
        if console:
            console.print("\n[bold yellow]👋 Bye Omku![/bold yellow]\n")
        return
    elif mode == "capture":
        from leonardo_auth_capture import capture_auth
        asyncio.run(capture_auth())
    elif mode == "auto":
        options = collect_terminal_options(mode, settings)
        save_app_settings({"mode": mode, **options})
        captured, results = asyncio.run(run_auto_batch(headless=False, **options))
        print_final_result(captured)
    elif mode == "auto_headless":
        options = collect_terminal_options(mode, settings)
        save_app_settings({"mode": mode, **options})
        captured, results = asyncio.run(run_auto_batch(headless=True, **options))
        print_final_result(captured)


if __name__ == "__main__":
    main()
