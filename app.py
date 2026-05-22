"""
===========================================================
LELIXIR AI AGENT v2.5
===========================================================
- Garansi 30 Hari + follow-up hari ke-30 + claim flow
- Auto follow-up hari ke-3 dan ke-10
- Auto-retry untuk overloaded
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
    "Halo Kak! Udah mulai rutin minum Lelixir nya? Kalau di hari-hari pertama kakak merasa BAB jadi lebih sering, tenang aja ya — itu justru tanda positif! Usus kakak sedang dibersihkan dari endapan sisa pencernaan yang mungkin sudah bertahun-tahun menumpuk. Lanjutkan terus ya! 🙌",
    "Hi Kak! Checking in nih, sudah 3 hari sejak terakhir chat. Semoga Lelixir nya sudah dicoba ya! Coba rutin 2 minggu ya Kak, biasanya di situ hasilnya mulai kelihatan — badan lebih segar, kulit lebih cerah, dan perut mulai menyusut! Semangat hidup sehat!"
]

FOLLOWUP_HARI_10 = [
    "Hai Kak! Gimana progress nya setelah rutin minum Lelixir? Kalau stock nya mulai menipis, bisa langsung re-stock biar programnya nggak putus. Banyak customer kita yang lingkar perutnya susut sampai 5-8 cm dalam 30 hari! Cek aja di toko terdekat Kak, sering ada promo flash sale dan free produk!",
    "Halo Kak! Kalau kakak rutin konsumsi Lelixir nya, pasti stock nya udah mulai menipis ya? Dari pengalaman banyak customer, hasil terbaik itu di 30 hari pemakaian rutin — ada yang perutnya susut sampai 8 cm! Cek Shopee Mall OWL ya Kak, sering ada promo flash sale! 💪",
    "Hi Kak! Semoga Lelixir nya sudah terasa manfaatnya ya. Kalau stock nya udah mau habis, jangan sampai putus ya Kak — konsistensi itu kuncinya. Cek marketplace terdekat Kak, sering ada promo flash sale dan bonus produk! Tetap semangat hidup sehat!"
]

FOLLOWUP_GARANSI_30 = [
    "Hai Kak {nama}! 🎉\n\nNggak kerasa ya, udah 30 hari sejak kakak daftar Program Pasti Langsing! Selamat udah konsisten selama sebulan penuh! 💪\n\nGimana Kak, udah turun berapa kg dan berapa cm lingkar perutnya?\n\nTolong kirim:\n1. Foto timbangan terbaru\n2. Foto ukur lingkar perut terbaru\n\nFoto dan progress kakak akan di-review oleh admin ya.\n\nDan yang paling penting — apakah kakak merasa ada progress? Cerita dong! 😊"
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
            streak INTEGER DEFAULT 0,
            followup_30_sent INTEGER DEFAULT 0
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
            "last_checkin_date": row[6], "streak": row[7],
            "followup_30_sent": row[8] if len(row) > 8 else 0
        }
    return None

def get_garansi_for_followup_30():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    target_date = (datetime.now() - timedelta(days=30)).isoformat()[:10]
    c.execute("""
        SELECT nomor, nama FROM garansi
        WHERE date(tanggal_mulai) <= ?
        AND date(tanggal_mulai) >= ?
        AND status = 'active'
        AND followup_30_sent = 0
    """, (target_date, (datetime.now() - timedelta(days=31)).isoformat()[:10]))
    results = [(row[0], row[1]) for row in c.fetchall()]
    conn.close()
    return results

def tandai_garansi_followup_30(nomor):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE garansi SET followup_30_sent = 1 WHERE nomor = ?", (nomor,))
    conn.commit()
    conn.close()

def daftar_garansi(nomor, nama):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.now().isoformat()
    mulai = (datetime.now() + timedelta(days=1)).isoformat()[:10]
    c.execute("""
        INSERT INTO garansi (nomor, nama, tanggal_daftar, tanggal_mulai, status, total_checkin, last_checkin_date, streak, followup_30_sent)
        VALUES (?, ?, ?, ?, 'active', 0, '', 0, 0)
        ON CONFLICT(nomor) DO UPDATE SET nama=?, tanggal_daftar=?, tanggal_mulai=?, status='active', total_checkin=0, last_checkin_date='', streak=0, followup_30_sent=0
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

                # Follow-up hari ke-3
                customers_3 = get_customers_for_followup(3, "followup_3_sent")
                for nomor in customers_3:
                    pesan = random.choice(FOLLOWUP_HARI_3)
                    kirim_wa(nomor, pesan)
                    tandai_followup(nomor, "followup_3_sent")
                    time.sleep(2)

                # Follow-up hari ke-10
                customers_10 = get_customers_for_followup(10, "followup_10_sent")
                for nomor in customers_10:
                    pesan = random.choice(FOLLOWUP_HARI_10)
                    kirim_wa(nomor, pesan)
                    tandai_followup(nomor, "followup_10_sent")
                    time.sleep(2)

                # Follow-up garansi hari ke-30
                garansi_30 = get_garansi_for_followup_30()
                for nomor, nama in garansi_30:
                    pesan = FOLLOWUP_GARANSI_30[0].replace("{nama}", nama)
                    kirim_wa(nomor, pesan)
                    tandai_garansi_followup_30(nomor)
                    print(f"[FOLLOWUP-GARANSI-30] Terkirim ke {nomor} ({nama})")
                    time.sleep(2)

        except Exception as e:
            print(f"[SCHEDULER ERROR] {str(e)}")
        time.sleep(3600)

SYSTEM_PROMPT = """# SYSTEM PROMPT FINAL — AI AGENT LELIXIR v2.5

## IDENTITAS UTAMA

Kamu adalah Health Assistant Lelixir — asisten kesehatan dan customer service WhatsApp resmi Lelixir. Punya 2 skill utama yang switch otomatis, plus handle Program Garansi 30 Hari.

## ATURAN IDENTITAS

- JANGAN PERNAH bilang kamu AI, bot, chatbot, atau sejenisnya
- "Saya Health Assistant Lelixir, siap bantu kakak"
- Keterbatasan file: "Saya memiliki keterbatasan untuk membaca/mengirim file, baik gambar maupun dokumen. Boleh diketik aja ya Kak"
- Peserta garansi kirim foto: "Ok terima kasih Kak, foto diterima!"

## DESKRIPSI FITUR (hanya kalau DITANYA)

Saya Health Assistant Lelixir — asisten gizi pribadi 24/7. Kayak punya dokter gizi di kantong.
Bisa bantu: Meal Plan, Workout Plan, Konsultasi Kondisi Khusus, Edukasi Gula & Insulin, Pendamping Program 30 Hari.

## PRINSIP CHAT

1. 90% chat dari konsumen yang SUDAH BELI. Fokus SUPPORT, bukan jualan.
2. Soft sell setelah beberapa kali chat, bukan chat pertama.
3. Meal plan & workout: jadwal Lelixir DI AWAL.
   - Target 1-6 kg: 1 sachet/hari (setelah makan siang)
   - Target 7 kg+: 2 sachet/hari (setelah makan siang + makan malam)
4. Akhiri chat dengan SEMANGAT dan MOTIVASI.

## FAKTA DETOX USUS (customer baru)
- Usus simpan endapan 2-10 kg bertahun-tahun
- Awal konsumsi: warna kehitaman, bau menyengat — NORMAL
- Endapan ini bikin asam lambung berlebih
- Rutin 2 minggu: badan segar, kulit cerah, perut menyusut
- Cek testimoni Shopee Mall OWL

---

## PROGRAM GARANSI 30 HARI PASTI LANGSING

### Kapan Tawarkan:
1. SETELAH jawab pertanyaan PERTAMA customer baru, tambahkan di akhir:
   "Oh iya Kak, kita juga punya Program 30 Hari Pasti Langsing dengan garansi uang kembali lho! Mau tau lebih lanjut?"

2. Kalau customer tanya: "ada garansi?", "kalau nggak kurus?", "jaminan uang kembali?" — langsung jelaskan.

### Cara Jelaskan:
"Kita punya Program 30 Hari Pasti Langsing dengan GARANSI UANG KEMBALI!

Syaratnya:
1. Beli 3 Box Lelixir (30 sachet untuk 30 hari)
2. Kirim foto stock 3 box + resi belanja Shopee ke chat ini
3. Kirim nama lengkap kakak
4. Kirim foto timbangan (BB saat ini) dan ukur lingkar perut berapa cm saat ini
5. Mulai besok setelah pendaftaran, setiap hari selama 30 hari kirim 4 foto:
   - Foto sarapan pagi
   - Foto makan siang
   - Foto makan malam
   - Foto 1 sachet Lelixir yang sudah dibuka/habis
6. Pengiriman foto TIDAK BOLEH PUTUS — 1 hari tidak kirim, garansi gugur
7. Setelah 30 hari, kirim foto timbangan dan ukur lingkar perut terbaru

Kalau BB tidak turun minimal 1 kg ATAU lingkar perut tidak susut minimal 1 cm, uang 3 box dikembalikan 100%!

Mau ikut Kak?"

### Kalau Customer Bilang MAU:
"Siap Kak! Untuk daftar, tolong kirimkan:
1. Foto stock 3 box Lelixir
2. Foto resi belanja Shopee
3. Nama lengkap kakak
4. Foto timbangan BB saat ini
5. Ukur lingkar perut saat ini (berapa cm)

Setelah lengkap saya konfirmasi pendaftarannya dan program dimulai besok ya!"

### Kalau Customer Kirim Nama (pendaftaran):
Konfirmasi pendaftaran, sebutkan program mulai besok, ingatkan kirim 4 foto setiap hari.

### Kalau Customer Kirim Foto (check-in harian):
Cukup: "Ok terima kasih Kak, foto diterima!"

### Kalau Customer Tanya Progress Garansi:
Sampaikan berapa hari sudah check-in, berapa hari tersisa, kasih semangat.

### SETELAH 30 HARI (follow-up otomatis akan terkirim):
Kalau customer balas dengan hasil/progress: respons dengan antusias, kasih apresiasi, tanya apakah puas.

### Kalau Customer Mau CLAIM Uang Kembali:
"Baik Kak, terima kasih sudah menjalankan programnya selama 30 hari. Foto kakak yang sehari 4x selama 30 hari akan dianalisa oleh Admin ya. Kalau semua syarat terpenuhi, dalam 4 hari ke depan admin akan chat kakak perihal pengembalian uang. Mohon ditunggu ya Kak 🙏"

Lalu ESKALASI ke admin manusia.

### Kalau Customer Puas dengan Hasil:
Respons dengan apresiasi dan semangat! Soft sell: "Kalau mau lanjut programnya supaya hasilnya makin maksimal, bisa re-stock Kak. Cek aja di toko terdekat, sering ada promo flash sale!"

---

# SKILL 1: ADMIN / SALES

## HARGA
- 1 Box (10 sachet) = Rp 145.000
- 2 Box (20 sachet) = Rp 285.000
- 3 Box (30 sachet) = Rp 425.000 — PALING RECOMMENDED

## LINK PEMBELIAN
SETIAP kasih link: "Cek aja dulu Kak, sering ada promo flash sale dan free produk!"

JAKARTA:
Jaksel: Spencer Mealblend Store https://s.shopee.co.id/9ALdD7gJI8 | Mealblend Store https://s.shopee.co.id/20sSgZn5yr
Jakbar: Hotto Purto Official https://s.shopee.co.id/7VDPEOPBXg | Spencers Mealblend https://s.shopee.co.id/3B4Q4efrzq
Jakut: Purnomo Jaya Store https://s.shopee.co.id/902D10RiTH | Hotto_id https://s.shopee.co.id/20sSgZn5yr

SURABAYA:
Sby Timur: Lala Healthy Shop https://s.shopee.co.id/3g0gf3iVQE
Sby Barat: Healthy Mealblend https://s.shopee.co.id/9zukCuzXzV
Sby Mall: OWL Mall https://s.shopee.co.id/8V5wQ0na9y

YOGYAKARTA / JATENG: 242you https://s.shopee.co.id/6Ai1e2oWVx

## KOMPETITOR
JANGAN jelek-jelekkan. "Lelixir Double Action — satu-satunya fokus lingkar perut dengan Metabolism Booster + Detox Usus sekaligus."
Vs obat diet: "Lelixir bukan obat, cara kerjanya lebih aman dan holistik secara alami."

## REBOUND: "Lelixir perbaiki DASAR (pencernaan + metabolisme), bukan penekan nafsu makan, jadi lebih sustainable."

## KETERGANTUNGAN: "Bahan alami, sama kayak buah naga untuk BAB — bukan ketergantungan. Setelah 1-2 bulan rutin, bisa minum occasionally."

## LEGALITAS
- BPOM: 272882011400050 (https://cekbpom.pom.go.id)
- Halal: ID32410029283580925 (https://www.halalmui.org)
- Produksi: PT Aimfood Manufacturing Indonesia
- Distribusi: PT Mega Bintang Sembilan

## ESKALASI: detail distributor, marah, refund, pengiriman, minta manusia, claim garansi.

---

# SKILL 2: HEALTH ASSISTANT

## TANYA DULU: BB/TB, kondisi khusus, target/aktivitas.
## DISCLAIMER: "Ini saran edukatif, bukan pengganti konsultasi dokter."

## PRODUK
LELIXIR, Blackcurrant, 10 sachet @30ml, Rp 145.000, BPOM HALAL HACCP, 15 kkal, 2g gula Stevia. Double Action.

## INGREDIENTS
Booster: L-Carnitine, Guarana, Green Tea EGCG.
Detox: Polydextrose, Inulin, Aloe Vera, Prune, Spirulina.
Pendukung: Blackcurrant, Red Beet, Mushroom, Vitamin Mineral Premix, Steviol Glycosides.

## KONSUMSI: Setelah makan siang/malam, 15-30 menit setelah makan. Jangan perut kosong.
## KONDISI: Hamil/Menyusui TIDAK. Maag AMAN setelah makan. Hipertensi monitor. Diabetes aman.

## NUTRISI: 1.Batasi gula 2.Kurangi karbo 3.Serat kunci 4.IF 5.Protein 6.Air 2L. Ref internal: GGL (jangan sebut).

## OLAHRAGA: Level 1-4, jalan kaki sampai HIIT. Konsistensi > intensitas.

## MEAL PLAN: Jadwal Lelixir di AWAL. Sarapan telur+sayur. Siang protein+sayur. Snack buah. Malam protein+sayur minimal karbo. Stop makan 19-20.

## YANG TIDAK BOLEH
- Jangan klaim menyembuhkan penyakit
- Jangan klaim aman hamil/menyusui
- Jangan janji hasil pasti
- Jangan jelek-jelekkan kompetitor
- Jangan di luar topik
- Jangan terlalu panjang
- Jangan sebut GGL
- Jangan jualan di chat pertama
- JANGAN bilang AI/bot"""

app = Flask(__name__)
riwayat_chat = {}
MAKS_RIWAYAT = 20

init_db()


def tanya_claude(nomor_customer, pesan_customer):
    if nomor_customer not in riwayat_chat:
        riwayat_chat[nomor_customer] = []

    riwayat = riwayat_chat[nomor_customer]

    garansi = get_garansi_status(nomor_customer)
    konteks = ""
    if garansi and garansi["status"] == "active":
        konteks = f"\n[GARANSI] {garansi['nama']}, mulai {garansi['tanggal_mulai']}, check-in {garansi['total_checkin']} hari, streak {garansi['streak']}."

    riwayat.append({"role": "user", "content": pesan_customer + konteks})

    if len(riwayat) > MAKS_RIWAYAT:
        riwayat = riwayat[-MAKS_RIWAYAT:]
        riwayat_chat[nomor_customer] = riwayat

    for attempt in range(3):
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
                print(f"[RETRY {attempt+1}/3] Claude overloaded, tunggu 5 detik...")
                time.sleep(5)
                continue
            else:
                print(f"[ERROR] Claude API: {response.status_code} - {response.text}")
                break

        except requests.exceptions.Timeout:
            print(f"[RETRY {attempt+1}/3] Timeout, tunggu 3 detik...")
            time.sleep(3)
            continue
        except Exception as e:
            print(f"[ERROR] {str(e)}")
            break

    return "Maaf Kak, sistem kami sedang sibuk. Coba chat lagi dalam 1-2 menit ya 🙏"


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json or request.form.to_dict()
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] === PESAN MASUK ===")
    print(f"Data: {json.dumps(data, indent=2, ensure_ascii=False)}")

    nomor_pengirim = data.get("sender", "")
    pesan_masuk = data.get("message", "")

    if not nomor_pengirim or not pesan_masuk:
        return jsonify({"status": "ignored"}), 200

    if "@g.us" in nomor_pengirim:
        return jsonify({"status": "ignored"}), 200

    catat_customer(nomor_pengirim)

    tipe_pesan = data.get("type", "text")

    if tipe_pesan != "text":
        garansi = get_garansi_status(nomor_pengirim)
        if garansi and garansi["status"] == "active":
            jumlah = catat_checkin(nomor_pengirim)
            if jumlah <= 4:
                kirim_wa(nomor_pengirim, f"Ok terima kasih Kak, foto ke-{jumlah} hari ini diterima! 👍")
            else:
                kirim_wa(nomor_pengirim, "Ok terima kasih Kak, foto diterima! 👍")
            return jsonify({"status": "garansi-checkin"}), 200
        else:
            kirim_wa(nomor_pengirim,
                     "Saya memiliki keterbatasan untuk membaca/mengirim file, "
                     "baik gambar maupun dokumen. Boleh diketik aja ya Kak pertanyaannya 😊")
            return jsonify({"status": "non-text"}), 200

    print(f"[INFO] Dari: {nomor_pengirim} | Pesan: {pesan_masuk}")

    pesan_lower = pesan_masuk.lower().strip()
    if any(kw in pesan_lower for kw in ["daftar garansi", "ikut program", "nama saya", "nama lengkap saya", "nama:"]):
        nama = pesan_masuk.strip()
        for prefix in ["nama saya ", "nama lengkap saya ", "nama: ", "daftar garansi ", "nama saya: "]:
            if pesan_lower.startswith(prefix):
                nama = pesan_masuk[len(prefix):].strip()
                break
        if 2 < len(nama) < 100:
            daftar_garansi(nomor_pengirim, nama)
            mulai = (datetime.now() + timedelta(days=1)).strftime("%d/%m/%Y")
            kirim_wa(nomor_pengirim,
                     f"Terima kasih Kak {nama}! 🎉\n\n"
                     f"Pendaftaran Program 30 Hari Pasti Langsing sudah dicatat!\n\n"
                     f"Program dimulai BESOK ({mulai}).\n\n"
                     f"Mulai besok, kirim 4 foto setiap hari:\n"
                     f"1. Foto sarapan pagi\n"
                     f"2. Foto makan siang\n"
                     f"3. Foto makan malam\n"
                     f"4. Foto sachet Lelixir yang sudah dibuka\n\n"
                     f"Ingat: 30 hari tanpa putus ya Kak! Semangat, 30 hari dari sekarang kakak pasti lihat hasilnya! 💪")
            return jsonify({"status": "garansi-daftar"}), 200

    jawaban = tanya_claude(nomor_pengirim, pesan_masuk)
    print(f"[INFO] Jawaban: {jawaban[:100]}...")

    kirim_wa(nomor_pengirim, jawaban)
    return jsonify({"status": "replied"}), 200


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "active",
        "app": "Lelixir AI Agent v2.5",
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
    return jsonify({"error": "Tidak terdaftar"}), 404


if __name__ == "__main__":
    print("=" * 50)
    print("LELIXIR AI AGENT v2.5 — SERVER STARTED")
    print("=" * 50)
    print(f"Model: claude-sonnet-4-6")
    print(f"Claude API: {'OK' if ANTHROPIC_API_KEY else 'NOT SET!'}")
    print(f"Fonnte API: {'OK' if FONNTE_API_KEY else 'NOT SET!'}")
    print(f"Follow-up: Day 3, 10, Garansi-30 ACTIVE")
    print("=" * 50)

    scheduler_thread = threading.Thread(target=jalankan_followup, daemon=True)
    scheduler_thread.start()

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
