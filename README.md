# Leonardo Auto Create + Auth Capture

Automated Leonardo.ai account creation and auth token capture.

## Files

- `leonardo_gui.py` — **GUI Desktop (CustomTkinter)** — modern dark theme, tombol, progress, log panel
- `leonardo_auto_create.py` — CLI script (Rich terminal UI) — auto create account + capture auth
- `leonardo_auth_capture.py` — CLI script — capture only (login manual)
- `requirements.txt` — Dependencies
- `README.md` — Dokumentasi

## Flow

```
Firefox Relay → Generate mask email
       ↓
Canva Signup → Enter mask email → Submit
       ↓
Gmail → Open Canva email → Extract OTP
       ↓
Canva OTP → Enter code → Verify
       ↓
Canva Team Invite → Accept (token: SeTQSbn...)
       ↓
Leonardo Login → Canva SSO → Dashboard
       ↓
Capture → Bearer token + Cookies + Credits
       ↓
Send to VPS → Server ready for API calls
```

## Requirements

```bash
pip install -r requirements.txt
playwright install chromium
```

## Usage

### GUI Desktop (Recommended)
```bash
python leonardo_gui.py
```
- Window popup dengan dark theme
- Pilih mode: Auto Create / Capture Only / Headless
- Input field untuk relay email (opsional)
- Progress bar + step indicators
- Log output real-time

### CLI — Full Auto Create
```bash
python leonardo_auto_create.py
```

### CLI — With existing relay email
```bash
python leonardo_auto_create.py --relay-email "mask@mozmail.com"
```

### CLI — Headless mode
```bash
python leonardo_auto_create.py --headless
```

### CLI — Capture only (skip account creation)
```bash
python leonardo_auto_create.py --capture-only
```

## Notes

- Browser profile saved in `browser_profile/` — session persists between runs
- Gmail must be logged in (first run = manual login, then persistent)
- Firefox Relay must be logged in (first run = manual login, then persistent)
- Canva team invite token: `SeTQSbn86mzp4Xh7tnL2LQ`
- Token sent to VPS via 3 methods (HTTP → HTTPS → SCP fallback)
