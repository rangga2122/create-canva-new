#!/usr/bin/env python3
"""Export Canva cookies dari file JSON ke format browser-ready.
Usage: python export_canva_browser.py [email]
"""
import json, sys, os, re

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CANVA_DIR = os.path.join(SCRIPT_DIR, "canva_accounts")

def load_account(email=None):
    if email and CANVA_DIR:
        safe = email.lower().strip()
        safe = re.sub(r'[^a-z0-9._@+-]+', '_', safe)
        path = os.path.join(CANVA_DIR, f"{safe}.json")
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
    
    fallback = os.path.join(SCRIPT_DIR, "canva_accounts.json")
    if os.path.exists(fallback):
        with open(fallback) as f:
            accounts = json.load(f)
        if email:
            for a in accounts:
                if a.get("email") == email:
                    return a
            return None
        return accounts[0] if accounts else None
    return None

def print_account_info(account):
    tokens = account.get("tokens", {})
    all_cookies = tokens.get("all_cookies", [])
    
    cookie_pairs = []
    if isinstance(all_cookies, list):
        for c in all_cookies:
            if isinstance(c, dict):
                cookie_pairs.append(f"{c['name']}={c['value']}")
    elif isinstance(all_cookies, dict):
        for k, v in all_cookies.items():
            cookie_pairs.append(f"{k}={v}")
    
    cookie_str = "; ".join(cookie_pairs)
    
    email = account.get("email", "")
    password = account.get("password", "")
    
    print("=" * 60)
    print(f"ACCOUNT: {email}")
    print(f"PASSWORD: {password}")
    print("=" * 60)
    print()
    print("# === CARA 1: Browser Console (paling gampang) ===")
    print("# 1. Buka https://www.canva.com/ di browser")
    print("# 2. Tekan F12 → Console")
    print("# 3. Paste ini lalu tekan Enter:")
    print()
    
    # Split cookies per baris untuk console
    for cp in cookie_pairs:
        print(f'document.cookie = "{cp}";')
    
    print()
    print('# 4. Refresh halaman (F5)')
    print()
    print("# === CARA 2: URL langsung ===")
    print(f"https://www.canva.com/")
    print(f"Email: {email}")
    print(f"Password: {password}")
    print()
    print("# Info:")
    print(f"# Credit: {account.get('leonardo_credit_balance', '?')}")
    print(f"# Captured: {account.get('captured_at', '?')}")
    print(f"# Eteum imported: {account.get('etteum_imported', False)}")

if __name__ == "__main__":
    email = sys.argv[1] if len(sys.argv) > 1 else None
    
    account = load_account(email)
    if not account:
        print("ERROR: Account tidak ditemukan!")
        print("Usage: python export_canva_browser.py <email>")
        print()
        print("Available accounts:")
        if CANVA_DIR and os.path.isdir(CANVA_DIR):
            for f in os.listdir(CANVA_DIR):
                if f.endswith('.json'):
                    print(f"  - {f.replace('.json', '')}")
        sys.exit(1)
    
    print_account_info(account)
