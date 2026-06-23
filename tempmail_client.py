"""
TempMail API Client untuk mail.digitalku.store
- Generate email (standard atau premium dengan voucher)
- Polling inbox untuk OTP
- Auto-extract OTP code dari email body
"""

import re
import time
import httpx
from typing import Optional

# Config
TEMPMAIL_BASE = "https://mail.digitalku.store"

# Voucher codes untuk premium domains
VOUCHER_CODES = ["Z3L7F", "Z1R4Y7"]

# Domain yang cocok untuk Leonardo (tech, biz.id, dll)
PREFERRED_DOMAINS = [
    "mailservice.studio",
    "digitalku.email",
    "aplikasipremium.me",
    "premiumku.app",
    "premiumku.me",
    "digitalku.store",
    "apku.me",
    "apke.me",
    "apko.me",
    "atlaz.tech",
    "botlayer.tech",
    "capcutpro.tech",
    "teravision.tech",
    "saltar.tech",
    "kasla.tech",
    "mesla.tech",
    "zarn.tech",
    "netro.dev",
    "nitroz.dev",
    "redmail.tech",
    "digitalku.tech",
    "zoro.biz.id",
    "mailserver.biz.id",
    "digitalku.dev",
    "vertaz.me",
    "zefa.me",
    "nextz.me",
    "apk.works",
]

# Domain yang sering diblokir (mental di Canva/Leonardo)
BLOCKED_DOMAINS = [
    "hotmail.web.id",   # terlalu mirip hotmail
    "frostmail.web.id", # kadang diblokir
    "spotifi.app",      # mirip spotify
    "spotifi.tech",
    "myapple.tech",     # mirip apple
    "asuraimu.eu.cc",   # standard, kadang diblokir
]

# OTP patterns
OTP_PATTERNS = [
    r'\b(\d{6})\b',            # 6 digit (paling umum)
    r'\b(\d{4})\b',            # 4 digit
    r'\b(\d{8})\b',            # 8 digit
    r'G-(\d{4,8})',            # Google style
    r'verification code[:\s]*(\d{4,8})',
    r'kode[:\s]*(\d{4,8})',
    r'code[:\s]*(\d{4,8})',
    r'OTP[:\s]*(\d{4,8})',
]

SENDER_WHITELIST = [
    'canva',
    'noreply@canva.com',
    'no-reply@canva.com',
    'team@canva.com',
    'noreply@google.com',
    'no-reply@accounts.google.com',
    'accounts.google.com',
    'leonardo',
    'noreply@leonardo.ai',
]


def get_available_domains() -> list:
    """Ambil list domain aktif dari API."""
    try:
        resp = httpx.get(f"{TEMPMAIL_BASE}/api/domains", timeout=15)
        data = resp.json()
        if data.get("success"):
            return data["domains"]
    except Exception as e:
        print(f"Error fetching domains: {e}")
    return []


def pick_best_domain() -> tuple:
    """
    Pilih domain terbaik untuk daftar Leonardo.
    Return (domain_name, domain_id, is_premium).
    """
    domains = get_available_domains()
    if not domains:
        return ("asuraimu.eu.cc", "", False)

    # Filter: active, tidak di blocklist
    candidates = []
    for d in domains:
        if d["status"] != "active":
            continue
        if d["name"] in BLOCKED_DOMAINS:
            continue
        is_premium = bool(d.get("is_premium"))
        is_standard = not is_premium and not d.get("is_hidden")
        candidates.append({
            "name": d["name"],
            "id": d["id"],
            "is_premium": is_premium,
            "is_standard": is_standard,
        })

    # Prioritas: domain preferred yang premium > domain preferred standard > lainnya
    for c in candidates:
        if c["name"] in PREFERRED_DOMAINS and c["is_premium"]:
            return (c["name"], c["id"], True)

    for c in candidates:
        if c["name"] in PREFERRED_DOMAINS and c["is_standard"]:
            return (c["name"], c["id"], False)

    # Fallback: premium pertama yang tidak di-block
    for c in candidates:
        if c["is_premium"]:
            return (c["name"], c["id"], True)

    # Fallback: standard pertama
    for c in candidates:
        if c["is_standard"]:
            return (c["name"], c["id"], False)

    # Last resort
    if candidates:
        return (candidates[0]["name"], candidates[0]["id"], candidates[0]["is_premium"])

    return ("asuraimu.eu.cc", "", False)


def generate_email(username: str = None, domain: str = None, domain_id: str = None,
                   voucher_code: str = None, password: str = None) -> dict:
    """
    Generate email temporer via API.

    Args:
        username: Username untuk email (random jika None)
        domain: Domain name (auto-pick jika None)
        domain_id: Domain ID dari API (zoneId)
        voucher_code: Kode voucher untuk premium domain
        password: Password protection (optional)

    Returns:
        dict: {success, email, error}
    """
    import random, string

    if not domain or not domain_id:
        domain, domain_id, is_premium = pick_best_domain()
    else:
        # Cek apakah domain yang di-provide adalah premium
        domains = get_available_domains()
        d_info = next((d for d in domains if d["name"] == domain), {})
        is_premium = bool(d_info.get("is_premium"))

    if is_premium and not voucher_code:
        # Coba semua voucher yang tersedia
        for vc in VOUCHER_CODES:
            if _validate_voucher(vc, domain):
                voucher_code = vc
                print(f"[TempMail] Using voucher: {vc} for {domain}")
                break

    if is_premium and not voucher_code:
        return {"success": False, "error": f"No valid voucher for premium domain {domain}"}

    if not username:
        username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))

    payload = {
        "username": username,
        "domain": domain,
        "zoneId": domain_id,
        "emailDomain": domain,
        "password": password,
        "voucherCode": voucher_code or "",
    }

    try:
        resp = httpx.post(f"{TEMPMAIL_BASE}/api/generate",
                         json=payload,
                         timeout=30,
                         headers={"Content-Type": "application/json"})
        data = resp.json()
        if data.get("success"):
            return {
                "success": True,
                "email": data["email"],
                "username": username,
                "domain": domain,
            }
        else:
            return {"success": False, "error": data.get("error", "Unknown error")}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _validate_voucher(code: str, domain: str) -> bool:
    """Validasi kode voucher untuk domain tertentu."""
    try:
        resp = httpx.post(f"{TEMPMAIL_BASE}/api/voucher/validate",
                         json={"code": code, "domain": domain},
                         timeout=15,
                         headers={"Content-Type": "application/json"})
        data = resp.json()
        return data.get("valid", False)
    except:
        return False


def fetch_inbox(email: str) -> list:
    """
    Ambil list email dari inbox.

    Returns:
        list of email dicts: [{id, from, subject, text, date, html, attachments}]
    """
    try:
        resp = httpx.post(f"{TEMPMAIL_BASE}/api/mailbox/fetch",
                         json={"email": email},
                         timeout=15,
                         headers={"Content-Type": "application/json"})
        data = resp.json()
        if data.get("success"):
            return data.get("emails", [])
    except Exception as e:
        print(f"Fetch inbox error: {e}")
    return []


def extract_otp(text: str, subject: str = "") -> Optional[str]:
    """
    Extract OTP code dari text email.
    Cari pattern 4-8 digit.
    """
    full_text = f"{subject}\n{text}"

    for pattern in OTP_PATTERNS:
        matches = re.findall(pattern, full_text, re.IGNORECASE)
        if matches:
            otp = matches[-1] if isinstance(matches[-1], str) else matches[-1][0]
            digits = re.sub(r'\D', '', otp)
            if 4 <= len(digits) <= 8:
                return digits

    return None


def wait_for_otp(email: str, timeout: int = 120, poll_interval: int = 5,
                 sender_filter: str = None) -> Optional[str]:
    """
    Polling inbox sampai OTP masuk atau timeout.

    Args:
        email: Alamat email temp mail
        timeout: Max wait dalam detik (default 120)
        poll_interval: Interval polling dalam detik (default 5)
        sender_filter: Filter pengirim (optional, e.g. "canva")

    Returns:
        OTP code string, atau None jika timeout
    """
    print(f"[TempMail] Waiting for OTP on {email} (timeout: {timeout}s)...")

    start = time.time()
    seen_ids = set()

    # Initial fetch — catat email yang sudah ada (skip)
    initial = fetch_inbox(email)
    for e in initial:
        seen_ids.add(str(e.get("id", "")))
    if initial:
        print(f"[TempMail] {len(initial)} existing emails (will skip)")

    while time.time() - start < timeout:
        emails = fetch_inbox(email)

        for e in emails:
            eid = str(e.get("id", ""))
            if eid in seen_ids:
                continue

            # New email!
            seen_ids.add(eid)
            sender = str(e.get("from", ""))
            subject = str(e.get("subject", ""))
            body = str(e.get("text", "")) or str(e.get("html", ""))

            print(f"[TempMail] New email: {sender} — {subject}")

            # Filter by sender if specified
            if sender_filter:
                if sender_filter.lower() not in sender.lower():
                    print(f"[TempMail] Sender mismatch (want: {sender_filter}), skipping...")
                    continue

            # Extract OTP
            otp = extract_otp(body, subject)
            if otp:
                print(f"[TempMail] OTP found: {otp}")
                return otp
            else:
                print(f"[TempMail] No OTP pattern in this email")

        elapsed = int(time.time() - start)
        print(f"[TempMail] No OTP yet ({elapsed}s/{timeout}s), retry in {poll_interval}s...")
        time.sleep(poll_interval)

    print(f"[TempMail] Timeout! No OTP received after {timeout}s")
    return None


def wait_for_email(email: str, timeout: int = 120, poll_interval: int = 5,
                   sender_filter: str = None, subject_filter: str = None) -> Optional[dict]:
    """
    Polling inbox sampai email yang dicari masuk.

    Returns:
        Email dict, atau None jika timeout
    """
    print(f"[TempMail] Waiting for email on {email} (timeout: {timeout}s)...")

    start = time.time()
    seen_ids = set()

    # Skip existing
    initial = fetch_inbox(email)
    for e in initial:
        seen_ids.add(str(e.get("id", "")))

    while time.time() - start < timeout:
        emails = fetch_inbox(email)

        for e in emails:
            eid = str(e.get("id", ""))
            if eid in seen_ids:
                continue

            seen_ids.add(eid)
            sender = str(e.get("from", ""))
            subject = str(e.get("subject", ""))

            if sender_filter and sender_filter.lower() not in sender.lower():
                continue
            if subject_filter and subject_filter.lower() not in subject.lower():
                continue

            print(f"[TempMail] Match found: {sender} — {subject}")
            return e

        time.sleep(poll_interval)

    print(f"[TempMail] Timeout! No matching email after {timeout}s")
    return None


def delete_email(email: str, email_id: str) -> bool:
    """Hapus email dari inbox."""
    try:
        resp = httpx.post(f"{TEMPMAIL_BASE}/api/mailbox/delete",
                         json={"email": email, "id": email_id},
                         timeout=15,
                         headers={"Content-Type": "application/json"})
        data = resp.json()
        return data.get("success", False)
    except:
        return False


# ════════════════════════════════════════════════════════════
# TEST MODE
# ════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=== TempMail Client Test ===\n")

    # 1. List domains
    print("Available domains:")
    domains = get_available_domains()
    for d in domains[:10]:
        tag = "PREMIUM" if d.get("is_premium") else "STANDARD"
        print(f"  [{tag}] {d['name']}")
    print(f"  ... total: {len(domains)}\n")

    # 2. Pick best domain
    domain, domain_id, is_premium = pick_best_domain()
    print(f"Best domain: {domain} (premium: {is_premium})\n")

    # 3. Generate email
    print("Generating email...")
    result = generate_email(domain=domain, domain_id=domain_id)
    print(f"Result: {result}\n")

    if result.get("success"):
        email = result["email"]
        print(f"Email created: {email}")
        print(f"Inbox URL: {TEMPMAIL_BASE}/mailbox.html?email={email}")

        # 4. Poll inbox for 30s (just to test)
        print("\nPolling inbox for 30s...")
        otp = wait_for_otp(email, timeout=30, poll_interval=5)
        if otp:
            print(f"OTP: {otp}")
        else:
            print("No OTP (expected — nobody sent email)")
