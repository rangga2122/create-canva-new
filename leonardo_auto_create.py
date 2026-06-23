#!/usr/bin/env python3
"""
Leonardo Auto Create Account + Auth Capture
============================================
Automated flow:
  1. Firefox Relay → Generate email mask
  2. Canva signup with mask email
  3. Gmail → Get OTP from Canva
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
  python leonardo_auto_create.py --relay-email "your@firefox.email"
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
VPS_PASS = "falcon-37#-panda"
SERVER_URL_HTTP = f"http://{VPS_IP}:{VPS_PORT}"
SERVER_URL_HTTPS = "https://leonardo.azkazamdigital.com"
SERVER_BEARER_IMPORT_URL = f"{SERVER_URL_HTTPS}/api/bearer/import"

# Canva team invite token
CANVA_INVITE_TOKEN = "SeTQSbn86mzp4Xh7tnL2LQ"
CANVA_INVITE_URL = f"https://www.canva.com/brand/join?token={CANVA_INVITE_TOKEN}&referrer=team-invite"

# URLs
FIREFOX_RELAY_URL = "https://relay.firefox.com/"
CANVA_URL = "https://www.canva.com/id_id/"
CANVA_SIGNUP_URL = "https://www.canva.com/id_id/signup/"
GMAIL_SPAM_URL = "https://mail.google.com/mail/u/0/#spam"
LEONARDO_LOGIN_URL = "https://app.leonardo.ai/auth/login"

# File paths
SCRIPT_DIR = Path(__file__).parent

# Eteum Pool — auto-import Canva account
ETTEUM_HOST = os.getenv("ETTEUM_HOST", "43.133.150.196")
ETTEUM_PORT = int(os.getenv("ETTEUM_PORT", "1930"))
ETTEUM_API_KEY = os.getenv("ETTEUM_API_KEY", "Nr201105")
ETTEUM_API_URL = f"http://{ETTEUM_HOST}:{ETTEUM_PORT}/api/accounts"
ETTEUM_HTTPS_URL = os.getenv("ETTEUM_HTTPS_URL", f"https://etteum.azkazamdigital.com/api/accounts")
CANVA_ACCOUNTS_FILE = SCRIPT_DIR / "canva_accounts.json"

AUTH_FILE = SCRIPT_DIR / "leonardo_auth.json"
ACCOUNTS_FILE = SCRIPT_DIR / "leonardo_accounts.json"
ACCOUNT_AUTH_DIR = SCRIPT_DIR / "auth_accounts"
BROWSER_DATA = SCRIPT_DIR / "browser_profile"
LOG_FILE = SCRIPT_DIR / "logs" / "auto_create.log"
LOG_FILE.parent.mkdir(exist_ok=True)
ACCOUNT_AUTH_DIR.mkdir(exist_ok=True)

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
        title.append("Firefox Relay → Canva → OTP → Leonardo → Token", style="bold cyan")
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
        flow.append(" Relay Mask  ", style="magenta")
        flow.append("→", style="dim")
        flow.append(" [2]", style="bold yellow on dark_magenta")
        flow.append(" Canva Signup  ", style="magenta")
        flow.append("→", style="dim")
        flow.append(" [3]", style="bold yellow on dark_magenta")
        flow.append(" Gmail OTP  ", style="magenta")
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
        print("║  Firefox Relay → Canva → OTP → Leonardo → Capture         ║")
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
                    # Include apiCredit — akun baru Leonardo pakai apiCredit (850), bukan subscription
                    for token_key in ["subscriptionTokens", "paidTokens", "rolloverTokens", "apiCredit", "streamTokens"]:
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


def save_account_auth_file(record):
    """Write full auth JSON for one account into auth_accounts/<email>.json."""
    ACCOUNT_AUTH_DIR.mkdir(exist_ok=True)
    email = record.get("email") or "unknown_account"
    auth_path = ACCOUNT_AUTH_DIR / safe_account_filename(email)
    payload = dict(record)
    payload["auth_file"] = str(auth_path)
    auth_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return auth_path


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
    record.update({
        "email": captured.get("email") or record.get("email") or "N/A",
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

    if existing:
        accounts[accounts.index(existing)] = record
    else:
        accounts.append(record)

    save_accounts(accounts)
    logger.ok(f"Account saved to registry: {record.get('email')}")
    logger.ok(f"Account auth JSON: {auth_path}")
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
                        await getJson("graphql-credits", "https://api.leonardo.ai/graphql", {
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


async def auto_create_account(headless=False, relay_email=None, gmail_logged_in=True):
    """
    Full automated flow:
    1. Firefox Relay → generate mask email
    2. Canva signup with mask
    3. Gmail → OTP
    4. Canva OTP verify
    5. Accept team invite
    6. Leonardo login via Canva SSO
    7. Capture auth
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
    }

    print_banner()

    async with async_playwright() as p:
        # Launch Chromium dengan persistent context
        logger.info("Launching browser (Chromium, persistent context)...")
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=str(BROWSER_DATA),
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

        try:
            await reset_canva_session(browser)
        except Exception as e:
            logger.warn(f"Canva startup reset failed, continuing anyway: {e}")

        try:
            await reset_leonardo_session(browser)
        except Exception as e:
            logger.warn(f"Leonardo startup reset failed, continuing anyway: {e}")

        # ════════════════════════════════════════════════════════
        # STEP 1: Firefox Relay → Generate email mask
        # ════════════════════════════════════════════════════════
        logger.step(1, "Firefox Relay — Generate Email Mask")
        print_step_header(1, "Firefox Relay — Generate Email Mask")

        # ════════════════════════════════════════════════════════
        # CLEAR CANVA COOKIES — hanya di awal, sebelum login Canva
        # (cookies Canva akan dipertahankan setelah login untuk Eteum Pool)
        # ════════════════════════════════════════════════════════
        try:
            logger.info("Clear Canva cookies (sebelum login)...")
            for domain in ["canva.com", ".canva.com", "www.canva.com", "www.canva.com/id_id/"]:
                try:
                    await browser.clear_cookies(domain=domain)
                except Exception:
                    pass
            logger.ok("Canva cookies cleared (awal)")
        except Exception as e:
            logger.warn(f"Failed to clear Canva cookies (awal): {e}")


        if relay_email:
            # Skip relay, pakai email yang sudah ada
            captured["email"] = relay_email
            logger.ok(f"Using provided email: {relay_email}")
            results.append({"desc": "Firefox Relay mask", "status": "SKIP", "data": relay_email})
        else:
            try:
                logger.info(f"Opening {FIREFOX_RELAY_URL}...")
                await page.goto(FIREFOX_RELAY_URL, wait_until="domcontentloaded", timeout=30000)
                await delay_ms(3000)

                try:
                    logger.info("Deleting old Relay mask with saved workflow selectors...")
                    await page.bring_to_front()
                    await delete_oldest_relay_mask(page)
                    logger.ok("Old Relay mask deleted")
                except Exception as de:
                    logger.warn(f"Relay delete skipped/failed: {de}")
                    try:
                        await page.keyboard.press("Escape")
                        await page.locator('div[class*="underlay"]').first.wait_for(state="detached", timeout=3000)
                    except Exception:
                        pass

                # Click "Generate new mask" / "Buat topeng baru" button
                logger.info("Looking for 'Generate new mask' button...")
                
                # Count existing masks before generating
                samp_before = page.locator("samp")
                mask_count_before = await samp_before.count()
                logger.info(f"Existing masks: {mask_count_before}")

                await click_workflow_selector(page, 'button[title="Generate new mask"]', timeout=5000)
                logger.ok('Clicked button[title="Generate new mask"]')
                await delay_ms(3000)

                # Get the newly created mask email from <samp> element
                logger.info("Extracting mask email...")
                samp = page.locator("samp")
                await samp.first.wait_for(state="visible", timeout=10000)
                
                # Get the first samp (newest mask is at the top)
                mask_count_after = await samp.count()
                logger.info(f"Masks after generate: {mask_count_after}")
                
                mask_email = await samp.first.text_content()
                mask_email = mask_email.strip()
                captured["email"] = mask_email
                logger.ok(f"Mask email: {mask_email}")
                results.append({"desc": "Firefox Relay mask", "status": "OK", "data": mask_email})

                logger.info("Firefox Relay tab kept open; continuing Canva signup in the same tab")

            except Exception as e:
                logger.error(f"Firefox Relay failed: {e}")
                results.append({"desc": "Firefox Relay mask", "status": "FAIL", "data": str(e)[:50]})
                # No email available — cannot continue
                logger.error("Tidak ada email! Masukkan email di field 'Relay Email' atau login Firefox Relay dulu via tombol BUKA BROWSER.")
                raise RuntimeError("Email tidak tersedia. Isi field Relay Email atau login Firefox Relay dulu.")

        # ════════════════════════════════════════════════════════
        # STEP 2: Delete old Firefox Relay mask
        logger.step(2, "Firefox Relay - Delete Old Mask")
        print_step_header(2, "Firefox Relay - Delete Old Mask")

        logger.info("Relay cleanup already ran before generating the new mask")
        results.append({"desc": "Firefox Relay cleanup", "status": "OK", "data": "before generate"})

        # STEP 3: Canva Signup with mask email
        # ════════════════════════════════════════════════════════
        logger.step(3, "Canva Signup with Mask Email")
        print_step_header(3, "Canva Signup with Mask Email")

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
            logger.info("Submitting signup form again...")
            await click_selector(canva_page, 'button[type="submit"]', timeout=5000)
            logger.ok("Signup form submitted — OTP should arrive in Gmail")
            await delay_ms(3000)
            results.append({"desc": "Canva signup", "status": "OK", "data": captured["email"]})

        except Exception as e:
            logger.error(f"Canva signup failed: {e}")
            results.append({"desc": "Canva signup", "status": "FAIL", "data": str(e)[:50]})

        # ════════════════════════════════════════════════════════
        # STEP 4: Gmail -> Get OTP
        # ════════════════════════════════════════════════════════
        logger.step(4, "Gmail - Get OTP from Canva")
        print_step_header(4, "Gmail - Get OTP from Canva")

        otp_code = None
        try:
            logger.info(f"Opening Gmail spam folder...")
            gmail_page = await browser.new_page()
            await gmail_page.goto(GMAIL_SPAM_URL, wait_until="domcontentloaded", timeout=30000)
            logger.info("Reloading Gmail before clicking inbox controls...")
            await gmail_page.reload(wait_until="domcontentloaded", timeout=30000)
            await delay_ms(5000)

            # Saved workflow clicks Gmail list controls twice after reload.
            logger.info('Clicking Gmail selector: div[class="asa"] (1/2)')
            await try_click_workflow_selector(gmail_page, 'div[class="asa"]', timeout=10000)
            await delay_ms(2000)
            logger.info('Clicking Gmail selector: div[class="asa"] (2/2)')
            await try_click_workflow_selector(gmail_page, 'div[class="asa"]', timeout=10000)
            await delay_ms(3000)

            logger.info("Clicking Gmail inbox row selector: tr.zA")
            row_otp_text = await click_gmail_canva_row(gmail_page, captured.get("email"), timeout=15000)
            await delay_ms(2000)

            logger.info('Clicking optional Gmail email selector: span[class="yP"]')
            await try_click_workflow_selector(gmail_page, 'span[class="yP"]', timeout=5000)
            logger.ok("Opened Canva email")
            await delay_ms(2000)

            # Extract OTP code from email body
            logger.info("Extracting OTP code...")
            otp_text = row_otp_text or ""
            
            # Method 1: td[align="center"] (standard Canva OTP selector)
            try:
                otp_element = gmail_page.locator('td[align="center"]')
                if await otp_element.count() > 0:
                    await otp_element.first.wait_for(state="visible", timeout=5000)
                    otp_text = (await otp_element.first.text_content()) or ""
                    logger.info(f"OTP Element text: {otp_text}")
            except:
                pass
            
            # Method 2: Fallback to reading the full email body (div.a3s is standard Gmail email body container)
            if not re.search(r'\b(\d{6})\b', otp_text):
                logger.info("Standard OTP element not found or invalid. Grabbing full email body content...")
                try:
                    body_element = gmail_page.locator('div.a3s').first
                    await body_element.wait_for(state="visible", timeout=5000)
                    otp_text = (await body_element.text_content()) or ""
                except Exception as be:
                    logger.warn(f"Failed to read full email body: {be}")
            
            # Extract numeric OTP (usually 6 digits)
            otp_match = re.search(r'\b(\d{6})\b', otp_text or "")
            if otp_match:
                otp_code = otp_match.group(1)
                logger.ok(f"OTP code: {otp_code}")
                results.append({"desc": "Gmail OTP", "status": "OK", "data": otp_code})
            else:
                # Try get full text as OTP
                otp_code = otp_text.strip()
                logger.warn(f"OTP extracted (non-standard): {otp_code}")
                results.append({"desc": "Gmail OTP", "status": "OK", "data": otp_code[:20]})

            await delay_ms(2000)
            logger.info('Clicking Gmail post-OTP delete/back selector: .iH .aFi > .Bn')
            await click_workflow_selector(gmail_page, '.iH .aFi > .Bn', timeout=5000)
            await delay_ms(3000)
            try:
                await gmail_page.close()
                logger.info("Gmail tab closed after OTP captured")
            except Exception as ce:
                logger.info(f"Gmail tab close skipped: {ce}")

        except Exception as e:
            logger.error(f"Gmail OTP failed: {e}")
            results.append({"desc": "Gmail OTP", "status": "FAIL", "data": str(e)[:50]})
            logger.error("OTP gagal diambil. Pastikan sudah login Gmail via tombol BUKA BROWSER.")
            raise RuntimeError("OTP gagal. Login Gmail dulu via BUKA BROWSER.")

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
        # STEP 8: Capture Auth (Canva cookies DIPERTAHANKAN untuk Eteum)
        # ════════════════════════════════════════════════════════
        logger.step(8, "Capture Auth")
        print_step_header(8, "Capture Auth")

        try:
            # NOTE: Canva cookies TIDAK di-clear — akan dipakai untuk import ke Eteum Pool
            # Clear cookies Canva hanya dilakukan di awal (sebelum login Canva)

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

            if not captured["access_token"] and has_captured_auth(captured):
                logger.info("Bearer token not found, using Leonardo cookie session auth")

            # NOTE: Canva cookies TIDAK di-clear — akan dipakai untuk import ke Eteum Pool
            # Clear cookies Canva hanya dilakukan di awal (sebelum login Canva)

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

        # ════════════════════════════════════════════════════════════
        # GENERATE VIA API — flux-dev 1024x1024 MEDIUM (sama dengan leonardo.azkazamdigital)
        # ════════════════════════════════════════════════════════════
        if has_complete_leonardo_auth(captured):
            logger.info("Generate image via API Leonardo untuk verify credit berkurang...")
            try:
                spend_ok = await ensure_credit_spent_via_api(captured, full_credit=8500, timeout=120)
                results.append({
                    "desc": "Leonardo credit spent (API)",
                    "status": "OK" if spend_ok else "FAIL",
                    "data": str(captured.get("credit_balance")),
                })
            except Exception as e:
                logger.warn(f"API generate skipped: {e}")

        # ════════════════════════════════════════════════════════════
        # CAPTURE CANVA COOKIES — untuk Eteum Pool
        # ════════════════════════════════════════════════════════════
        try:
            all_browser_cookies = await browser.cookies()
            logger.info(f"Total browser cookies: {len(all_browser_cookies)}")
            # Log semua domain unik untuk debug
            domains = set((c.get("domain") or "").lower() for c in all_browser_cookies)
            canva_domains = [d for d in domains if "canva" in d]
            logger.info(f"Cookie domains: {len(domains)} total, Canva: {canva_domains or 'NONE'}")
            canva_tokens = extract_canva_cookies(all_browser_cookies)
            if canva_tokens:
                captured["canva_tokens"] = canva_tokens
                logger.ok(f"Canva cookies captured: {len(canva_tokens)} keys (caz={len(canva_tokens.get('caz', ''))} chars)")
            else:
                logger.warn("Canva cookies tidak ditemukan (caz missing)")
        except Exception as e:
            logger.warn(f"Canva cookies capture gagal: {e}")

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
    if has_complete_leonardo_auth(captured):
        save_success_account(captured)
    elif has_captured_auth(captured):
        logger.warn("Partial Leonardo auth saved for debug only; not added to successful account list")

    # Print summary
    print_summary(results)

    # Send to server
    if has_complete_leonardo_auth(captured):
        logger.info("Sending bearer to VPS server...")
        sent = await send_to_server(captured)
        if sent:
            logger.ok("Auth sent to server! 🎉")
        else:
            logger.warn("Could not send to server - auth saved locally")
    elif has_captured_auth(captured):
        logger.warn("Skipping VPS send because bearer/credit capture is incomplete")
    else:
        logger.warn("No Leonardo auth captured - check screenshots + logs")

    # ════════════════════════════════════════════════════════════
    # ETEUM POOL: Import akun Canva + simpan lokal PC
    # ════════════════════════════════════════════════════════════
    canva_tokens = captured.get("canva_tokens")
    if has_canva_auth(canva_tokens):
        logger.info("Importing Canva account to Eteum Pool...")
        etteum_result = await send_to_etteum(captured)
        if etteum_result:
            logger.ok(f"Canva account imported to Eteum! (id={etteum_result.get('id', '?')})")
            captured["etteum_imported"] = True
            captured["etteum_account_id"] = etteum_result.get("id")
        else:
            logger.warn("Eteum import gagal — Canva account tetap disimpan lokal")
            captured["etteum_imported"] = False

        local_record = save_canva_account_local(captured)
        if local_record:
            logger.ok("Canva account saved to local PC (canva_accounts.json)")
    else:
        logger.info("Canva tokens tidak lengkap, skip Eteum import + save lokal")

    return captured, results


# ════════════════════════════════════════════════════════════
# ETEUM POOL: Import Canva account + simpan lokal PC
# ════════════════════════════════════════════════════════════

def extract_canva_cookies(browser_cookies):
    """Extract cookies Canva dari browser context untuk Eteum Pool."""
    # Canva cookies pakai UPPERCASE (CAZ, CB, CAU) — normalisasi ke lowercase
    canva_keys = {"caz", "cb", "cau", "user_id", "cid", "cui", "cul", "cdi", "cs", "cl", "cf_clearance"}
    tokens = {}
    all_canva = []
    canva_domains_found = set()
    all_cookie_names = []

    for c in browser_cookies or []:
        domain = (c.get("domain") or "").lower()
        name = c.get("name", "")
        name_lower = name.lower()
        all_cookie_names.append(f"{name}@{domain}")
        # Match berbagai format domain Canva: canva.com, .canva.com, www.canva.com
        if "canva.com" not in domain:
            continue
        canva_domains_found.add(domain)
        all_canva.append(c)
        # Case-insensitive match — normalisasi ke lowercase
        if name_lower in canva_keys:
            tokens[name_lower] = c.get("value", "")

    tokens["all_cookies"] = all_canva

    # Debug logging
    if not tokens.get("caz"):
        logger.warn(f"caz NOT found. Canva domains: {canva_domains_found or 'NONE'}")
        logger.info(f"Total cookies: {len(browser_cookies or [])}, Canva cookies: {len(all_canva)}")
        if all_canva:
            canva_names = [c.get("name", "") for c in all_canva]
            logger.info(f"Canva cookie names: {canva_names[:30]}")
    else:
        logger.ok(f"Canva cookies found: {list(tokens.keys())}")

    return tokens if tokens.get("caz") else None


def has_canva_auth(canva_tokens):
    """Cek apakah tokens Canva cukup untuk import ke Eteum."""
    if not canva_tokens:
        return False
    return bool(canva_tokens.get("caz") and canva_tokens.get("cb"))


async def send_to_etteum(captured):
    """POST akun Canva ke Eteum Pool API."""
    canva_tokens = captured.get("canva_tokens") or {}
    if not has_canva_auth(canva_tokens):
        logger.warn("Canva tokens tidak lengkap (caz/cb missing), skip Eteum import")
        return None

    email = captured.get("email") or captured.get("canva_email") or "unknown@canva.com"
    password = captured.get("password") or captured.get("canva_password") or ""

    payload = {
        "provider": "canva",
        "email": email,
        "password": password,
        "tokens": canva_tokens,
        "status": "active",
    }

    headers = {
        "Content-Type": "application/json",
        "X-API-Key": ETTEUM_API_KEY,
    }

    import requests as _req
    urls = [ETTEUM_API_URL, ETTEUM_HTTPS_URL]
    for url in urls:
        try:
            logger.info(f"POST {url} (provider=canva)...")
            resp = _req.post(url, json=payload, headers=headers, timeout=15)
            if resp.status_code in (200, 201):
                data = resp.json()
                logger.ok(f"Eteum import OK: id={data.get('id', '?')}, status={data.get('status', '?')}")
                return data
            elif resp.status_code == 409:
                logger.warn(f"Eteum: akun Canva sudah ada (409)")
                return {"id": None, "status": "duplicate"}
            else:
                logger.warn(f"Eteum import HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            logger.warn(f"Eteum import gagal ({url}): {type(e).__name__}: {e}")

    return None


def save_canva_account_local(captured):
    """Simpan akun Canva ke canva_accounts.json di lokal PC."""
    canva_tokens = captured.get("canva_tokens") or {}
    if not has_canva_auth(canva_tokens):
        return None

    record = {
        "email": captured.get("email") or captured.get("canva_email"),
        "password": captured.get("password") or captured.get("canva_password"),
        "tokens": canva_tokens,
        "leonardo_bearer": captured.get("access_token"),
        "leonardo_credit_balance": captured.get("credit_balance"),
        "captured_at": captured.get("captured_at") or datetime.now().isoformat(),
        "etteum_imported": captured.get("etteum_imported", False),
        "etteum_account_id": captured.get("etteum_account_id"),
    }

    accounts = []
    if CANVA_ACCOUNTS_FILE.exists():
        try:
            accounts = json.loads(CANVA_ACCOUNTS_FILE.read_text())
        except Exception:
            accounts = []

    # Cek duplikat by email
    email = record.get("email")
    accounts = [a for a in accounts if a.get("email") != email]
    accounts.append(record)

    try:
        CANVA_ACCOUNTS_FILE.write_text(json.dumps(accounts, indent=2, default=str))
        return record
    except Exception as e:
        logger.warn(f"save_canva_account_local gagal: {e}")
        return None


# ════════════════════════════════════════════════════════════
# GENERATE VIA BROWSER UI
# ════════════════════════════════════════════════════════════

# ════════════════════════════════════════════════════════════
# LEONARDO API: Generate via httpx (gpt-image-2, 1024x1024, medium)
# Format sama dengan leonardo.azkazamdigital.com (server.py)
# ════════════════════════════════════════════════════════════

LEONARDO_GRAPHQL_URL = "https://api.leonardo.ai/v1/graphql"
LEONARDO_REST_GENERATIONS_URL = "https://cloud.leonardo.ai/api/rest/v1/generations"
LEONARDO_GPT_IMAGE_MODEL = "gpt-image-2"


def _build_generation_graphql_payload(prompt):
    """Build GraphQL mutation payload — flux-dev, 1024x1024, MEDIUM (sama dengan leonardo.azkazamdigital)."""
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
    """Build REST fallback payload — gpt-image-2, 1024x1024."""
    return {
        "prompt": prompt,
        "modelId": LEONARDO_GPT_IMAGE_MODEL,
        "num_images": 1,
        "width": 1024,
        "height": 1024,
    }


def _leonardo_api_headers(token):
    """Headers untuk API Leonardo (sama dengan leonardo.azkazamdigital)."""
    return {
        "accept": "*/*",
        "content-type": "application/json",
        "authorization": f"Bearer {token}",
        "origin": "https://app.leonardo.ai",
        "referer": "https://app.leonardo.ai/",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
        "x-leo-schema-version": "1.185.11",
        "sec-ch-ua-platform": '"Windows"',
    }


async def trigger_leonardo_generation_via_api(captured):
    """Generate 1x gambar via httpx langsung ke API Leonardo (tanpa browser).

    Menggunakan format yang terbukti berhasil di leonardo.azkazamdigital.com:
    flux-dev, 1024x1024, MEDIUM, CreateGenerationRequest!, generate mutation.
    """
    token = captured.get("access_token")
    if not token:
        logger.warn("Bearer token belum tersedia, tidak bisa generate via API")
        return False

    prompt = f"pemandangan indah {int(time.time())}"
    logger.info("Generate gambar via API Leonardo (flux-dev 1024x1024 MEDIUM)...")

    headers = _leonardo_api_headers(token)
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

            # Fallback: REST endpoint dengan gpt-image-2
            logger.info("Fallback: REST endpoint dengan gpt-image-2...")
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
        return None

    headers = _leonardo_api_headers(token)

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
                logger.info(f"Credit API response: {str(data)[:400]}")
                credits = extract_credit_balance(data) if "extract_credit_balance" in globals() else None
                if credits is not None:
                    captured["credit_balance"] = credits
                    logger.ok(f"Saldo credit: {credits}")
                    return credits
                # Manual extract — include apiCredit (akun baru pakai apiCredit)
                users = (data.get("data") or {}).get("users") or []
                if users:
                    details = users[0].get("user_details") or {}
                    sub = details.get("subscriptionTokens") or 0
                    paid = details.get("paidTokens") or 0
                    roll = details.get("rolloverTokens") or 0
                    api = details.get("apiCredit") or 0
                    stream = details.get("streamTokens") or 0
                    total = sub + paid + roll + api + stream
                    logger.info(f"Credit breakdown: sub={sub} paid={paid} roll={roll} api={api} stream={stream} → total={total}")
                    captured["credit_balance"] = total
                    logger.ok(f"Saldo credit: {total}")
                    return total
            else:
                logger.warn(f"Credit API HTTP {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        logger.warn(f"Cek credit via API gagal: {e}")

    return None


async def ensure_credit_spent_via_api(captured, full_credit=8500, timeout=120):
    """Generate via API lalu tunggu credit berkurang.

    1. Cek credit awal via API
    2. Generate 1x gambar via API (flux-dev 1024x1024 MEDIUM)
    3. Cek credit setiap 5s, retry generate setiap 15s sampai berkurang
    """
    initial = await refresh_credit_via_api(captured)
    logger.info(f"Credit awal: {initial}, target: kurang dari {full_credit}")

    if initial is not None and initial < full_credit:
        logger.ok(f"Credit sudah di bawah full: {initial} < {full_credit}")
        return True

    deadline = time.time() + timeout
    retry_interval = 15
    last_retry = 0

    while time.time() < deadline:
        api_ok = await trigger_leonardo_generation_via_api(captured)
        if not api_ok:
            logger.warn("Generate via API gagal, retry 15s...")
            await asyncio.sleep(15)
            continue

        # Tunggu credit berkurang
        for _ in range(6):
            await asyncio.sleep(5)
            current = await refresh_credit_via_api(captured)
            if initial is not None and current is not None and current < initial:
                logger.ok(f"Credit berkurang: {initial} -> {current}")
                return True
            if current is not None and full_credit and current < full_credit:
                logger.ok(f"Credit di bawah full: {current} < {full_credit}")
                return True

        logger.info(f"Credit belum berkurang ({captured.get('credit_balance')}), retry generate...")

    logger.warn(f"Credit belum berkurang dari {full_credit}; generate gagal")
    return False


async def send_to_server(captured):
    """Send bearer token to the current VPS bearer import endpoint."""
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
# MAIN MENU
# ════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Leonardo Auto Create Account + Auth Capture")
    parser.add_argument("--relay-email", help="Skip Firefox Relay, use provided email")
    parser.add_argument("--headless", action="store_true", help="Run headless (no browser window)")
    parser.add_argument("--capture-only", action="store_true", help="Only capture auth (skip account creation)")
    parser.add_argument("--no-menu", action="store_true", help="Skip interactive menu, run directly")
    args = parser.parse_args()

    # If CLI args provided, skip menu
    if args.capture_only:
        from leonardo_auth_capture import capture_auth
        asyncio.run(capture_auth())
        return

    if args.relay_email or args.headless or args.no_menu:
        asyncio.run(auto_create_account(
            headless=args.headless,
            relay_email=args.relay_email,
        ))
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
        captured, results = asyncio.run(auto_create_account(headless=False))
        print_final_result(captured)
    elif mode == "auto_headless":
        captured, results = asyncio.run(auto_create_account(headless=True))
        print_final_result(captured)


if __name__ == "__main__":
    main()
