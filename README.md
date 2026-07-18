# 11th All India Police Judo Cluster 2026 — Ops Dashboard

**Repo:** [https://github.com/nisalms2026-cell/judo-cluster](https://github.com/nisalms2026-cell/judo-cluster)  
**CISF Host · Hyderabad · LAN + optional free internet View**

Flask dashboard for Accommodation, Mess, Arrival / Departure, and Directory.  
Data lives in local JSON files under `data/` (no database).

---

## Push / update this repo (from the ops PC)

If Git is installed and you are signed in to GitHub:

```bat
cd "C:\Users\TECH-1\Desktop\Judo Cluster\TGPA_Dashboard_LAN"
git init
git add .
git commit -m "Initial commit: Judo Cluster ops dashboard"
git branch -M main
git remote add origin https://github.com/nisalms2026-cell/judo-cluster.git
git push -u origin main
```

If `origin` already exists: `git remote set-url origin https://github.com/nisalms2026-cell/judo-cluster.git`  
Then `git add .` → `git commit -m "..."` → `git push`.

Install Git if needed: https://git-scm.com/download/win (or `winget install --id Git.Git`), then **close and reopen** the terminal.

---

## Architecture (important)

| Role | Port | Who uses it | Internet? |
|------|------|-------------|-----------|
| **VIEW** (read-only) | `5000` | Everyone / teams | Optional — free Cloudflare tunnel |
| **EDIT** (full write) | `5001` | Ops desk only | **Never** expose to the internet |

Both modes read the same `data/` folder. View mode blocks all API writes (`403`).

---

## Setup on a new PC (from GitHub)

### 1. Prerequisites
- Windows 10/11 (scripts are `.bat`; Linux/Mac can run `py` / `python` commands manually)
- [Python 3.10+](https://www.python.org/downloads/) — tick **Add Python to PATH**
- Git

### 2. Clone and install
```bat
git clone https://github.com/nisalms2026-cell/judo-cluster.git
cd judo-cluster
py -m pip install -r requirements.txt
```

### 3. Start the dashboard
Double-click one of:

| File | What it does |
|------|----------------|
| `start_both.bat` | VIEW `:5000` + EDIT `:5001` (recommended for ops PC) |
| `start_view.bat` | VIEW only |
| `start_edit.bat` | EDIT only |

Or from a terminal:
```bat
py app.py --mode view --port 5000
py app.py --mode edit --port 5001
```

Open:
- View: http://localhost:5000  
- Edit: http://localhost:5001  
- On LAN: http://\<this-PC-IP\>:5000 (e.g. `http://192.168.1.92:5000`)

Find your PC IP: `ipconfig` → IPv4 Address.

---

## Free internet View (Edit stays local)

Teams outside the venue can open a public **HTTPS** link. Ops still edit only on this PC / LAN.

**Cost: ₹0** (Cloudflare quick tunnel). Do **not** tunnel port `5001`.

### One-time on each PC — get `cloudflared.exe`
Preferred (reliable on Windows): download into this project folder:

1. Open: https://github.com/cloudflare/cloudflared/releases  
2. Download **`cloudflared-windows-amd64.exe`**  
3. Rename to **`cloudflared.exe`**  
4. Place it in the same folder as `start_internet_view.bat`  
   (`cloudflared.exe` is gitignored — each machine downloads its own copy)

Optional alternative:
```bat
winget install --id Cloudflare.cloudflared
```
Then open a **new** Command Prompt (PATH refresh). Local `cloudflared.exe` in the project folder is still preferred.

### Every time you need a public link
1. Start **VIEW** first: `start_view.bat` or `start_both.bat` (must be on port **5000**)
2. Double-click **`start_internet_view.bat`**
3. Wait for a line like:  
   `https://something-random.trycloudflare.com`
4. **Share only that HTTPS link** with teams  
5. Leave the tunnel window **open**. Close it to stop public access.

### Notes
- The free URL **changes** each time you restart the tunnel  
- This PC must stay on and online  
- Edits on `:5001` appear on View / internet after refresh (same `data/` files)  
- If the bat “crashes” or exits immediately: `cloudflared.exe` is missing — download it into the project folder as above  
- If the public page fails to load: start View on `:5000` first, then re-run the tunnel

---

## Data files

| File | Contents |
|------|----------|
| `data/accommodation.json` | Venues + strength |
| `data/mess.json` | Mess tags + TGPA dining lists |
| `data/arrival.json` | Arrival / departure travel, hubs |
| `data/directory.json` | Managers & phones |
| `data/adm_staff.json` | ADM staff persons, tasks, detailments |
| `data/event.json` | Event meta |

- Arrival plans: `travel` (+ optional `travel_extra`)  
- Departure plans: `travel_departure` (saved from Departure page on Edit)  
- Arrival-only Excel re-import (CLI):  
  `py import_excel.py --arrival "Arrival Plan 17.07.2026.xlsx"`  
  Preserves existing `travel_departure` rows.

Legacy: `event_data.json` / `roster_data.json` may exist from older versions; live ops use `data/*.json`.

---

## Daily ops cheat sheet

1. On the control-room PC: run **`start_both.bat`**
2. Work in **Edit** → http://localhost:5001  
   - Accommodation / Mess / Arrival / Departure / Directory / **ADM Staff**  
   - Departure: same rail / flight / bus planning as Arrival; saves to `travel_departure`
   - **ADM Staff:** onboard persons (CISF No 9 digits, Mobile 10 digits) → create Tasks → Detail persons onto tasks (`data/adm_staff.json`)
3. Share **View** on LAN: http://\<PC-IP\>:5000  
4. Optional internet: run **`start_internet_view.bat`**, share the `https://….trycloudflare.com` link  
5. Before full Excel import on Edit, know it can refresh travel/roster from the workbook — prefer arrival-only import when you only need travel updates

---

## Project layout

```
TGPA_Dashboard_LAN/
  app.py                 Flask server (view / edit modes)
  store.py               Merge / save JSON pages
  import_excel.py        Excel → data/*.json
  index.html             Single-page UI
  requirements.txt
  start_both.bat
  start_view.bat
  start_edit.bat
  start_internet_view.bat
  cloudflared.exe        (local only — not in git)
  data/                  Live JSON (commit if you want shared baseline)
  README.md              This file
```

---

## Checklist — new system

- [ ] Python installed + on PATH  
- [ ] `git clone` + `py -m pip install -r requirements.txt`  
- [ ] `start_both.bat` works locally  
- [ ] Edit `:5001` can save; View `:5000` cannot  
- [ ] (Optional) Download `cloudflared.exe` into project folder  
- [ ] (Optional) `start_internet_view.bat` → copy HTTPS link  
- [ ] Firewall: allow inbound TCP 5000 on LAN if other PCs need View  

---

## Security reminder

- **EDIT is local / LAN only** — never put `:5001` on a tunnel or public URL  
- Internet link (if used) must be **VIEW only** (`:5000`)  
- Anyone with the public View URL can see ops data (strength, phones, travel) — share with intended audience only  
