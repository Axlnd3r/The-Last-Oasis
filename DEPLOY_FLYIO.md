# Deploy The Last Oasis ke Fly.io

## Kenapa Fly.io?
- ✅ **Gratis** - 256MB RAM, 3GB storage, always-on
- ✅ **Persistent storage** - SQLite database tetap ada setelah restart
- ✅ **Tidak sleep** - Server always running
- ✅ **Global deployment** - Deploy ke Singapore (fastest for Indonesia)

---

## Langkah-Langkah

### 1. Install Fly CLI

**Windows (PowerShell):**
```powershell
powershell -Command "iwr https://fly.io/install.ps1 -useb | iex"
```

**Mac/Linux:**
```bash
curl -L https://fly.io/install.sh | sh
```

### 2. Login ke Fly.io

```bash
flyctl auth login
```

Ini akan buka browser untuk login. Gratis, tidak perlu kartu kredit untuk free tier.

### 3. Deploy Aplikasi

```bash
# Di folder root project (e:\MONAD)
flyctl launch
```

Saat ditanya:
- **App name**: `the-last-oasis` (atau nama lain)
- **Region**: `sea` (Singapore) - paling dekat dengan Indonesia
- **Would you like to set up a PostgreSQL database?**: **NO**
- **Would you like to set up an Upstash Redis database?**: **NO**
- **Deploy now?**: **YES**

### 4. Buat Persistent Volume untuk Database

```bash
flyctl volumes create oasis_data --region sea --size 1
```

### 5. Set Environment Variables

```bash
flyctl secrets set \
  CHAIN_RPC_URL=https://monad-testnet.drpc.org \
  STATE_ANCHOR_CONTRACT_ADDRESS=0xbfb9ea1285D9aD15BEF814608d3ca3583E65B004 \
  ENTRY_FEE_CONTRACT_ADDRESS=0x09725D8194cd1AaA09AB35eC621f9932914FBcEa \
  ORACLE_PRIVATE_KEY=0xYOUR_ORACLE_PRIVATE_KEY_HERE
```

**PENTING:** Ganti `0xYOUR_ORACLE_PRIVATE_KEY_HERE` dengan oracle private key Anda!

### 6. Deploy Ulang (setelah set secrets)

```bash
flyctl deploy
```

### 7. Cek Status & Logs

```bash
# Cek status
flyctl status

# Lihat logs real-time
flyctl logs

# Buka di browser
flyctl open
```

---

## URL Aplikasi

Setelah deploy, aplikasi Anda akan tersedia di:
```
https://the-last-oasis.fly.dev
```

(atau nama app yang Anda pilih)

---

## Troubleshooting

### Build gagal (out of memory)
Coba deploy ulang:
```bash
flyctl deploy --remote-only
```

### App crash / tidak running
Cek logs:
```bash
flyctl logs
```

### Database hilang setelah restart
Pastikan volume sudah dibuat:
```bash
flyctl volumes list
```

Kalau belum ada, buat volume:
```bash
flyctl volumes create oasis_data --region sea --size 1
```

### Update environment variables
```bash
flyctl secrets set KEY=value
```

---

## Scale (kalau butuh lebih banyak resources)

Free tier: 256MB RAM
Scale ke 512MB (PAID):
```bash
flyctl scale memory 512
```

Scale ke 2 instances (PAID):
```bash
flyctl scale count 2
```

---

## Useful Commands

```bash
# SSH ke container
flyctl ssh console

# Restart app
flyctl apps restart

# Destroy app (hapus semua)
flyctl apps destroy the-last-oasis

# Monitor real-time
flyctl dashboard
```

---

## Cost

**Free tier includes:**
- Up to 3 shared-cpu-1x 256mb VMs
- 3GB persistent volume storage
- 160GB outbound data transfer

Selama Anda hanya pakai 1 VM 256MB + 1GB volume = **GRATIS SELAMANYA** ✅
