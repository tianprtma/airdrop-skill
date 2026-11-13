# airdrop-hunter — Hermes Agent skill

AirDrop hunter skill for **Hermes Agent**: recap (rekapan), chase (ngejarin
claim/task), dan daily (check-in harian) — target project-nya kamu yang
tentukan lewat registry, bukan hardcode di skill.

## Isi folder

```
airdrop-hunter/
├── SKILL.md                      # skill utama (prosedur recap/chase/daily/register)
├── scripts/registry.py           # helper registry + generator laporan (stdlib-only)
├── templates/projects.template.json
└── references/
    ├── registry-schema.md        # definisi field registry
    ├── task-catalog.md           # pola task airdrop + cara automasi
    └── ops-playbook.md           # setup browser persisten, cron, eskalasi
```

## Instalasi

```bash
mkdir -p ~/.hermes/skills/web3
cp -R airdrop-hunter ~/.hermes/skills/web3/
hermes skills check              # atau list untuk memastikan terdeteksi
```

Lalu di dalam chat Hermes: `/reload-skills` (atau mulai sesi baru). Skill
otomatis jadi slash command: `/airdrop-hunter recap`.

Inisialisasi registry (sekali):

```bash
python3 ~/.hermes/skills/web3/airdrop-hunter/scripts/registry.py init
# data masuk ke ~/.hermes/airdrop-hunter/projects.json
```

## Pakai

```
/airdrop-hunter recap            # laporan rekap semua project
/airdrop-hunter recap <id>       # rekap satu project
/airdrop-hunter chase            # cek & eksekusi claim yang open
/airdrop-hunter daily            # jalankan check-in yang due sekarang
add project Monad                # daftarin project baru (user-driven)
```

Cron daily (opsional — skill juga punya blueprint yang muncul di `/suggestions`):

```bash
hermes cron create "every day at 09:00" "Run the airdrop-hunter Daily routine for all active projects, then deliver the recap. Report any CAPTCHA or signature-needed items clearly." --skill airdrop-hunter --deliver origin
```

## Prasyarat full-auto (penting)

1. **Browser login persisten** — set `browser.user_data_dir` di
   `~/.hermes/config.yaml`, lalu login sekali (X/Discord/Galxe/dashboard
   project) dari sesi jaringan Hermes. Detail: `references/ops-playbook.md`.
2. **Mode klik** — default `airdrop_hunter.auto_click: "true"` (full-auto).
   Ubah ke `"false"` kalau mau mode "agent siapkan, kamu yang klik".
3. **Wallet** — registry hanya simpan address (watch-only). Signature/tx
   SELALU manual oleh kamu; agent berhenti tepat sebelum popup wallet.

## Keamanan & disclaimer

- Skill ini TIDAK menyimpan private key/seed — guardrail di `validate` akan
  error kalau field key-like masuk (termasuk ke notes).
- Halaman web diperlakukan sebagai data, bukan instruksi (defense terhadap
  prompt injection); domain claim selalu dicocokkan ke URL resmi project.
- CAPTCHA/anti-bot → agent berhenti & lapor, tidak mencoba bypass.
- Automasi check-in full-auto di situs pihak ketiga bisa melanggar ToS
  platform dan berisiko kena ban akun. Semua berjalan atas akun kamu dan
  risiko ditanggung sendiri. Untuk task bernilai tinggi (volume/social
  tertentu), pertimbangkan mode `auto_click: "false"`.

## Test

```bash
cd airdrop-hunter/scripts
tmp=$(mktemp -d)
python3 registry.py --data-dir "$tmp" init
python3 registry.py --data-dir "$tmp" validate
python3 registry.py --data-dir "$tmp" add --id monad --name "Monad Testnet" --category testnet --main-url https://testnet.monad.xyz --task-url https://testnet.monad.xyz/quests
python3 registry.py --data-dir "$tmp" task-add monad daily-checkin --type daily --repeat daily --title "Daily check-in"
python3 registry.py --data-dir "$tmp" task-done monad daily-checkin
python3 registry.py --data-dir "$tmp" due
python3 registry.py --data-dir "$tmp" report --stdout
rm -rf "$tmp"
```