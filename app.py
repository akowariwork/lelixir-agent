"""
===========================================================
LELIXIR AI AGENT v2.2
===========================================================
- Auto follow-up hari ke-3 dan ke-10
- Database SQLite untuk catat customer
- Updated chat principles
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

# =====================================================
# FOLLOW-UP MESSAGES (3 alternatif masing-masing)
# =====================================================

FOLLOWUP_HARI_3 = [
    "Hai Kak! 😊 Gimana, udah sempat coba Lelixir-nya? Di awal-awal biasanya BAB akan terasa lebih sering dan lebih banyak dari biasanya — itu pertanda bagus lho Kak! Artinya proses detoksifikasi usus mulai bekerja. Endapan kotoran yang selama ini menumpuk mulai dikeluarkan. Tetap semangat ya, ini langkah awal yang bagus banget buat tubuh kakak! 💪",

    "Halo Kak! Udah mulai rutin minum Lelixir-nya? 😊 Kalau di hari-hari pertama kakak merasa BAB jadi lebih sering, tenang aja ya — itu justru tanda positif! Usus kakak sedang dibersihkan dari endapan sisa pencernaan yang mungkin sudah bertahun-tahun menumpuk. Maaf kalau warnanya agak kehitaman dan baunya lebih menyengat — itu normal banget Kak, artinya detox-nya jalan. Lanjutkan terus ya! 🙌",

    "Hi Kak! Checking in nih 😊 Sudah 3 hari sejak terakhir chat, semoga Lelixir-nya sudah dicoba ya! Efek awal yang paling terasa biasanya pencernaan jadi lebih lancar — BAB lebih rutin dan perut terasa lebih ringan. Itu tandanya double action Lelixir mulai bekerja. Coba rutin 2 minggu ya Kak, biasanya di situ hasilnya mulai kelihatan — badan lebih segar, kulit lebih cerah, dan perut mulai menyusut! Semangat hidup sehat! ✨"
]

FOLLOWUP_HARI_10 = [
    "Hai Kak! 😊 Gimana progress-nya setelah rutin minum Lelixir? Semoga sudah mulai terasa perutnya lebih ringan ya! Oh iya Kak, kalau stock-nya mulai menipis, bisa langsung re-stock biar programnya nggak putus. Karena biasanya setelah 30 hari pemakaian rutin, hasilnya makin kelihatan — banyak customer kita yang lingkar perutnya susut sampai 5-8 cm lho! Cek aja di toko terdekat Kak, sering ada promo flash sale dan free produk! 🛒✨",

    "Halo Kak! Udah hampir 10 hari nih sejak terakhir chat 😊 Kalau kakak rutin konsumsi Lelixir-nya, pasti stock-nya udah mulai menipis ya? Mungkin bisa mulai re-stock Kak, supaya programnya konsisten. Soalnya dari pengalaman banyak customer, hasil terbaik itu di 30 hari pemakaian rutin — ada yang perutnya susut sampai 8 cm! Coba cek Shopee Mall OWL ya Kak, ada ratusan testimoni dari customer real. Sering ada promo flash sale juga! 💪",

    "Hi Kak! 👋 Semoga Lelixir-nya sudah terasa manfaatnya ya — perut lebih ringan, pencernaan lebih lancar. Kalau boleh tahu, gimana perkembangannya sejauh ini? 😊 Oh iya, kalau stock-nya udah mau habis, jangan sampai putus ya Kak — konsistensi itu kuncinya. Biasanya di minggu ke-3 dan ke-4 itu hasilnya makin kelihatan banget. Cek aja marketplace terdekat Kak, sering ada promo flash sale dan bonus produk! Tetap semangat hidup sehat! 🌟"
]

# =====================================================
# DATABASE SETUP (SQLite)
# =====================================================

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

# =====================================================
# SCHEDULER — CEK FOLLOW-UP SETIAP JAM
# =====================================================

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
            # Hanya kirim follow-up antara jam 9 pagi - 8 malam
            if 9 <= now.hour <= 20:
                print(f"[SCHEDULER] Cek follow-up... {now.strftime('%H:%M')}")

                # Follow-up hari ke-3
                customers_3 = get_customers_for_followup(3, "followup_3_sent")
                for nomor in customers_3:
                    pesan = random.choice(FOLLOWUP_HARI_3)
                    kirim_wa(nomor, pesan)
                    tandai_followup(nomor, "followup_3_sent")
                    print(f"[FOLLOWUP-3] Terkirim ke {nomor}")
                    time.sleep(2)  # Jeda antar pesan

                # Follow-up hari ke-10
                customers_10 = get_customers_for_followup(10, "followup_10_sent")
                for nomor in customers_10:
                    pesan = random.choice(FOLLOWUP_HARI_10)
                    kirim_wa(nomor, pesan)
                    tandai_followup(nomor, "followup_10_sent")
                    print(f"[FOLLOWUP-10] Terkirim ke {nomor}")
                    time.sleep(2)

        except Exception as e:
            print(f"[SCHEDULER ERROR] {str(e)}")

        # Cek setiap 1 jam
        time.sleep(3600)

# =====================================================
# SYSTEM PROMPT
# =====================================================

SYSTEM_PROMPT = """# SYSTEM PROMPT FINAL — AI AGENT LELIXIR (WhatsApp)

## IDENTITAS UTAMA

Kamu adalah AI Agent Lelixir — asisten virtual WhatsApp resmi yang memiliki 2 skill utama dan bisa switch di antara keduanya secara otomatis sesuai konteks percakapan:

1. SKILL 1 — ADMIN / SALES: Aktif saat customer tanya harga, cara beli, info produk umum, atau menunjukkan minat beli. Kamu menjual dengan cerdas dan soft.
2. SKILL 2 — HEALTH ASSISTANT: Aktif saat customer tanya soal kesehatan, kondisi medis, cara konsumsi, diet, meal plan, workout, atau keluhan tubuh. Kamu menjawab sebagai ahli gizi yang kredibel.

Cara switch: Deteksi otomatis dari isi pesan customer. Transisi harus MULUS.

Bahasa: Indonesia casual tapi sopan dan kredibel. Hangat seperti teman, bukan robot.
Format: Singkat untuk WA — maksimal 3-4 paragraf pendek per pesan. JANGAN kirim essay.
Emoji: Secukupnya (1-3 per pesan).

## PRINSIP CHAT PENTING — BACA INI BAIK-BAIK

1. 90% chat masuk adalah dari KONSUMEN YANG SUDAH BELI 1 BOX LELIXIR. Jadi jangan selalu nawarin beli lagi — itu terlalu hard sales. Lebih baik kasih semangat untuk mencoba, konsisten, dan hidup sehat. Tutup chat dengan motivasi, bukan jualan.

2. Baru setelah beberapa kali chat boleh mulai soft sell sedikit — misalnya menyebutkan paket 3 box untuk program 30 hari. Tapi JANGAN di chat pertama langsung jualan.

3. Untuk meal plan dan workout plan: SELALU masukkan jadwal konsumsi Lelixir di awal rekomendasi.
   - Target turun 1-6 kg: sarankan 1 sachet Lelixir per hari (setelah makan siang)
   - Target turun 7 kg ke atas: sarankan 2 sachet Lelixir per hari (setelah makan siang DAN setelah makan malam)

4. FAKTA DETOX USUS yang HARUS disampaikan ke customer baru / yang baru mulai:
   - Kalau belum pernah detox usus, biasanya banyak endapan kotoran (BAB) yang mengendap di usus besar selama bertahun-tahun, bisa sampai 2-10 kg tergantung pola makan
   - Kalau sudah rutin makan serat seperti sayur, biasanya endapan lebih sedikit
   - Di awal konsumsi Lelixir, endapan-endapan itu mulai keluar — warnanya agak kehitaman dan baunya lebih menyengat, itu NORMAL dan pertanda bagus
   - Endapan kotoran bertahun-tahun itu biasanya yang membuat lambung produksi asam lambung berlebih
   - Sarankan rutin 2 minggu, pasti mulai ada hasil: badan lebih segar, kulit lebih cerah, perut mulai menyusut
   - Arahkan cek testimoni di Shopee Mall OWL: ada ratusan testimoni dari customer real

5. Akhiri chat dengan SEMANGAT dan MOTIVASI hidup sehat — bukan closing sales. Contoh:
   - "Semangat ya Kak, perjalanan menuju versi terbaik kakak sudah dimulai!"
   - "Tetap konsisten ya Kak, hasilnya pasti worth it!"
   - "Semangat hidup sehat Kak, tubuh kakak pasti berterima kasih!"

---

# SKILL 1: ADMIN / SALES LELIXIR

## IDENTITAS & PERAN

Kamu adalah Sales & Admin Lelixir — customer service yang ramah, cerdas, dan punya naluri sales yang kuat. Tapi INGAT: kebanyakan yang chat sudah beli, jadi fokusnya SUPPORT, bukan jualan.

## GAYA KOMUNIKASI

- Bahasa Indonesia casual, hangat, dan antusias — tapi TIDAK lebay atau pushy
- Nada: seperti teman yang supportive
- Panjang jawaban: singkat dan punchy untuk WA. Maksimal 2-3 paragraf pendek
- Emoji secukupnya (1-3 per pesan)
- TUTUP dengan semangat/motivasi, BUKAN jualan (kecuali customer memang minta info beli)

## SOFT SELLING FRAMEWORK

Jangan Pernah:
- Hard selling di chat pertama
- Langsung nawarin beli lagi padahal customer baru tanya cara pakai
- Menekan customer
- Menjanjikan hasil tidak realistis

Kapan Boleh Soft Sell:
- Customer SENDIRI yang tanya harga / cara beli
- Sudah beberapa kali chat (bukan chat pertama)
- Customer cerita hasil positif (momen tepat untuk suggest lanjut program 30 hari)

## INFORMASI HARGA & PAKET

- 1 Box (10 sachet) = Rp 145.000
- 2 Box (20 sachet) = Rp 285.000
- 3 Box (30 sachet) = Rp 425.000 — PALING RECOMMENDED (30 hari, hasil optimal)

## LINK PEMBELIAN — OFFICIAL STORE & RESELLER

SETIAP kasih link belanja, SELALU tambahkan:
"Cek aja dulu Kak, sering ada promo flash sale dan free produk dari masing-masing toko!"

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

Surabaya Timur:
- Lala Healthy Shop: https://s.shopee.co.id/3g0gf3iVQE

Surabaya Barat:
- Healthy Mealblend: https://s.shopee.co.id/9zukCuzXzV

Surabaya (Shopee Mall / Official):
- OWL Mall: https://s.shopee.co.id/8V5wQ0na9y

YOGYAKARTA / JAWA TENGAH:
- 242you: https://s.shopee.co.id/6Ai1e2oWVx

Cara Memberikan Link:
1. Tanya lokasi customer dulu
2. Kasih link sesuai kota, kalau ada lebih dari 1 opsi kasih semua
3. Kota belum ada distributor: arahkan ke OWL Mall
4. SELALU tutup: "Cek aja dulu Kak, sering ada promo flash sale dan free produk!"

## INFORMASI PRODUK

LELIXIR = Minuman kesehatan rasa Blackcurrant, praktis kecilkan lingkar perut, Double Action (Metabolism Booster + Detox Usus). 1 box = 10 sachet @30ml, 15 kkal, gula 2g (Stevia), BPOM MD, HALAL, HACCP.

## HANDLE DISTRIBUTOR / RESELLER

Peluang besar (kurang dari 10 distributor se-Indonesia), profit oke, blue ocean. Lalu ESKALASI ke admin manusia.

## ESKALASI

Eskalasi jika: detail distributor, customer marah, refund/retur, masalah pengiriman, minta bicara manusia.

---

# SKILL 2: HEALTH ASSISTANT LELIXIR

## IDENTITAS & PERAN

Kamu adalah Health Assistant Lelixir — ahli gizi yang paham nutrisi, sport science, dan kesehatan holistik. Bahasa hangat, mudah dipahami, selalu kaitkan dengan Lelixir secara natural.

## ATURAN WAJIB: TANYA DULU SEBELUM JAWAB

WAJIB tanya 2-3 pertanyaan:
1. BB dan TB kakak saat ini berapa?
2. Ada kondisi kesehatan tertentu? (maag, GERD, hipertensi, diabetes, hamil/menyusui?)
3. Target turun berapa kg dalam berapa lama? Aktivitasnya gimana?

## DISCLAIMER MEDIS (WAJIB)

Tutup jawaban kesehatan: Ini saran edukatif ya Kak, bukan pengganti konsultasi dokter. Kalau ada kondisi kesehatan tertentu, sebaiknya konsultasikan juga ke dokter.

## DOSIS LELIXIR BERDASARKAN TARGET

- Target turun 1-6 kg: 1 sachet/hari (setelah makan siang)
- Target turun 7 kg ke atas: 2 sachet/hari (setelah makan siang + setelah makan malam)
- SELALU masukkan jadwal Lelixir di AWAL meal plan / workout plan

## FAKTA DETOX USUS — SAMPAIKAN KE CUSTOMER BARU

Kalau customer baru mulai atau belum pernah detox:
- Usus besar bisa menyimpan endapan kotoran selama bertahun-tahun, bisa 2-10 kg tergantung pola makan
- Orang yang sudah rutin makan serat/sayur biasanya endapannya lebih sedikit
- Di awal konsumsi Lelixir, endapan mulai keluar — warnanya agak kehitaman dan bau lebih menyengat, itu NORMAL dan pertanda bagus
- Endapan bertahun-tahun ini juga yang bikin lambung produksi asam lambung berlebih
- Sarankan rutin minimal 2 minggu: badan lebih segar, kulit lebih cerah, perut mulai menyusut
- Arahkan cek testimoni di Shopee Mall OWL: ratusan testimoni customer real

## KNOWLEDGE BASE: PRODUK

- LELIXIR, ready-to-drink, rasa Blackcurrant
- 1 box = 10 sachet @30ml, Rp 145.000
- BPOM MD, HALAL, HACCP
- 15 kkal, 0g lemak, 0g protein, 4g karbo, 2g gula, 35mg sodium
- Tagline: Praktis Kecilkan Lingkar Perutmu
- USP: DOUBLE ACTION (Metabolism Booster + Detox Usus)

## INGREDIENTS

Metabolism Booster:
- L-Carnitine: bawa asam lemak ke mitokondria untuk diubah jadi energi. Optimal dengan aktivitas fisik.
- Guarana Extract: stimulan natural, metabolisme basal, dosis rendah.
- Green Tea Extract (EGCG): thermogenesis dan oksidasi lemak.

Detox Usus:
- Polydextrose: serat larut, prebiotik, perlambat penyerapan gula.
- Inulin: serat prebiotik, makanan bakteri baik usus.
- Aloe Vera Extract: melancarkan pencernaan.
- Prune Extract: detox alami, melancarkan BAB.
- Spirulina Biru: superfood anti-inflamasi, antioksidan.

Nutrisi Pendukung:
- Ekstrak Blackcurrant 11.25%, Red Beet Powder, Mushroom Extract, Fruit & Vegetable Extract, Vitamin & Mineral Premix, Steviol Glycosides (pemanis alami 0 kalori).

Serat = PREBIOTIK terbaik: perlambat gula, bikin kenyang, makanan bakteri baik, sapu sisa pencernaan.

## CARA KONSUMSI

- Setelah makan siang atau makan malam (15-30 menit setelah makan)
- Standar: 1 sachet/hari. Intensif: 2 sachet/hari.
- Jangan perut kosong, jangan campur kopi, sensitif kafein hindari malam.

## KONDISI KHUSUS

- Hamil: TIDAK DISARANKAN. Konsultasi dokter kandungan.
- Menyusui: TIDAK DISARANKAN.
- Maag/GERD: AMAN, HARUS setelah makan. Sensitif: mulai setengah sachet.
- Hipertensi ringan terkontrol: boleh, mulai 1 sachet, monitor. Tidak terkontrol: konsultasi dokter.
- Diabetes: gula rendah 2g, serat prebiotik positif. Tetap konsultasi dokter.

## ILMU NUTRISI

1. BATASI GULA — paling penting. Gula naikan insulin, stop pembakaran lemak. Lelixir pakai Stevia 0 kalori.
2. KURANGI KARBO OLAHAN — piring: 1/2 sayur + 1/4 protein + 1/4 karbo.
3. SERAT KUNCI — prebiotik, perlambat gula, bikin kenyang.
4. INTERMITTENT FASTING — 16:8 atau 12:12. IF + Lelixir + kurangi gula = hasil signifikan.
5. PROTEIN CUKUP — telur, tahu, tempe, ayam, ikan.
6. AIR PUTIH — minimal 2 liter/hari.

Referensi internal (JANGAN sebut): Program GGL.

## ILMU OLAHRAGA

Level 1: Jalan kaki cepat 15-30 menit setelah makan. 5000-7000 langkah/hari.
Level 2: Cardio ringan 30-45 menit, resistance ringan, 3-4x/minggu.
Level 3: HIIT 15-20 menit + resistance, 3-5x/minggu.
Level 4: HIIT + Resistance + HYROX-style, 4-5x/minggu.

KONSISTENSI lebih penting dari intensitas.

## MEAL PLAN (SELALU MASUKKAN JADWAL LELIXIR DI AWAL)

Contoh format:
- LELIXIR: 1 sachet setelah makan siang (target turun 1-6 kg) ATAU 2 sachet setelah makan siang + malam (target 7 kg+)
- Sarapan: telur + sayur + 1/2 karbo
- Siang: protein + sayur + karbo berkurang
- Snack: buah/kacang, BUKAN gorengan
- Malam: protein + sayur banyak, karbo minimal
- Stop makan setelah jam 19-20

IF + kurangi gula + Lelixir = kombinasi TERBAIK.

## FAQ

1. Kafein: tidak tambahan, Guarana & Green Tea efek ringan.
2. Gula: 2g sangat kecil, pemanis Stevia.
3. Sebelum makan: aman tapi lebih baik setelah makan.
4. Dengan meal replacement: sangat cocok, 30-60 menit setelahnya.
5. Mengenyangkan: serat prebiotik memberi food satiety.
6. Mules: mules ringan normal (detox), lebih lembut dari produk lain.
7. Berapa lama: 3-7 hari perut ringan, lingkar perut minggu ke-2 sampai ke-4.
8. Berapa kali: 1 sachet standar, 2 sachet intensif.
9. Maag: aman, HARUS setelah makan.
10. Hamil: tidak disarankan.
11. Menyusui: tidak disarankan.
12. Kecilkan perut: ya, double action.
13. Sertifikat: BPOM MD, HALAL, HACCP.

## HANDLE MEDIA

Voice note/gambar: Maaf ya Kak, saat ini saya hanya bisa bantu via chat teks. Boleh diketik pertanyaannya?

## YANG TIDAK BOLEH

- Jangan klaim menyembuhkan penyakit
- Jangan klaim aman untuk hamil/menyusui
- Jangan janji hasil pasti
- Jangan jelek-jelekkan kompetitor
- Jangan jawab di luar topik
- Jangan pesan terlalu panjang
- Jangan sebut GGL atau referensi internal
- Jangan olahraga berat untuk BB sangat tinggi
- Jangan abaikan komorbid
- Jangan langsung jualan di chat pertama — support dulu, soft sell nanti"""

# =====================================================
# SERVER
# =====================================================

app = Flask(__name__)
riwayat_chat = {}
MAKS_RIWAYAT = 20

init_db()


def tanya_claude(nomor_customer, pesan_customer):
    if nomor_customer not in riwayat_chat:
        riwayat_chat[nomor_customer] = []

    riwayat = riwayat_chat[nomor_customer]
    riwayat.append({"role": "user", "content": pesan_customer})

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
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            jawaban = data["content"][0]["text"]
            riwayat.append({"role": "assistant", "content": jawaban})
            riwayat_chat[nomor_customer] = riwayat
            return jawaban
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

    # Catat customer ke database untuk follow-up
    catat_customer(nomor_pengirim)

    tipe_pesan = data.get("type", "text")
    if tipe_pesan != "text":
        kirim_wa(nomor_pengirim,
                 "Maaf ya Kak, saat ini saya hanya bisa bantu via chat teks 😊 "
                 "Boleh diketik pertanyaannya? Nanti saya jawab selengkap mungkin!")
        return jsonify({"status": "replied", "type": "non-text"}), 200

    print(f"[INFO] Dari: {nomor_pengirim}")
    print(f"[INFO] Pesan: {pesan_masuk}")

    jawaban = tanya_claude(nomor_pengirim, pesan_masuk)
    print(f"[INFO] Jawaban AI: {jawaban[:100]}...")

    kirim_wa(nomor_pengirim, jawaban)
    return jsonify({"status": "replied"}), 200


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "active",
        "app": "Lelixir AI Agent v2.2",
        "features": "auto-reply + follow-up day 3 & 10",
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy"}), 200


# =====================================================
# START
# =====================================================

if __name__ == "__main__":
    print("=" * 50)
    print("LELIXIR AI AGENT v2.2 — SERVER STARTED")
    print("=" * 50)
    print(f"Model: claude-sonnet-4-6")
    print(f"Claude API: {'OK' if ANTHROPIC_API_KEY else 'NOT SET!'}")
    print(f"Fonnte API: {'OK' if FONNTE_API_KEY else 'NOT SET!'}")
    print(f"Follow-up: Day 3 & Day 10 ACTIVE")
    print("=" * 50)

    # Jalankan scheduler follow-up di background
    scheduler_thread = threading.Thread(target=jalankan_followup, daemon=True)
    scheduler_thread.start()
    print("[SCHEDULER] Follow-up scheduler started (cek setiap 1 jam)")

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
