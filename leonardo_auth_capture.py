#!/usr/bin/env python3
"""
Leonardo Auth Capture — Jalankan di PC sendiri
Buka Leonardo, login manual, capture full auth, kirim ke server.

Install:
  pip install playwright httpx
  playwright install chromium

Run:
  python leonardo_auth_capture.py
"""

import asyncio
import json
import os
import sys
import time
import base64
from pathlib import Path
from datetime import datetime

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("Install dulu: pip install playwright && playwright install chromium")
    sys.exit(1)

try:
    import httpx
except ImportError:
    print("Install dulu: pip install httpx")
    sys.exit(1)

# === CONFIG ===
# Server VPS — coba beberapa metode
VPS_IP = "43.133.150.196"
VPS_PORT = 1940
VPS_USER = "ubuntu"
VPS_PASS = "falcon-37#-panda"  # Akan diminta interaktif kalau kosong
SERVER_URL_HTTP = f"http://{VPS_IP}:{VPS_PORT}"
SERVER_URL_HTTPS = "https://leonardo.azkazamdigital.com"

AUTH_FILE = Path(__file__).parent / "leonardo_auth.json"
BROWSER_DATA = Path(__file__).parent / "browser_profile"

async def capture_auth():
    print("""
╔══════════════════════════════════════════════╗
║  Leonardo Auth Capture                      ║
║  1. Browser akan terbuka                    ║
║  2. Login Leonardo (Google/Canva/Email)     ║
║  3. Script auto-capture token setelah login ║
║  4. Kirim auth ke server VPS                ║
╚══════════════════════════════════════════════╝
    """)

    async with async_playwright() as p:
        # Launch Chromium dengan persistent context (simpan session)
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=str(BROWSER_DATA),
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

        # Capture token via network interception
        captured = {
            "access_token": None,
            "refresh_token": None,
            "session_token": None,
            "session_cookie": None,
            "auth_mode": None,
            "cookie_header": None,
            "all_cookies": [],
            "leonardo_cookies": [],
            "user_info": None,
        }

        async def on_request(request):
            url = request.url
            # Capture Authorization header
            auth_header = request.headers.get("authorization", "")
            if auth_header.startswith("Bearer ") and "leonardo" in url.lower():
                token = auth_header.replace("Bearer ", "")
                if not captured["access_token"] or len(token) > len(captured["access_token"]):
                    captured["access_token"] = token
                    print(f"  [TOKEN] Captured bearer token ({len(token)} chars)")

            # Capture from API calls
            if "api.leonardo.ai" in url and auth_header.startswith("Bearer "):
                token = auth_header.replace("Bearer ", "")
                if len(token) > 50:
                    captured["access_token"] = token

        async def on_response(response):
            url = response.url
            # Capture user profile / credit balance
            if "api.leonardo.ai" in url and response.request.method == "GET":
                try:
                    body = await response.json()
                    if isinstance(body, dict):
                        # User profile
                        if "user" in body or "email" in body or "credit" in body:
                            captured["user_info"] = body
                            credits = body.get("credit_balance") or body.get("credits")
                            if credits:
                                print(f"  [CREDITS] Balance: {credits}")
                        # Token refresh response
                        if "access_token" in body or "accessToken" in body:
                            token = body.get("access_token") or body.get("accessToken")
                            captured["access_token"] = token
                            print(f"  [TOKEN] Got from API response ({len(token)} chars)")
                            if body.get("refresh_token") or body.get("refreshToken"):
                                captured["refresh_token"] = body.get("refresh_token") or body.get("refreshToken")
                except:
                    pass

        page.on("request", on_request)
        page.on("response", on_response)

        # Buka Leonardo
        print("Opening Leonardo.ai...")
        await page.goto("https://app.leonardo.ai/", wait_until="domcontentloaded", timeout=60000)

        # Cek apakah sudah login (persistent context)
        if "login" not in page.url.lower():
            print("✅ Already logged in! Capturing auth...")
        else:
            print(f"\n{'='*50}")
            print("📝 LOGIN MANUAL DIBUTUHKAN")
            print(f"{'='*50}")
            print("1. Login pakai Google / Canva / Email")
            print("2. Tunggu sampai masuk dashboard Leonardo")
            print("3. Script akan auto-detect login\n")

            # Tungu sampai login berhasil (URL berubah dari /login ke dashboard)
            print("Menunggu login... (timeout 5 menit)")
            for i in range(300):  # 5 menit
                await asyncio.sleep(1)
                url = page.url

                # Deteksi login berhasil
                if "leonardo.ai" in url and "login" not in url.lower() and "sign" not in url.lower():
                    print(f"\n✅ Login detected! URL: {url}")
                    break

                # Progress setiap 30 detik
                if i % 30 == 0 and i > 0:
                    print(f"  Still waiting... ({i}s) URL: {url[:60]}")

        # Tungu API calls selesai (trigger dengan navigate)
        print("\nTriggering API calls untuk capture token...")
        await asyncio.sleep(3)

        # Navigate ke beberapa halaman untuk trigger API
        for nav_url in [
            "https://app.leonardo.ai/",
            "https://app.leonardo.ai/ai-images",
            "https://app.leonardo.ai/image-generation",
        ]:
            try:
                await page.goto(nav_url, wait_until="domcontentloaded", timeout=20000)
                await asyncio.sleep(3)
            except:
                pass

        # Capture cookies
        cookies = await browser.cookies()
        captured["all_cookies"] = cookies

        # Cari session cookie Leonardo
        for c in cookies:
            if "leonardo" in c.get("domain", ""):
                if "session" in c.get("name", "").lower() or "auth" in c.get("name", "").lower():
                    captured["session_cookie"] = c
                    print(f"  [COOKIE] {c['name']} = {c['value'][:30]}...")

        # Coba ambil token dari localStorage/sessionStorage
        try:
            local_data = await page.evaluate("""() => {
                const data = {};
                for (let i = 0; i < localStorage.length; i++) {
                    const key = localStorage.key(i);
                    data[key] = localStorage.getItem(key);
                }
                return data;
            }""")
            if local_data:
                captured["localStorage"] = local_data
                # Cari token di localStorage
                for key, val in local_data.items():
                    if "token" in key.lower() or "auth" in key.lower() or "session" in key.lower():
                        print(f"  [LOCAL] {key} = {str(val)[:50]}...")
                        # Kalau JSON, parse
                        try:
                            parsed = json.loads(val)
                            if isinstance(parsed, dict):
                                for k in ["access_token", "accessToken", "token", "session"]:
                                    if k in parsed:
                                        captured["access_token"] = captured["access_token"] or parsed[k]
                                        print(f"  [TOKEN] From localStorage.{key}.{k}")
                        except:
                            if len(val) > 50 and not captured["access_token"]:
                                captured["access_token"] = val
        except:
            pass

        # Coba ambil dari sessionStorage
        try:
            session_data = await page.evaluate("""() => {
                const data = {};
                for (let i = 0; i < sessionStorage.length; i++) {
                    const key = sessionStorage.key(i);
                    data[key] = sessionStorage.getItem(key);
                }
                return data;
            }""")
            if session_data:
                captured["sessionStorage"] = session_data
        except:
            pass

        # Screenshot final
        try:
            await page.screenshot(path=str(Path(__file__).parent / "leonardo_dashboard.png"), timeout=10000)
            print("Screenshot saved: leonardo_dashboard.png")
        except Exception as e:
            print(f"Screenshot skipped: {e}")

        # Cek credit balance via API
        if captured["access_token"]:
            print("\nChecking credit balance...")
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
                    print(f"💰 Credit balance: {credits}")
                    if credits is not None:
                        if credits >= 850:
                            print(f"✅ Credit OK: {credits} (expected ≥ 850)")
                        else:
                            print(f"⚠️ Credit LOW: {credits} (expected 850)")
            except Exception as e:
                print(f"Could not check credits via API: {e}")

        await browser.close()

    from leonardo_auto_create import has_captured_auth, has_complete_leonardo_auth, normalize_captured_auth, save_success_account, send_to_server
    normalize_captured_auth(captured)

    # Simpan ke file lokal
    captured["captured_at"] = datetime.now().isoformat()
    captured["source"] = "PC local capture"

    AUTH_FILE.write_text(json.dumps(captured, indent=2, default=str))
    if has_complete_leonardo_auth(captured):
        save_success_account(captured)
    print(f"\n💾 Auth saved to: {AUTH_FILE}")

    # Print summary
    print(f"\n{'='*50}")
    print("CAPTURE SUMMARY")
    print(f"{'='*50}")
    print(f"  Access token: {'✅ ' + str(len(captured['access_token'])) + ' chars' if captured['access_token'] else '❌ NOT FOUND'}")
    print(f"  Refresh token: {'✅' if captured.get('refresh_token') else '❌'}")
    print(f"  Session cookie: {'✅' if captured.get('session_cookie') else '❌'}")
    print(f"  All cookies: {len(captured.get('all_cookies', []))} cookies")
    print(f"  User info: {'✅' if captured.get('user_info') else '❌'}")
    print(f"  Credit balance: {captured.get('credit_balance', '❌')}")
    print(f"  localStorage: {len(captured.get('localStorage', {}))} keys")
    print(f"  sessionStorage: {len(captured.get('sessionStorage', {}))} keys")

    if not has_captured_auth(captured):
        print("\n⚠️ Token tidak tercapture! Coba:")
        print("  1. Pastikan sudah login di dashboard Leonardo")
        print("  2. Refresh halaman / navigate ke image generation")
        print("  3. Run script lagi (session browser tersimpan)")

    # Kirim ke server — coba beberapa metode
    if has_complete_leonardo_auth(captured):
        print(f"\n{'='*50}")
        print("Mengirim bearer ke server VPS...")
        print(f"{'='*50}")
        sent = await send_to_server(captured)
        if sent:
            print("Bearer terkirim ke VPS.")
        else:
            print(f"Bearer gagal dikirim. Auth tersimpan lokal: {AUTH_FILE}")
    elif has_captured_auth(captured):
        print("\nAuth belum lengkap bearer/credit, tidak dikirim ke server.")

    # Legacy sender disabled. Endpoint aktif: /api/bearer/import.
    if False and has_complete_leonardo_auth(captured):
        print(f"\n{'='*50}")
        print("Mengirim auth ke server VPS...")
        print(f"{'='*50}")

        sent = False
        payload = build_server_auth_payload(captured)

        # Metode 1: HTTP direct ke IP:PORT
        if not sent:
            print(f"\n[1/3] Coba HTTP direct {VPS_IP}:{VPS_PORT}...")
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.post(
                        f"{SERVER_URL_HTTP}/api/bearer/import",
                        json=payload,
                        headers={"Content-Type": "application/json"},
                    )
                    if resp.status_code == 200:
                        result = resp.json()
                        print(f"✅ Auth terkirim via HTTP! Response: {result}")
                        sent = True
                    else:
                        print(f"  HTTP error: {resp.status_code}")
            except Exception as e:
                print(f"  HTTP gagal: {e}")

        # Metode 2: HTTPS via domain
        if not sent:
            print(f"\n[2/3] Coba HTTPS leonardo.azkazamdigital.com...")
            try:
                async with httpx.AsyncClient(timeout=15, verify=False) as client:
                    resp = await client.post(
                        f"{SERVER_URL_HTTPS}/api/bearer/import",
                        json=payload,
                        headers={"Content-Type": "application/json"},
                    )
                    if resp.status_code == 200:
                        result = resp.json()
                        print(f"✅ Auth terkirim via HTTPS! Response: {result}")
                        sent = True
                    else:
                        print(f"  HTTPS error: {resp.status_code} {resp.text[:100]}")
            except Exception as e:
                print(f"  HTTPS gagal: {e}")

        # Metode 3: SCP file langsung + curl dari VPS
        if not sent:
            print(f"\n[3/3] Coba SCP + curl via SSH...")
            try:
                import subprocess
                import tempfile

                # Tulis auth ke temp file
                tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
                json.dump(payload, tmp, default=str)
                tmp.close()

                # SCP ke VPS
                print(f"  SCP {tmp.name} → {VPS_IP}...")
                scp_result = subprocess.run(
                    ["sshpass", "-p", VPS_PASS, "scp", "-o", "StrictHostKeyChecking=no",
                     tmp.name, f"{VPS_USER}@{VPS_IP}:/home/ubuntu/leonardo-reverse/data/leonardo_auth_pc.json"],
                    capture_output=True, text=True, timeout=30
                )

                if scp_result.returncode == 0:
                    print("  SCP OK! Mengirim ke API via curl...")
                    # curl dari VPS
                    curl_result = subprocess.run(
                        ["sshpass", "-p", VPS_PASS, "ssh", "-o", "StrictHostKeyChecking=no",
                         f"{VPS_USER}@{VPS_IP}",
                         f"curl -s -X POST http://localhost:{VPS_PORT}/api/bearer/import "
                         f"-H 'Content-Type: application/json' "
                         f"-d @/home/ubuntu/leonardo-reverse/data/leonardo_auth_pc.json"],
                        capture_output=True, text=True, timeout=15
                    )
                    print(f"  curl response: {curl_result.stdout[:200]}")
                    if "ok" in curl_result.stdout.lower():
                        print("✅ Auth terkirim via SCP+SSH!")
                        sent = True
                else:
                    print(f"  SCP gagal: {scp_result.stderr[:100]}")
                    print("  (sshpass mungkin belum install di PC. Install: apt install sshpass)")

                os.unlink(tmp.name)
            except Exception as e:
                print(f"  SCP+SSH gagal: {e}")

        if not sent:
            print(f"\n⚠️ Semua metode gagal. Auth tersimpan lokal: {AUTH_FILE}")
            print("Omku bisa kirim manual:")
            print(f"  scp leonardo_auth.json ubuntu@{VPS_IP}:/home/ubuntu/leonardo-reverse/data/")
            print(f"  lalu di VPS: curl -X POST http://localhost:{VPS_PORT}/api/bearer/import "
                  f"-H 'Content-Type: application/json' -d @/home/ubuntu/leonardo-reverse/data/leonardo_auth.json")

    print(f"\n{'='*50}")
    print("SELESAI! Cek leonardo_auth.json")
    print(f"{'='*50}")


if __name__ == "__main__":
    asyncio.run(capture_auth())
