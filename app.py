"""
===========================================================
LELIXIR AI AGENT v2.4
===========================================================
- Garansi 30 Hari Pasti Langsing + tracking check-in
- Auto follow-up hari ke-3 dan ke-10
- Database SQLite
- Model: claude-sonnet-4-6
===========================================================
"""

from flask import Flask, request, jsonify
import requests
import os
import json
import random
import sqlite3
import threading
import time
from datetime import datetime, timedelta

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
FONNTE_API_KEY = os.environ.get("FONNTE_API_KEY", "")
ADMIN_WA_NUMBER = os.environ.get("ADMIN_WA_NUMBER", "628xxxxxxxxxx")

FOLLOWUP_HARI_3 = [
    "Hai Kak! Gimana, udah sempat coba Lelixir nya? Di awal-awal biasanya BAB akan terasa lebih sering dan lebih banyak dari biasanya — itu pertanda bagus lho Kak! Artinya proses detoksifikasi usus mulai bekerja. Endapan kotoran yang selama ini menumpuk mulai dikeluarkan. Tetap semangat ya, ini langkah awal yang bagus banget buat tubuh kakak! 💪",
    "Halo Kak! Udah mulai rutin minum Lelixir nya? Kalau di hari-hari pertama kakak merasa BAB jadi lebih sering, tenang aja ya — itu justru tanda positif! Usus kakak sedang dibersihkan dari endapan sisa pencernaan yang mungkin sudah bertahun-tahun menumpuk. Maaf kalau warnanya agak kehitaman dan baunya lebih menyengat — itu normal banget Kak, artinya detox nya jalan. Lanjutkan terus ya! 🙌",
    "Hi Kak! Checking in nih, sudah 3 hari sejak terakhir chat. Semoga Lelixir nya sudah dicoba ya! Efek awal yang paling terasa biasanya pencernaan jadi lebih lancar — BAB lebih rutin dan perut terasa lebih ringan. Itu tandanya double action Lelixir mulai bekerja. Coba rutin 2 minggu ya Kak, biasanya di situ hasilnya mulai kelihatan — badan lebih segar, kulit lebih cerah, dan perut mulai menyusut! Semangat hidup sehat!"
]

FOLLOWUP_HARI_10 = [
    "Hai Kak! Gimana progress nya setelah rutin minum Lelixir? Semoga sudah mulai terasa perutnya lebih ringan ya! Oh iya Kak, kalau stock nya mulai menipis, bisa langsung re-stock biar programnya nggak putus. Karena biasanya setelah 30 hari pemakaian rutin, hasilnya makin kelihatan — banyak customer kita yang lingkar perutnya susut sampai 5-8 cm lho! Cek aja di toko terdekat Kak, sering ada promo flash sale dan free produk!",
    "Halo Kak! Udah hampir 10 hari nih. Kalau kakak rutin konsumsi Lelixir nya, pasti stock nya udah mulai menipis ya? Mungkin bisa mulai re-stock Kak, supaya programnya konsisten. Soalnya dari pengalaman banyak customer, hasil terbaik itu di 30 hari pemakaian rutin — ada yang perutnya susut sampai 8 cm! Coba cek Shopee Mall OWL ya Kak, ada ratusan testimoni dari customer real. Sering ada promo flash sale juga! 💪",
    "Hi Kak! Semoga Lelixir nya sudah terasa manfaatnya ya — perut lebih ringan, pencernaan lebih lancar. Kalau boleh tahu, gimana perkembangannya sejauh ini? Oh iya, kalau stock nya udah mau habis, jangan sampai putus ya Kak — konsistensi itu kuncinya. Biasanya di minggu ke-3 dan ke-4 itu hasilnya makin kelihatan banget. Cek aja marketplace terdekat Kak, sering ada promo flash sale dan bonus produk! Tetap semangat hidup sehat!"
]

DB_PATH = "lelixir_customers.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            nomor TEXT PRIMARY KEY,
            first_chat TEXT,
            last_chat TEXT,
            followup_3_sent INTEGER DEFAULT 0,
            followup_10_sent INTEGER DEFAULT 0
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS garansi (
            nomor TEXT PRIMARY KEY,
            nama TEXT,
            tanggal_daftar TEXT,
            tanggal_mulai TEXT,
            status TEXT DEFAULT 'pending',
            total_checkin INTEGER DEFAULT 0,
            last_checkin_date TEXT,
            streak INTEGER DEFAULT 0
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS checkin_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nomor TEXT,
            tanggal TEXT,
            jumlah_foto INTEGER DEFAULT 0,
            timestamp TEXT
        )
    """)
    conn.commit()
    conn.close()

def catat_customer(nomor):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute("""
        INSERT INTO customers (nomor, first_chat, last_chat, followup_3_sent, followup_10_sent)
        VALUES (?, ?, ?, 0, 0)
        ON CONFLICT(nomor) DO UPDATE SET last_chat = ?
    """, (nomor, now, now, now))
    conn.commit()
    conn.close()

def is_first_chat(nomor):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT first_chat FROM customers WHERE nomor = ?", (nomor,))
    row = c.fetchone()
    conn.close()
    if row is None:
        return True
    first = row[0][:10]
    today = datetime.now().isoformat()[:10]
    return first == today

def get_customers_for_followup(hari, followup_field):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    target_date = (datetime.now() - timedelta(days=hari)).isoformat()[:10]
    c.execute(f"""
        SELECT nomor FROM customers
        WHERE date(first_chat) <= ?
        AND date(first_chat) >= ?
        AND {followup_field} = 0
    """, (target_date, (datetime.now() - timedelta(days=hari+1)).isoformat()[:10]))
    results = [row[0] for row in c.fetchall()]
    conn.close()
    return results

def tandai_followup(nomor, followup_field):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(f"UPDATE customers SET {followup_field} = 1 WHERE nomor = ?", (nomor,))
    conn.commit()
    conn.close()

def get_garansi_status(nomor):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM garansi WHERE nomor = ?", (nomor,))
    row = c.fetchone()
    conn.close()
    if row:
        return {
            "nomor": row[0], "nama": row[1], "tanggal_daftar": row[2],
            "tanggal_mulai": row[3], "status": row[4], "total_checkin": row[5],
            "last_checkin_date": row[6], "streak": row[7]
        }
    return None

def daftar_garansi(nomor, nama):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.now().isoformat()
    mulai = (datetime.now() + timedelta(days=1)).isoformat()[:10]
    c.execute("""
        INSERT INTO garansi (nomor, nama, tanggal_daftar, tanggal_mulai, status, total_checkin, last_checkin_date, streak)
        VALUES (?, ?, ?, ?, 'active', 0, '', 0)
        ON CONFLICT(nomor) DO UPDATE SET nama=?, tanggal_daftar=?, tanggal_mulai=?, status='active', total_checkin=0, last_checkin_date='', streak=0
    """, (nomor, nama, now, mulai, nama, now, mulai))
    conn.commit()
    conn.close()

def catat_checkin(nomor):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    today = datetime.now().isoformat()[:10]
    now = datetime.now().isoformat()
    c.execute("SELECT jumlah_foto FROM checkin_log WHERE nomor = ? AND tanggal = ?", (nomor, today))
    row = c.fetchone()
    if row:
        new_count = row[0] + 1
        c.execute("UPDATE checkin_log SET jumlah_foto = ?, timestamp = ? WHERE nomor = ? AND tanggal = ?",
                  (new_count, now, nomor, today))
    else:
        new_count = 1
        c.execute("INSERT INTO checkin_log (nomor, tanggal, jumlah_foto, timestamp) VALUES (?, ?, 1, ?)",
                  (nomor, today, now))
    garansi = get_garansi_status(nomor)
    if garansi and garansi["status"] == "active":
        last_date = garansi["last_checkin_date"]
        if last_date == today:
            streak = garansi["streak"]
        else:
            yesterday = (datetime.now() - timedelta(days=1)).isoformat()[:10]
            if last_date == yesterday or last_date == "":
                streak = garansi["streak"] + 1
            else:
                streak = 1
        total = garansi["total_checkin"] + 1
        c.execute("UPDATE garansi SET total_checkin=?, last_checkin_date=?, streak=? WHERE nomor=?",
                  (total, today, streak, nomor))
    conn.commit()
    conn.close()
    return new_count

def kirim_wa(nomor_tujuan, pesan):
    try:
        response = requests.post(
            "https://api.fonnte.com/send",
            headers={"Authorization": FONNTE_API_KEY},
            json={"target": nomor_tujuan, "message": pesan, "typing": True},
            timeout=15
        )
        if response.status_code == 200:
            print(f"[OK] Pesan terkirim ke {nomor_tujuan}")
            return True
        else:
            print(f"[ERROR] Fonnte error: {response.status_code}")
            return False
    except Exception as e:
        print(f"[ERROR] Gagal kirim WA: {str(e)}")
        return False

def jalankan_followup():
    while True:
        try:
            now = datetime.now()
            if 9 <= now.hour <= 20:
                print(f"[SCHEDULER] Cek follow-up... {now.strftime('%H:%M')}")
                customers_3 = get_customers_for_followup(3, "followup_3_sent")
                for nomor in customers_3:
                    pesan = random.choice(FOLLOWUP_HARI_3)
                    kirim_wa(nomor, pesan)
                    tandai_followup(nomor, "followup_3_sent")
                    time.sleep(2)
                customers_10 = get_customers_for_followup(10, "followup_10_sent")
                for nomor in customers_10:
                    pesan = random.choice(FOLLOWUP_HARI_10)
                    kirim_wa(nomor, pesan)
                    tandai_followup(nomor, "followup_10_sent")
                    time.sleep(2)
        except Exception as e:
            print(f"[SCHEDULER ERROR] {str(e)}")
        time.sleep(3600)

SYSTEM_PROMPT = """# SYSTEM PROMPT FINAL — AI AGENT LELIXIR v2.4

## IDENTITAS UTAMA

Kamu adalah Health Assistant Lelixir — asisten kesehatan dan customer service WhatsApp resmi Lelixir. Kamu punya 2 skill utama yang switch otomatis, plus bisa handle Program Garansi 30 Hari.

1. SKILL 1 — ADMIN / SALES
2. SKILL 2 — HEALTH ASSISTANT
3. PROGRAM GARANSI 30 HARI PASTI LANGSING

## ATURAN IDENTITAS

- JANGAN PERNAH bilang kamu AI, bot, chatbot, atau sejenisnya
- Kalau ditanya: "Saya Health Assistant Lelixir, siap bantu kakak"
- Keterbatasan file: "Saya memiliki keterbatasan untuk membaca/mengirim file, baik gambar maupun dokumen. Boleh diketik aja ya Kak"
- Tapi untuk PROGRAM GARANSI: kalau customer kirim foto (type bukan text), jawab "Ok terima kasih Kak, foto diterima!" (ini dihitung sebagai check-in harian)

## DESKRIPSI FITUR (hanya kalau DITANYA)

Saya Health Assistant Lelixir — asisten gizi pribadi kakak 24/7. Kayak punya dokter gizi di kantong — tanya kapan aja, dijawab langsung, semua saran disesuaikan kondisi kakak.

Yang bisa dibantu: Meal Plan Personal, Workout Plan, Konsultasi Kondisi Khusus, Edukasi Gula & Insulin, Pendamping Program 30 Hari.

## PRINSIP CHAT

1. 90% chat dari konsumen yang SUDAH BELI. Fokus SUPPORT, bukan jualan.
2. Soft sell setelah beberapa kali chat, bukan chat pertama.
3. Meal plan & workout: SELALU masukkan jadwal Lelixir di awal.
   - Target 1-6 kg: 1 sachet/hari (setelah makan siang)
   - Target 7 kg+: 2 sachet/hari (setelah makan siang + makan malam)
4. Akhiri chat dengan SEMANGAT dan MOTIVASI.

## PROGRAM GARANSI 30 HARI PASTI LANGSING

### Kapan Tawarkan Program Garansi:
1. SETELAH menjawab pertanyaan PERTAMA dari customer baru — tambahkan di akhir jawaban:
   "Oh iya Kak, kita juga punya Program 30 Hari Pasti Langsing dengan garansi uang kembali lho! Mau tau lebih lanjut?"

2. Kalau customer tanya soal jaminan/garansi hasil, misalnya: "ada garansi nggak?", "kalau nggak kurus gimana?", "apa ada jaminan uang kembali?" — langsung jelaskan program garansi.

### Cara Jelaskan Program:
"Kita punya Program 30 Hari Pasti Langsing dengan GARANSI UANG KEMBALI! Kalau kakak disiplin 30 hari dan hasilnya nol — uang kembali 100%.

Syaratnya simpel:
1. Beli 3 Box Lelixir (30 sachet untuk 30 hari)
2. Kirim foto stock 3 box + resi belanja Shopee ke chat ini
3. Daftarkan nama lengkap kakak + Kirim foto Timbangan BB dan Lingkar perut
4. Mulai besok setelah pendaftaran, setiap hari selama 30 hari kirim 4 foto:
   - Foto sarapan pagi
   - Foto makan siang
   - Foto makan malam
   - Foto 1 sachet Lelixir yang sudah dibuka/habis
5. Pengiriman foto TIDAK BOLEH PUTUS — kalau 1 hari saja tidak kirim, garansi gugur
6. Setelah 30 hari, kirim foto timbangan atau ukur lingkar perut

Kalau berat badan tidak turun minimal 1 kg ATAU lingkar perut tidak susut minimal 1 cm, uang 3 box dikembalikan 100%!

Garansi gugur jika: ada 1 hari atau lebih yang tidak kirim 4 foto lengkap, atau program tidak dijalankan 30 hari penuh berturut-turut.

Mau ikut Kak?"

### Kalau Customer Bilang MAU:
"Siap Kak! Untuk daftar, tolong kirimkan:
1. Foto stock 3 box Lelixir kakak
2. Foto resi belanja dari Shopee
3. Nama lengkap kakak

Setelah itu saya akan konfirmasi pendaftarannya dan program dimulai besok ya!"

### Kalau Customer Kirim Nama:
"Terima kasih Kak [NAMA]! Pendaftaran Program 30 Hari Pasti Langsing sudah dicatat. Program kakak dimulai BESOK ya! Mulai besok, jangan lupa kirim 4 foto setiap hari. Semangat Kak, 30 hari dari sekarang kakak pasti lihat hasilnya!"

### Kalau Customer Kirim Foto (check-in harian):
Cukup jawab: "Ok terima kasih Kak, foto diterima!"
Jangan jawab panjang-panjang setiap kali kirim foto — cukup konfirmasi singkat.

### Kalau Customer Tanya Progress Garansi:
Sampaikan berapa hari sudah check-in dan berapa hari tersisa. Kasih semangat.

---

# SKILL 1: ADMIN / SALES

## GAYA
Hangat, antusias, TIDAK pushy. Support first, sell later.

## HARGA
- 1 Box (10 sachet) = Rp 145.000
- 2 Box (20 sachet) = Rp 285.000
- 3 Box (30 sachet) = Rp 425.000 — PALING RECOMMENDED

## LINK PEMBELIAN

SETIAP kasih link: "Cek aja dulu Kak, sering ada promo flash sale dan free produk dari masing-masing toko!"

JAKARTA:
Jakarta Selatan:
- Spencer Mealblend Store: https://s.shopee.co.id/9ALdD7gJI8
- Mealblend Store: https://s.shopee.co.id/20sSgZn5yr

Jakarta Barat:
- Hotto Purto Official Jakbar: https://s.shopee.co.id/7VDPEOPBXg
- Spencers Mealblend: https://s.shopee.co.id/3B4Q4efrzq

Jakarta Utara:
- Purnomo Jaya Store: https://s.shopee.co.id/902D10RiTH
- Hotto_id (Tokopedia): https://s.shopee.co.id/20sSgZn5yr

SURABAYA:
Surabaya Timur: Lala Healthy Shop: https://s.shopee.co.id/3g0gf3iVQE
Surabaya Barat: Healthy Mealblend: https://s.shopee.co.id/9zukCuzXzV
Surabaya (Shopee Mall): OWL Mall: https://s.shopee.co.id/8V5wQ0na9y

YOGYAKARTA / JAWA TENGAH:
242you: https://s.shopee.co.id/6Ai1e2oWVx

## HANDLE KOMPETITOR

JANGAN jelek-jelekkan. Jawab: "Lelixir ini Double Action Kak — satu-satunya yang fokus ke lingkar perut dengan Metabolism Booster + Detox Usus sekaligus. Hasilnya lebih cepat terasa."
Dibanding obat diet: "Lelixir bukan obat ya Kak, cara kerjanya relatif lebih aman dan holistik secara alami."

## REBOUND / YO-YO EFFECT

"Lelixir kecilkan lingkar perut dengan memperbaiki DASAR nya — pencernaan dan metabolisme. Bukan penekan nafsu makan atau blocker, jadi hasilnya lebih sustainable. Tapi tetap jaga pola makan dan aktivitas ya Kak."

## KETERGANTUNGAN

"Bahan Lelixir itu alami, bantu kinerja usus dan metabolisme. Sama kayak makan buah naga untuk lancarkan BAB — bukan ketergantungan kan? Setelah rutin 1-2 bulan, bisa stop dan minum occasionally aja — misalnya habis makan berlemak atau perut bloated."

## LEGALITAS

- No BPOM: 272882011400050 (cek di https://cekbpom.pom.go.id)
- No Sertifikat Halal: ID32410029283580925 (cek di https://www.halalmui.org)
- Produksi: PT Aimfood Manufacturing Indonesia
- Distribusi: PT Mega Bintang Sembilan

## DISTRIBUTOR / RESELLER
Peluang besar, kurang dari 10 se-Indonesia. ESKALASI ke admin.

## ESKALASI
Detail distributor, customer marah, refund/retur, masalah pengiriman, minta bicara manusia.

---

# SKILL 2: HEALTH ASSISTANT

## TANYA DULU
1. BB dan TB? 2. Kondisi khusus? 3. Target dan aktivitas?

## DISCLAIMER MEDIS
Tutup jawaban kesehatan: Ini saran edukatif ya Kak, bukan pengganti konsultasi dokter.

## DOSIS
- Target 1-6 kg: 1 sachet/hari (setelah makan siang)
- Target 7 kg+: 2 sachet/hari (setelah makan siang + makan malam)

## FAKTA DETOX USUS (customer baru)
- Usus simpan endapan 2-10 kg bertahun-tahun
- Awal konsumsi: warna kehitaman, bau menyengat — NORMAL
- Endapan ini bikin asam lambung berlebih
- Rutin 2 minggu: badan segar, kulit cerah, perut menyusut
- Cek testimoni Shopee Mall OWL

## PRODUK
LELIXIR, ready-to-drink Blackcurrant, 1 box = 10 sachet @30ml, Rp 145.000, BPOM MD, HALAL, HACCP, 15 kkal, 2g gula (Stevia). Double Action: Metabolism Booster + Detox Usus.

## INGREDIENTS
Metabolism Booster: L-Carnitine, Guarana Extract, Green Tea Extract (EGCG).
Detox Usus: Polydextrose, Inulin, Aloe Vera, Prune Extract, Spirulina Biru.
Pendukung: Blackcurrant 11.25%, Red Beet, Mushroom Extract, Vitamin & Mineral Premix, Steviol Glycosides.

## CARA KONSUMSI
Setelah makan siang/malam, 15-30 menit setelah makan. Jangan perut kosong, jangan campur kopi.

## KONDISI KHUSUS
Hamil/Menyusui: TIDAK DISARANKAN. Maag: AMAN setelah makan. Hipertensi terkontrol: boleh, monitor. Diabetes: gula rendah, serat positif.

## NUTRISI
1. BATASI GULA 2. KURANGI KARBO OLAHAN 3. SERAT KUNCI 4. INTERMITTENT FASTING 5. PROTEIN CUKUP 6. AIR PUTIH 2L/hari
Referensi internal (JANGAN sebut): GGL.

## OLAHRAGA
Level 1-4 dari jalan kaki sampai HIIT. KONSISTENSI > intensitas.

## MEAL PLAN
Jadwal Lelixir DI AWAL. Sarapan: telur+sayur+1/2 karbo. Siang: protein+sayur. Snack: buah. Malam: protein+sayur, karbo minimal. Stop makan jam 19-20.

## FAQ
1-13 (kafein, gula, cara konsumsi, maag, hamil, dll) + rebound + ketergantungan.

## YANG TIDAK BOLEH
- Jangan klaim menyembuhkan penyakit
- Jangan klaim aman untuk hamil/menyusui
- Jangan janji hasil pasti
- Jangan jelek-jelekkan kompetitor
- Jangan jawab di luar topik
- Jangan pesan terlalu panjang
- Jangan sebut GGL
- Jangan langsung jualan di chat pertama
- JANGAN bilang kamu AI/bot"""

app = Flask(__name__)
riwayat_chat = {}
MAKS_RIWAYAT = 20

init_db()


def tanya_claude(nomor_customer, pesan_customer):
    if nomor_customer not in riwayat_chat:
        riwayat_chat[nomor_customer] = []

    riwayat = riwayat_chat[nomor_customer]

    # Tambah konteks garansi jika customer terdaftar
    garansi = get_garansi_status(nomor_customer)
    konteks_garansi = ""
    if garansi and garansi["status"] == "active":
        hari_mulai = garansi["tanggal_mulai"]
        streak = garansi["streak"]
        total = garansi["total_checkin"]
        nama = garansi["nama"]
        konteks_garansi = f"\n[INFO GARANSI] Customer ini ({nama}) terdaftar Program Garansi 30 Hari. Mulai: {hari_mulai}. Total check-in: {total} hari. Streak saat ini: {streak} hari berturut-turut."

    pesan_with_context = pesan_customer + konteks_garansi

    riwayat.append({"role": "user", "content": pesan_with_context})

    if len(riwayat) > MAKS_RIWAYAT:
        riwayat = riwayat[-MAKS_RIWAYAT:]
        riwayat_chat[nomor_customer] = riwayat

    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "content-type": "application/json",
                "anthropic-version": "2023-06-01"
            },
            json={
                "model": "claude-sonnet-4-6",
                "max_tokens": 1024,
                "system": SYSTEM_PROMPT,
                "messages": riwayat
            },
            timeout=60
        )

        if response.status_code == 200:
            data = response.json()
            jawaban = data["content"][0]["text"]
            riwayat.append({"role": "assistant", "content": jawaban})
            riwayat_chat[nomor_customer] = riwayat
            return jawaban
        elif response.status_code == 529:
            # Auto-retry untuk overloaded
            print("[RETRY] Claude overloaded, retrying in 3 seconds...")
            time.sleep(3)
            response2 = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "content-type": "application/json",
                    "anthropic-version": "2023-06-01"
                },
                json={
                    "model": "claude-sonnet-4-6",
                    "max_tokens": 1024,
                    "system": SYSTEM_PROMPT,
                    "messages": riwayat
                },
                timeout=60
            )
            if response2.status_code == 200:
                data = response2.json()
                jawaban = data["content"][0]["text"]
                riwayat.append({"role": "assistant", "content": jawaban})
                riwayat_chat[nomor_customer] = riwayat
                return jawaban
            else:
                print(f"[ERROR] Retry juga gagal: {response2.status_code}")
                return "Maaf Kak, sistem kami sedang sibuk. Coba chat lagi dalam 1-2 menit ya 🙏"
        else:
            print(f"[ERROR] Claude API error: {response.status_code}")
            print(f"[ERROR] Detail: {response.text}")
            return "Maaf Kak, sistem kami sedang maintenance sebentar ya. Coba chat lagi dalam beberapa menit 🙏"

    except requests.exceptions.Timeout:
        return "Maaf Kak, sistem lagi sibuk nih. Coba chat lagi dalam 1-2 menit ya 🙏"
    except Exception as e:
        print(f"[ERROR] Unexpected: {str(e)}")
        return "Maaf Kak, ada gangguan teknis. Coba lagi sebentar ya 🙏"


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json or request.form.to_dict()
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] === PESAN MASUK ===")
    print(f"Data: {json.dumps(data, indent=2, ensure_ascii=False)}")

    nomor_pengirim = data.get("sender", "")
    pesan_masuk = data.get("message", "")

    if not nomor_pengirim or not pesan_masuk:
        return jsonify({"status": "ignored", "reason": "empty"}), 200

    if "@g.us" in nomor_pengirim:
        return jsonify({"status": "ignored", "reason": "group"}), 200

    catat_customer(nomor_pengirim)

    tipe_pesan = data.get("type", "text")

    # Handle foto/media — cek apakah peserta garansi
    if tipe_pesan != "text":
        garansi = get_garansi_status(nomor_pengirim)
        if garansi and garansi["status"] == "active":
            jumlah = catat_checkin(nomor_pengirim)
            if jumlah <= 4:
                kirim_wa(nomor_pengirim, f"Ok terima kasih Kak, foto ke-{jumlah} hari ini diterima! 👍")
            else:
                kirim_wa(nomor_pengirim, "Ok terima kasih Kak, foto diterima! 👍")
            return jsonify({"status": "replied", "type": "garansi-checkin"}), 200
        else:
            kirim_wa(nomor_pengirim,
                     "Saya memiliki keterbatasan untuk membaca/mengirim file, "
                     "baik gambar maupun dokumen. Boleh diketik aja ya Kak pertanyaannya 😊")
            return jsonify({"status": "replied", "type": "non-text"}), 200

    print(f"[INFO] Dari: {nomor_pengirim}")
    print(f"[INFO] Pesan: {pesan_masuk}")

    # Deteksi pendaftaran garansi (customer kirim nama setelah bilang mau)
    pesan_lower = pesan_masuk.lower().strip()
    if any(keyword in pesan_lower for keyword in ["daftar garansi", "ikut program", "nama saya", "nama lengkap saya", "nama:"]):
        # Coba ekstrak nama dari pesan
        nama = pesan_masuk.strip()
        for prefix in ["nama saya ", "nama lengkap saya ", "nama: ", "daftar garansi ", "nama saya: "]:
            if pesan_lower.startswith(prefix):
                nama = pesan_masuk[len(prefix):].strip()
                break
        if len(nama) > 2 and len(nama) < 100:
            daftar_garansi(nomor_pengirim, nama)
            tanggal_mulai = (datetime.now() + timedelta(days=1)).strftime("%d %B %Y")
            kirim_wa(nomor_pengirim,
                     f"Terima kasih Kak {nama}! 🎉\n\n"
                     f"Pendaftaran Program 30 Hari Pasti Langsing sudah dicatat!\n\n"
                     f"Program kakak dimulai BESOK ({tanggal_mulai}) ya.\n\n"
                     f"Mulai besok, kirim 4 foto setiap hari:\n"
                     f"1. Foto sarapan pagi\n"
                     f"2. Foto makan siang\n"
                     f"3. Foto makan malam\n"
                     f"4. Foto sachet Lelixir yang sudah dibuka\n\n"
                     f"30 hari dari sekarang, kakak pasti lihat hasilnya! Semangat! 💪")
            return jsonify({"status": "replied", "type": "garansi-daftar"}), 200

    jawaban = tanya_claude(nomor_pengirim, pesan_masuk)
    print(f"[INFO] Jawaban AI: {jawaban[:100]}...")

    kirim_wa(nomor_pengirim, jawaban)
    return jsonify({"status": "replied"}), 200


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "active",
        "app": "Lelixir AI Agent v2.4",
        "features": "auto-reply + follow-up + garansi 30 hari",
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy"}), 200


@app.route("/garansi-status/<nomor>", methods=["GET"])
def cek_garansi(nomor):
    garansi = get_garansi_status(nomor)
    if garansi:
        return jsonify(garansi), 200
    return jsonify({"error": "Customer tidak terdaftar program garansi"}), 404


if __name__ == "__main__":
    print("=" * 50)
    print("LELIXIR AI AGENT v2.4 — SERVER STARTED")
    print("=" * 50)
    print(f"Model: claude-sonnet-4-6")
    print(f"Claude API: {'OK' if ANTHROPIC_API_KEY else 'NOT SET!'}")
    print(f"Fonnte API: {'OK' if FONNTE_API_KEY else 'NOT SET!'}")
    print(f"Follow-up: Day 3 & Day 10 ACTIVE")
    print(f"Garansi 30 Hari: ACTIVE")
    print("=" * 50)

    scheduler_thread = threading.Thread(target=jalankan_followup, daemon=True)
    scheduler_thread.start()

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
