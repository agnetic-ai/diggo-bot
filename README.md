# DIGGO Miner Bot Automation ⛏️💎

Bot otomasi canggih, tangguh, dan mandiri untuk game penambangan Telegram **DIGGO Miner** (`@Diggominer_bot` / `https://app.diggocoin.com/`).

Dirancang dengan arsitektur mandiri (*standalone*), ringan, mendukung multi-akun, rotasi IP terisolasi via Tor, penanganan tonton iklan Adsgram lengkap, dan fitur **Auto-Healing Session** (otomatis me-refresh `initData` jika kadaluarsa).

---

## 🌟 Fitur Utama

- **Konfigurasi Super Simpel (`.env` Murni):**
  - Berkas `.env` **murni hanya berisi baris string data `user=...&hash=...`** (atau `query_id=...&user=...&hash=...`) tanpa perlu menulis variabel `INIT_DATA=` atau konfigurasi Base URL.
  - Untuk multi-akun, cukup tempel string `initData` berikutnya di baris baru (1 akun per baris).
- **Auto-Healing Fresh InitData (Anti-Expired):**
  - Parameter `auth_date` pada WebApp Telegram memiliki masa berlaku singkat (~10–15 menit).
  - Jika `initData` di `.env` sudah kadaluarsa (respons HTTP 401 `expired_init_data`), bot secara **otomatis menghubungkan ke berkas `.session` Telethon akun bersangkutan** di `/opt/telegram-multi-account/sessions/`.
  - Bot meminta token `initData` baru dengan timestamp detik sekarang secara *on-the-fly*, memperbarui sesi, dan langsung melanjutkan login tanpa terhenti!
- **Otomasi 5 Kategori Task Utama:**
  1. **Daily Check-in:** Klaim harian otomatis (`+10 DIGGO`).
  2. **Daily Streak:** Klaim berantai Day 1 s/d Day 7 (`+15 DIGGO` + Energy).
  3. **Play Game:** Deteksi status leveling dan klaim reward game (`+10 DIGGO`).
  4. **Self-Reported Social:** Eksekusi otomatis tugas sosial (`x_follow`, `x_post`, `community_react`) dengan simulasi jeda server 15 detik dan konfirmasi `attemptId` (`+15 DIGGO`).
  5. **Tonton Iklan (Adsgram Engine):**
     - Emulasi penuh siklus penayangan iklan Adsgram (`blockId: 54249`).
     - Mengirim request materi iklan ke `https://api.adsgram.ai/adv`.
     - Menembak tracking pixel `render` dan `show`.
     - Memutar video iklan dengan timer 16 detik.
     - Menembak tracking pixel `reward` ke server Adsgram untuk memicu *webhook server-to-server* ke backend DIGGO.
     - Menyelesaikan kuota harian (4/4 slot) dan mengklaim seluruh reward (`+40 DIGGO`/hari).
- **Penambangan & Auto-Claim Tiap 8 Jam:**
  - Membaca telemetri mining secara real-time (Rate harian, Hashrate TH/s, Energy).
  - Menghitung waktu tunggu presisi hingga cooldown klaim berikutnya (`nextClaimAt`).
  - Mode Daemon (`--loop`) otomatis tidur dan bangun tepat waktu untuk mengklaim hasil mining setiap 8 jam.
- **Rotasi IP Otomatis (Tor Stream Isolation):**
  - Menggunakan Tor SOCKS5 lokal (`127.0.0.1:9050`) secara default (`PROXY_MODE = "tor"`).
  - Setiap akun mendapatkan sirkuit dan **Exit IP unik** melalui format autentikasi stream isolation `socks5://<username>:diggo@127.0.0.1:9050`.
  - Mendukung juga mode proxy kustom: `none`, `list` (round-robin), atau `single`.
- **CLI Manager Praktis (`diggo.sh`):**
  - Kontrol daemon background (`start`, `stop`, `restart`, `status`, `once`, `log`).
- **Alat Ekstraksi Massal (`export_all_init_data.py`):**
  - Skrip otomatis untuk mengekstrak `initData` dari puluhan file session Telegram sekaligus ke dalam file `.env`.

---

## 📁 Struktur File

```text
diggo-bot/
├── .env                     # Berkas akun murni berisi string user=...&hash=... (diabaikan git)
├── .env.example             # Contoh format pengisian .env
├── .gitignore               # Proteksi kredensial, session, dan file privat
├── requirements.txt         # Dependensi Python minimal (httpx, telethon, python-dotenv)
├── config.py                # Konfigurasi terpusat (Base URL, Proxy, Task filters, Parser)
├── client.py                # Engine API DIGGO & Adsgram (Auth, Auto-refresh, Tasks, Mining)
├── runner.py                # Orkestrator & scheduler (mode once & loop 8 jam)
├── diggo.sh                 # CLI shell script manajemen service (start/stop/status/once/log)
├── export_all_init_data.py  # Skrip pembantu ekstraksi massal dari session Telethon
└── README.md                # Dokumentasi lengkap berbahasa Indonesia
```

---

## 📋 Prasyarat

- Python 3.10 atau versi lebih baru
- `pip` atau `uv`
- Tor Service (sudah aktif di port 9050 untuk rotasi IP)

---

## 🚀 Panduan Penggunaan di VPS

### 1. Masuk ke Direktori Bot

```bash
cd /opt/diggo-miner
```

### 2. Format File `.env`

File `.env` murni hanya berisi satu baris string data per akun:

```text
user=%7B%22id%22%3A7401736174%2C%22first_name%22%3A%22Baba%22%2C%22username%22%3A%22baba_turbo%22%7D&chat_instance=1234567890&chat_type=sender&auth_date=1728000000&hash=abcdef1234567890...
user=%7B%22id%22%3A6926143028%2C%22first_name%22%3A%22Rojak%22%2C%22username%22%3A%22rojak038%22%7D&chat_instance=9876543210&chat_type=sender&auth_date=1728000000&hash=123456abcdef...
```

> **Catatan Auto-Healing:** Anda tidak perlu khawatir jika string `initData` di `.env` sudah berusia lebih dari 15 menit. Selama file `.session` Telethon tersedia di `/opt/telegram-multi-account/sessions/`, bot akan otomatis mendeteksi status `expired_init_data` dan mengambil token baru secara langsung!

---

## 🛠️ Perintah CLI (`diggo.sh`)

Gunakan script `diggo.sh` untuk menjalankan bot:

```bash
# 1. Menjalankan 1 siklus langsung di foreground (Testing & cek saldo)
./diggo.sh once

# 2. Menjalankan bot di background (Daemon auto-claim loop 8 jam nonstop)
./diggo.sh start

# 3. Memeriksa status proses dan ringkasan saldo akun
./diggo.sh status

# 4. Memantau live log output
./diggo.sh log

# 5. Menghentikan bot background
./diggo.sh stop

# 6. Merestart bot background
./diggo.sh restart
```

---

## 🔄 Alat Ekstraksi Massal Akun (`export_all_init_data.py`)

Jika Anda memiliki banyak file `.session` Telegram dan ingin memperbarui seluruh isi `.env` secara serentak dalam satu perintah:

```bash
./export_all_init_data.py
```
*Skrip akan memindai seluruh sesi di folder session (secara ketat mengabaikan akun utama seperti `ombengz`), mengambil `initData` resmi terbaru, dan menyusunnya rapi di file `.env`.*

---

## ⚙️ Menjalankan sebagai Systemd Service (Opsional 24/7)

Jika ingin bot otomatis berjalan saat VPS baru menyala (*reboot*):

1. Buat file service:
   ```bash
   sudo nano /etc/systemd/system/diggo-miner.service
   ```
2. Salin konfigurasi berikut:
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
