# DIGGO Miner Bot Automation ⛏️💎

Bot otomasi canggih untuk game penambangan Telegram **DIGGO Miner** (`@Diggominer_bot` / `https://diggo.linkpc.net/`).

Dirancang dengan arsitektur mandiri (*standalone*), ringan, mendukung multi-akun, rotasi proxy opsional (Tor / HTTP / SOCKS5), dan berjalan nonstop dengan siklus klaim mining otomatis setiap 8 jam.

---

## 🌟 Fitur Utama

- **Otomasi Daily Rewards:**
  - Klaim otomatis **Daily Check-in** harian (`+10 DIGGO`).
  - Klaim otomatis **Daily Streak** Day 1 hingga Day 7 (`+15 DIGGO` per hari aktif).
  - Verifikasi otomatis tugas sosial (Telegram Community `+30 DIGGO`, X Follow `+5`, X Post `+5`).
- **Penambangan & Auto-Claim Tiap 8 Jam:**
  - Membaca telemetri mining secara real-time (Rate per hari, Hashrate TH/s, Energy).
  - Menghitung waktu tunggu presisi hingga cooldown claim berikutnya (`nextClaimAt`).
  - Mode Daemon (`--loop`) otomatis tidur dan bangun tepat waktu untuk mengklaim hasil mining setiap 8 jam tanpa intervensi manual.
- **Dukungan Rotasi Proxy Fleksibel:**
  - `none`: Mode langsung (*direct connection*).
  - `tor`: Menggunakan Tor SOCKS5 lokal (`127.0.0.1:9050`) dengan **Stream Isolation** otomatis per akun (`socks5://<account>:diggo@127.0.0.1:9050`) untuk memastikan setiap akun memiliki exit IP unik.
  - `list`: Rotasi round-robin dari daftar proxy di `PROXY_LIST`.
  - `single`: Menggunakan satu endpoint proxy HTTP/SOCKS5.
- **Konfigurasi Berbasis `initData` / `tgWebAppData`:**
  - Cukup masukkan query string `initData` atau URL web app Telegram di file `.env`.
  - Sistem otomatis membersihkan URL lengkap maupun string encoded.
  - Mendukung akun tunggal maupun armada multi-akun (`INIT_DATA_1`, `INIT_DATA_2`, dst, atau array JSON).
- **CLI Manager Praktis (`diggo.sh`):**
  - Kontrol daemon background (`start`, `stop`, `restart`, `status`, `once`, `log`).

---

## 📁 Struktur File

```text
diggo-bot/
├── .env.example        # Template konfigurasi environment
├── .gitignore          # Proteksi data rahasia & cache
├── requirements.txt    # Dependensi Python minimal
├── config.py           # Parser konfigurasi & proxy rotator
├── client.py           # Engine HTTP API DIGGO (auth, daily, streaks, claims)
├── runner.py           # Orkestrator & scheduler (mode once & loop 8 jam)
├── diggo.sh            # CLI shell script untuk manajemen service
└── README.md           # Dokumentasi lengkap
```

---

## 📋 Prasyarat

- Python 3.10 atau versi lebih baru
- `pip` atau `uv`
- Tor Service (opsional, jika ingin mengaktifkan rotasi IP via Tor)

---

## 🚀 Panduan Instalasi & Penggunaan

### 1. Clone Repository & Setup Virtual Environment

```bash
git clone https://github.com/agnetic-ai/diggo-bot.git
cd diggo-bot

# Buat virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependensi
pip install -r requirements.txt
```

### 2. Konfigurasi File `.env`

Salin template `.env.example` menjadi `.env`:

```bash
cp .env.example .env
nano .env
```

Isi parameter yang diperlukan:

```ini
BASE_URL=https://diggo.linkpc.net
DEFAULT_REF=ref_0615dd5877f9bdaa953fc770

# Masukkan initData Telegram akun Anda:
INIT_DATA="query_id=...&user=...&auth_date=...&hash=..."

# Jika multi-akun, tambahkan baris:
# INIT_DATA_2="query_id=...&user=...&hash=..."
# INIT_DATA_3="query_id=...&user=...&hash=..."

# Mode Proxy (none / tor / list / single):
PROXY_MODE=none
PROXY_URL=socks5://127.0.0.1:9050
TOR_PROXY=socks5://127.0.0.1:9050

# Siklus klaim (default 8 jam):
MINING_INTERVAL_HOURS=8
AUTO_DAILY_CHECKIN=true
AUTO_DAILY_STREAK=true
AUTO_TASKS=true
ACCOUNT_DELAY_SECONDS=3
```

---

## 🔍 Cara Mendapatkan `initData` / `tgWebAppData`

1. Buka Telegram Web (`https://web.telegram.org/k/` atau `web.telegram.org/a/`) di Google Chrome / Edge.
2. Buka bot `@Diggominer_bot` dan jalankan mini app-nya.
3. Tekan `F12` untuk membuka Developer Tools, lalu buka tab **Console**.
4. Ketik perintah berikut lalu tekan Enter:
   ```javascript
   Telegram.WebApp.initData
   ```
5. Salin teks hasil yang muncul (dimulai dengan `query_id=...` atau `user=...`) dan tempelkan ke variabel `INIT_DATA` di file `.env`.

---

## 🛠️ Perintah CLI (`diggo.sh`)

Script `diggo.sh` memudahkan pengoperasian bot di server VPS:

```bash
# Berikan izin eksekusi jika baru clone
chmod +x diggo.sh runner.py

# 1. Menjalankan 1 siklus langsung di foreground (uji coba)
./diggo.sh once

# 2. Menjalankan bot di background (daemon loop 8 jam nonstop)
./diggo.sh start

# 3. Memeriksa status proses dan saldo akun terakhir
./diggo.sh status

# 4. Memantau log real-time
./diggo.sh log

# 5. Menghentikan bot background
./diggo.sh stop

# 6. Merestart bot background
./diggo.sh restart
```

---

## ⚙️ Menjalankan via Systemd Service (Opsional 24/7)

Jika ingin menjalankan bot sebagai service otomatis saat server booting:

1. Buat file service:
   ```bash
   sudo nano /etc/systemd/system/diggo-miner.service
   ```
2. Isi konfigurasi berikut:
   ```ini
   [Unit]
   Description=DIGGO Miner Automation Daemon
   After=network.target

   [Service]
   Type=simple
   User=root
   WorkingDirectory=/opt/diggo-miner
   ExecStart=/opt/diggo-miner/.venv/bin/python3 /opt/diggo-miner/runner.py --loop
   Restart=always
   RestartSec=10

   [Install]
   WantedBy=multi-user.target
   ```
3. Aktifkan dan jalankan:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now diggo-miner
   sudo systemctl status diggo-miner
   ```

---

## ⚠️ Disclaimer & Keamanan

- Proyek ini ditujukan untuk tujuan edukasi, otomasi pribadi, dan pengujian keandalan sistem.
- Simpan file `.env` Anda dengan aman dan jangan pernah mengunggah kredensial atau `initData` aktif ke repository publik. File `.gitignore` telah dikonfigurasi secara default untuk mencegah kebocoran data sensitif.
