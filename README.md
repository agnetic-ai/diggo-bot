# DIGGO Miner Bot Automation ⛏️💎

Bot otomasi canggih untuk game penambangan Telegram **DIGGO Miner** (`@Diggominer_bot` / `https://diggo.linkpc.net/`).

Dirancang dengan arsitektur mandiri (*standalone*), ringan, mendukung multi-akun, konfigurasi proxy terpusat, dan berjalan nonstop dengan siklus klaim mining otomatis setiap 8 jam.

---

## 🌟 Fitur Utama

- **Konfigurasi Super Simpel:**
  - Berkas `.env` **murni hanya berisi string data `user=...&hash=...`** (atau `query_id=...&user=...&hash=...`) tanpa perlu menulis variabel `INIT_DATA=` atau mengatur Base URL.
  - Untuk multi-akun, cukup tempel string `initData` berikutnya di baris baru.
- **Otomasi Daily Rewards:**
  - Klaim otomatis **Daily Check-in** harian (`+10 DIGGO`).
  - Klaim otomatis **Daily Streak** Day 1 hingga Day 7 (`+15 DIGGO` per hari aktif).
  - Verifikasi otomatis tugas sosial (Telegram Community `+30 DIGGO`, X Follow `+5`, X Post `+5`).
- **Penambangan & Auto-Claim Tiap 8 Jam:**
  - Membaca telemetri mining secara real-time (Rate per hari, Hashrate TH/s, Energy).
  - Menghitung waktu tunggu presisi hingga cooldown claim berikutnya (`nextClaimAt`).
  - Mode Daemon (`--loop`) otomatis tidur dan bangun tepat waktu untuk mengklaim hasil mining setiap 8 jam tanpa intervensi manual.
- **Dukungan Rotasi Proxy Terpusat (`config.py`):**
  - `none`: Mode langsung (*direct connection*).
  - `tor`: Menggunakan Tor SOCKS5 lokal (`127.0.0.1:9050`) dengan **Stream Isolation** otomatis per akun (`socks5://<account>:diggo@127.0.0.1:9050`).
  - `list`: Rotasi round-robin dari daftar proxy di `PROXY_LIST`.
  - `single`: Menggunakan satu endpoint proxy HTTP/SOCKS5 di `PROXY_URL`.
- **CLI Manager Praktis (`diggo.sh`):**
  - Kontrol daemon background (`start`, `stop`, `restart`, `status`, `once`, `log`).

---

## 📁 Struktur File

```text
diggo-bot/
├── .env                # File akun murni berisi string user=...&hash=... (diabaikan git)
├── .env.example        # Contoh format pengisian .env
├── .gitignore          # Proteksi data rahasia & cache
├── requirements.txt    # Dependensi Python minimal
├── config.py           # Konfigurasi terpusat (Base URL, Proxy, Timing) & parser .env
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

### 2. Isi File `.env`

Buat atau salin file `.env`:

```bash
cp .env.example .env
nano .env
```

Cukup tempelkan string `user=...&hash=...` langsung di dalam `.env`:

```text
user=%7B%22id%22%3A123456789%2C%22first_name%22%3A%22Budi%22%2C%22username%22%3A%22budi519%22%7D&chat_instance=1234567890&chat_type=sender&auth_date=1728000000&hash=abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890
```

> **Untuk Multi-Akun:** Cukup tempel string akun ke-2, ke-3, dst. di baris berikutnya (1 akun per baris). Sistem otomatis membaca semua baris akun dan memberi nama sesuai username masing-masing.

### 3. Pengaturan Proxy & Server (Opsional di `config.py`)

Jika ingin menggunakan proxy Tor atau proxy kustom, cukup buka berkas `config.py`:

```python
# Ubah PROXY_MODE di config.py:
PROXY_MODE = "tor"     # Pilihan: "none" | "tor" | "list" | "single"
PROXY_URL = "socks5://127.0.0.1:9050"
```

---

## 🔍 Cara Mendapatkan String `initData`

1. Buka Telegram Web (`https://web.telegram.org/k/` atau `web.telegram.org/a/`) di browser PC (Chrome / Edge).
2. Buka bot `@Diggominer_bot` dan luncurkan mini app-nya.
3. Tekan tombol `F12` untuk membuka Developer Tools, lalu klik tab **Console**.
4. Ketik perintah berikut lalu tekan Enter:
   ```javascript
   Telegram.WebApp.initData
   ```
5. Salin string yang dihasilkan (diawali `user=...` atau `query_id=...`), lalu tempel langsung ke file `.env`.

---

## 🛠️ Perintah CLI (`diggo.sh`)

Script `diggo.sh` memudahkan pengoperasian bot di server VPS:

```bash
# Berikan izin eksekusi jika baru clone
chmod +x diggo.sh runner.py

# 1. Menjalankan 1 siklus langsung di foreground (testing / cek saldo)
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
