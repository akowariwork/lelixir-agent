"""
LELIXIR AI AGENT v3.2
Health Assistant — Program Pasti Langsing
PostgreSQL + persistent chat history
"""

from flask import Flask, request, jsonify
import requests, os, random, re, threading, time, psycopg2, psycopg2.extras
from datetime import datetime, timedelta
import pytz

DATABASE_URL      = os.environ.get("DATABASE_URL", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
FONNTE_API_KEY    = os.environ.get("FONNTE_API_KEY", "")
ADMIN_WA_NUMBER   = os.environ.get("ADMIN_WA_NUMBER", "628xxxxxxxxxx")

WIB = pytz.timezone("Asia/Jakarta")

def now_wib():
    return datetime.now(WIB)

def get_conn():
    conn = psycopg2.connect(DATABASE_URL)
    conn.cursor().execute("SET timezone TO 'Asia/Jakarta'")
    conn.commit()
    return conn

# ---------------------------------------------------------------------------
# FOLLOW-UP MESSAGES
# ---------------------------------------------------------------------------

FOLLOWUP_H1 = [
    "Hai! Kemarin sempat chat ya, makasih sudah mampir.\n\nSaya Health Assistant Lelixir — bisa bantu konsultasi soal cara pakai Lelixir, meal plan, tips diet, atau nutrisi kapan aja.\n\nJangan sungkan kalau ada yang mau ditanyain ya.",
    "Halo! Salam kenal, saya Health Assistant Lelixir.\n\nBisa bantu:\n- Konsultasi Lelixir\n- Meal plan sesuai target\n- Tips diet & olahraga simpel\n- Nutrisi & kesehatan umum\n\nAnggap aja teman yang paham gizi — tanya aja.",
    "Hi! Kemarin sempat mampir ya.\n\nSaya Health Assistant Lelixir — siap bantu soal cara pakai Lelixir, meal plan, olahraga ringan, dan nutrisi. 24 jam.\n\nAda yang mau ditanyain?"
]
FOLLOWUP_D3 = [
    "Hai! Udah coba Lelixir?\n\nKalau awal-awal BAB lebih sering atau warna lebih gelap — itu normal, bagian dari proses detoksifikasi usus. Rutin 2 minggu biasanya mulai kerasa lebih enteng dan segar. Semangat ya!",
    "Halo! Udah 3 hari nih. Gimana rasanya?\n\nReaksi awal seperti BAB lebih sering itu tanda usus lagi bersihin diri. Lanjutin rutin ya — hasilnya mulai keliatan di minggu kedua.",
    "Hi! Sudah 3 hari pakai Lelixir. Konsistensi itu kuncinya — rutin 2 minggu pertama biasanya yang paling berasa perubahannya. Semangat!"
]
FOLLOWUP_D10 = [
    "Hai! Gimana progress-nya?\n\nKalau stock mulai menipis, jangan sampai putus ya — konsistensi 30 hari yang bikin hasil optimal. Banyak yang susut 5-8 cm di lingkar perut setelah rutin sebulan.\n\nCek Shopee Mall OWL atau toko terdekat, sering ada flash sale.",
    "Halo! Sudah 10 hari — good job!\n\nStock mau habis? Segera re-stock biar nggak putus. Hasil terbaik di 30 hari rutin. Cek marketplace, sering ada promo.",
    "Hi! 10 hari udah lewat. Kalau stock menipis, jangan tunda re-stock ya — jeda bikin progress mundur. Cek Shopee sering ada flash sale."
]
FOLLOWUP_G_H0 = [
    "Hai {nama}! Program Pasti Langsing kamu resmi mulai hari ini.\n\nInget ya, hari ini harus submit 3 foto:\n1. Foto makan siang (sebelum jam 14.00) + foto sachet Lelixir\n2. Foto makan malam (antara jam 17.00-21.00)\n\nBelum punya meal plan? Chat aja sekarang, langsung saya buatkan untuk 2 hari pertama.",
    "Halo {nama}! Hari pertama program dimulai nih!\n\nJangan lupa 3 foto hari ini:\n- Foto makan siang (sebelum 14.00) — sertakan foto sachet Lelixir\n- Foto makan malam (17.00-21.00)\n\nBelum ada meal plan? Minta sekarang ke saya ya, nanti saya buatkan langsung.",
    "Hi {nama}! Program Pasti Langsing mulai hari ini — semangat!\n\nTarget hari ini: 3 foto (makan siang + sachet Lelixir + makan malam).\n\nMau minta meal plan untuk hari ini dan besok? Chat aja."
]
FOLLOWUP_G30 = [
    "Hai {nama}!\n\n30 hari udah selesai — selamat, itu bukan hal yang gampang!\n\nGimana hasilnya? Turun berapa kg? Kirim foto timbangan terbaru ya (ada HP menyala sebagai timestamp).\n\nFYI — setiap 3 bulan kami adain undian untuk peserta dengan penurunan BB terbanyak. Hadiahnya 3 box Lelixir gratis atau uang Rp 500.000. Jadi catat progress kamu ya!",
    "Halo {nama}! Program 30 hari selesai!\n\nCerita dong — turun berapa kg dan berapa cm? Kirim foto timbangan terbaru kalau bisa (dengan timestamp HP).\n\nInfo: setiap 3 bulan ada undian peserta dengan penurunan terbanyak — hadiahnya 3 box Lelixir atau Rp 500K. Progress kamu masuk hitungan ya."
]
GARANSI_MISS = [
    "Hai {nama},\n\nKemarin foto belum masuk ya. Ini terhitung dispensasi ke-{miss} dari 2 yang diizinkan dalam program.\n\nSantai aja, masih bisa lanjut — yang penting besok submit 3 foto ya. Kalau butuh reminder atau support, chat aja.",
    "Halo {nama}, kemarin missed upload ya.\n\nIni dispensasi ke-{miss}/2. Masih aman lanjut program, tapi jangan sampai terulang lagi ya. Besok pastikan submit 3 foto (makan siang + sachet + makan malam). Semangat!"
]
GARANSI_GUGUR = [
    "Hai {nama},\n\nSayang banget, dispensasi sudah habis (3x missed). Program garansi resmi berakhir.\n\nTapi kamu masih bisa konsultasi kapan aja di sini — dan tetap rutin Lelixir ya. Banyak yang tetap turun meski tanpa program formal, karena pola makannya udah berubah. Semangat terus!"
]

# ---------------------------------------------------------------------------
# DATABASE INIT
# ---------------------------------------------------------------------------

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            nomor TEXT PRIMARY KEY,
            first_chat TIMESTAMPTZ,
            last_chat TIMESTAMPTZ,
            chat_count INTEGER DEFAULT 0,
            followup_h1_sent INTEGER DEFAULT 0,
            followup_3_sent INTEGER DEFAULT 0,
            followup_10_sent INTEGER DEFAULT 0
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS garansi (
            nomor TEXT PRIMARY KEY,
            nama TEXT,
            tanggal_daftar TIMESTAMPTZ,
            tanggal_mulai DATE,
            status TEXT DEFAULT 'active',
            total_checkin INTEGER DEFAULT 0,
            last_checkin_date DATE,
            streak INTEGER DEFAULT 0,
            miss_count INTEGER DEFAULT 0,
            followup_h0_sent INTEGER DEFAULT 0,
            followup_30_sent INTEGER DEFAULT 0,
            miss_notified_dates TEXT DEFAULT ''
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS checkin_log (
            id SERIAL PRIMARY KEY,
            nomor TEXT,
            tanggal DATE,
            jumlah_foto INTEGER DEFAULT 0,
            timestamp TIMESTAMPTZ,
            UNIQUE(nomor, tanggal)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id SERIAL PRIMARY KEY,
            nomor TEXT,
            role TEXT,
            content TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_chat_history_nomor ON chat_history(nomor, created_at)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_checkin_nomor ON checkin_log(nomor, tanggal)")
    conn.commit()
    conn.close()
    print("[DB] Tables ready")

# ---------------------------------------------------------------------------
# CUSTOMERS
# ---------------------------------------------------------------------------

def catat_customer(nomor):
    conn = get_conn()
    c = conn.cursor()
    now = now_wib()
    c.execute("""
        INSERT INTO customers (nomor, first_chat, last_chat, chat_count)
        VALUES (%s, %s, %s, 1)
        ON CONFLICT (nomor) DO UPDATE
        SET last_chat = %s, chat_count = customers.chat_count + 1
    """, (nomor, now, now, now))
    conn.commit()
    conn.close()

# ---------------------------------------------------------------------------
# GARANSI
# ---------------------------------------------------------------------------

def get_garansi(nomor):
    conn = get_conn()
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    c.execute("SELECT * FROM garansi WHERE nomor = %s", (nomor,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def has_garansi(nomor):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT 1 FROM garansi WHERE nomor = %s", (nomor,))
    row = c.fetchone()
    conn.close()
    return row is not None

def reg_garansi(nomor, nama):
    conn = get_conn()
    c = conn.cursor()
    now = now_wib()
    mulai = (now_wib() + timedelta(days=1)).date()
    c.execute("""
        INSERT INTO garansi
            (nomor, nama, tanggal_daftar, tanggal_mulai, status, total_checkin,
             last_checkin_date, streak, miss_count, followup_h0_sent, followup_30_sent, miss_notified_dates)
        VALUES (%s, %s, %s, %s, 'active', 0, NULL, 0, 0, 0, 0, '')
        ON CONFLICT (nomor) DO UPDATE SET
            nama = EXCLUDED.nama,
            tanggal_daftar = EXCLUDED.tanggal_daftar,
            tanggal_mulai = EXCLUDED.tanggal_mulai,
            status = 'active',
            total_checkin = 0,
            last_checkin_date = NULL,
            streak = 0,
            miss_count = 0,
            followup_h0_sent = 0,
            followup_30_sent = 0,
            miss_notified_dates = ''
    """, (nomor, nama, now, mulai))
    conn.commit()
    conn.close()

def checkin(nomor):
    conn = get_conn()
    c = conn.cursor()
    td = now_wib().date()
    now = now_wib()
    c.execute("""
        INSERT INTO checkin_log (nomor, tanggal, jumlah_foto, timestamp)
        VALUES (%s, %s, 1, %s)
        ON CONFLICT (nomor, tanggal) DO UPDATE
        SET jumlah_foto = checkin_log.jumlah_foto + 1, timestamp = %s
        RETURNING jumlah_foto
    """, (nomor, td, now, now))
    nc = c.fetchone()[0]

    g = get_garansi(nomor)
    if g and g["status"] == "active":
        ld = g["last_checkin_date"]
        yesterday = (now_wib() - timedelta(days=1)).date()
        if ld == td:
            s = g["streak"]
        elif ld is None or ld == yesterday:
            s = g["streak"] + 1
        else:
            s = 1
        c.execute("""
            UPDATE garansi SET total_checkin = total_checkin + 1,
            last_checkin_date = %s, streak = %s WHERE nomor = %s
        """, (td, s, nomor))

    conn.commit()
    conn.close()
    return nc

# ---------------------------------------------------------------------------
# CHAT HISTORY (persistent)
# ---------------------------------------------------------------------------

MAKS_RIWAYAT = 20

def get_history(nomor):
    conn = get_conn()
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    c.execute("""
        SELECT role, content FROM chat_history
        WHERE nomor = %s
        ORDER BY created_at DESC
        LIMIT %s
    """, (nomor, MAKS_RIWAYAT))
    rows = c.fetchall()
    conn.close()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

def save_message(nomor, role, content):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO chat_history (nomor, role, content, created_at)
        VALUES (%s, %s, %s, %s)
    """, (nomor, role, content, now_wib()))
    # Cleanup old messages beyond limit
    c.execute("""
        DELETE FROM chat_history WHERE id IN (
            SELECT id FROM chat_history
            WHERE nomor = %s
            ORDER BY created_at DESC
            OFFSET %s
        )
    """, (nomor, MAKS_RIWAYAT))
    conn.commit()
    conn.close()

def cleanup_old_history():
    """Hapus chat history lebih dari 7 hari."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM chat_history WHERE created_at < NOW() - INTERVAL '7 days'")
    conn.commit()
    conn.close()

# ---------------------------------------------------------------------------
# FOLLOW-UP QUERIES
# ---------------------------------------------------------------------------

def get_fu_h1():
    conn = get_conn()
    c = conn.cursor()
    yesterday = (now_wib() - timedelta(days=1)).date()
    c.execute("""
        SELECT nomor FROM customers
        WHERE DATE(first_chat AT TIME ZONE 'Asia/Jakarta') = %s
        AND chat_count <= 3 AND followup_h1_sent = 0
    """, (yesterday,))
    r = [row[0] for row in c.fetchall()]
    conn.close()
    return r

def get_fu(hari, field):
    conn = get_conn()
    c = conn.cursor()
    target = (now_wib() - timedelta(days=hari)).date()
    prev   = (now_wib() - timedelta(days=hari+1)).date()
    c.execute(f"""
        SELECT nomor FROM customers
        WHERE DATE(first_chat AT TIME ZONE 'Asia/Jakarta') <= %s
        AND DATE(first_chat AT TIME ZONE 'Asia/Jakarta') >= %s
        AND {field} = 0
    """, (target, prev))
    r = [row[0] for row in c.fetchall()]
    conn.close()
    return r

def mark_fu(nomor, field):
    conn = get_conn()
    c = conn.cursor()
    c.execute(f"UPDATE customers SET {field} = 1 WHERE nomor = %s", (nomor,))
    conn.commit()
    conn.close()

def get_garansi_h0():
    conn = get_conn()
    c = conn.cursor()
    today = now_wib().date()
    c.execute("""
        SELECT nomor, nama FROM garansi
        WHERE tanggal_mulai = %s AND status = 'active' AND followup_h0_sent = 0
    """, (today,))
    r = [(row[0], row[1]) for row in c.fetchall()]
    conn.close()
    return r

def mark_garansi_h0(nomor):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE garansi SET followup_h0_sent = 1 WHERE nomor = %s", (nomor,))
    conn.commit()
    conn.close()

def get_g30():
    conn = get_conn()
    c = conn.cursor()
    target = (now_wib() - timedelta(days=30)).date()
    prev   = (now_wib() - timedelta(days=31)).date()
    c.execute("""
        SELECT nomor, nama FROM garansi
        WHERE tanggal_mulai <= %s AND tanggal_mulai >= %s
        AND status = 'active' AND followup_30_sent = 0
    """, (target, prev))
    r = [(row[0], row[1]) for row in c.fetchall()]
    conn.close()
    return r

def mark_g30(nomor):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE garansi SET followup_30_sent = 1 WHERE nomor = %s", (nomor,))
    conn.commit()
    conn.close()

def check_miss():
    conn = get_conn()
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    yesterday = (now_wib() - timedelta(days=1)).date()
    c.execute("""
        SELECT nomor, nama, miss_count, miss_notified_dates, tanggal_mulai
        FROM garansi WHERE status = 'active'
    """)
    rows = c.fetchall()
    results = []
    for row in rows:
        nomor = row["nomor"]
        nama  = row["nama"]
        miss_count = row["miss_count"]
        notified   = row["miss_notified_dates"] or ""
        mulai      = row["tanggal_mulai"]

        if mulai > yesterday:
            continue
        if str(yesterday) in notified:
            continue

        c2 = conn.cursor()
        c2.execute("SELECT jumlah_foto FROM checkin_log WHERE nomor = %s AND tanggal = %s", (nomor, yesterday))
        foto_row = c2.fetchone()
        foto = foto_row[0] if foto_row else 0

        if foto < 3:
            new_miss  = miss_count + 1
            new_dates = (notified + "," + str(yesterday)) if notified else str(yesterday)
            if new_miss >= 3:
                c2.execute("UPDATE garansi SET status='failed', miss_count=%s, miss_notified_dates=%s WHERE nomor=%s",
                           (new_miss, new_dates, nomor))
                results.append((nomor, nama, new_miss, True))
            else:
                c2.execute("UPDATE garansi SET miss_count=%s, miss_notified_dates=%s WHERE nomor=%s",
                           (new_miss, new_dates, nomor))
                results.append((nomor, nama, new_miss, False))

    conn.commit()
    conn.close()
    return results

# ---------------------------------------------------------------------------
# WHATSAPP
# ---------------------------------------------------------------------------

def send_wa(nomor, pesan):
    try:
        r = requests.post(
            "https://api.fonnte.com/send",
            headers={"Authorization": FONNTE_API_KEY},
            json={"target": nomor, "message": pesan, "typing": True},
            timeout=15
        )
        if r.status_code == 200:
            print(f"[OK] {nomor}")
            return True
        print(f"[ERR] {r.status_code}")
        return False
    except Exception as e:
        print(f"[ERR] {e}")
        return False

# ---------------------------------------------------------------------------
# SCHEDULER
# ---------------------------------------------------------------------------

def scheduler():
    print("[SCHED] Started")
    while True:
        try:
            now = now_wib()
            if 9 <= now.hour <= 20:
                print(f"[SCHED] {now.strftime('%Y-%m-%d %H:%M')} WIB")

                if now.hour == 9:
                    for nomor, nama, miss_count, gugur in check_miss():
                        if gugur:
                            msg = random.choice(GARANSI_GUGUR).replace("{nama}", nama)
                        else:
                            msg = random.choice(GARANSI_MISS).replace("{nama}", nama).replace("{miss}", str(miss_count))
                        send_wa(nomor, msg)
                        time.sleep(3)
                    cleanup_old_history()

                for nomor, nama in get_garansi_h0():
                    send_wa(nomor, random.choice(FOLLOWUP_G_H0).replace("{nama}", nama))
                    mark_garansi_h0(nomor)
                    time.sleep(3)

                for nomor in get_fu_h1():
                    send_wa(nomor, random.choice(FOLLOWUP_H1))
                    mark_fu(nomor, "followup_h1_sent")
                    time.sleep(3)

                for nomor in get_fu(3, "followup_3_sent"):
                    send_wa(nomor, random.choice(FOLLOWUP_D3))
                    mark_fu(nomor, "followup_3_sent")
                    time.sleep(3)

                for nomor in get_fu(10, "followup_10_sent"):
                    send_wa(nomor, random.choice(FOLLOWUP_D10))
                    mark_fu(nomor, "followup_10_sent")
                    time.sleep(3)

                for nomor, nama in get_g30():
                    send_wa(nomor, random.choice(FOLLOWUP_G30).replace("{nama}", nama))
                    mark_g30(nomor)
                    time.sleep(3)

        except Exception as e:
            print(f"[SCHED ERR] {e}")
        time.sleep(3600)

# ---------------------------------------------------------------------------
# SYSTEM PROMPT
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """# LELIXIR HEALTH ASSISTANT v3.2

## IDENTITAS & PERSONA
Kamu adalah Health Consultant (HC) dari Lelixir. Nama: Health Assistant Lelixir.
JANGAN bilang kamu AI atau bot. Kalau ditanya, bilang "Saya HC dari tim Lelixir."
Bahasa: Indonesia santai, boleh campur sedikit English. Ramah, suportif, nggak lebay.
Emoticon: minimal — maksimal 1-2 per pesan, hanya kalau memang pas.
Jawaban: singkat dan padat. Jangan panjang-panjang kalau nggak perlu.
File/foto: "Saya terbatas baca file di sini, boleh diketik aja ya."

## PRINSIP UTAMA
1. 90% customer sudah beli — fokus ke SUPPORT, bukan jualan.
2. Soft sell boleh, tapi hanya setelah beberapa chat.
3. Lelixir selalu disebut di awal meal plan (sebagai "dessert" pengganti manis).
4. Eskalasi ke admin: SELALU konfirmasi dulu sebelum eskalasi.
5. Disclaimer: "Ini saran edukatif, bukan pengganti konsultasi dokter."

---

## PROGRAM PASTI LANGSING (GARANSI 30 HARI)

### Konsep
Program ini sengaja dibuat ringan supaya bisa dijalankan. Yang penting konsistensi — kalau ikut pola makan + Lelixir rutin, pasti turun.

### Syarat Garansi
- Minimal beli 3 box Lelixir (30 sachet)
- Ada kode unik dari Sales Lia di note pesanan Shopee (sebagai bukti dapat quota)
- 1 orang hanya bisa ikut 1x
- Pengembalian uang = nominal sesuai invoice Shopee (3 box)

### Pendaftaran (urutan)
Customer harus kirim:
1. Nama lengkap
2. Foto timbangan awal — ada kaki + HP menyala (terlihat tanggal sebagai timestamp)
3. Bukti transaksi Shopee (invoice selesai) yang ada kode dari Sales Lia di bagian note

Setelah semua lengkap → konfirmasi nama → kirim tag [DAFTAR_GARANSI:Nama] di akhir response. Satu kali saja. Kalau sudah pernah daftar → tolak dengan ramah.

### Kewajiban Harian (30 hari berturutan)
Submit 3 foto per hari:
- Foto 1: Foto makan SIANG (sebelum jam 14.00) + foto sachet Lelixir dalam 1 foto atau terpisah
- Foto 2: Foto makan MALAM (antara jam 17.00–21.00)

Total = 3 foto/hari (siang + sachet + malam)

### Toleransi Miss
- Miss = hari itu submit < 3 foto
- Dispensasi: 2x dalam 30 hari
- Miss ke-3 → program garansi gugur (tapi tetap bisa konsultasi)

### Mealplan
- HC (kamu) yang buat mealplan
- Format per 2 hari — akhiri dengan "mau lanjut 2 hari berikutnya? tinggal bilang ya"
- Mealplan = panduan/ilustrasi, bukan kewajiban persis. Minimal ikutin 2 dari 3 makan.
- Konsep dasar: banyak protein, kurangi nasi, makan sayur, no gula tambahan, no snacking di jeda makan.

### Kalau Customer Tanya "Foto makan saya udah bener ga?"
Variasikan jawaban dari konsep ini (WAJIB divariasi, jangan copy-paste):
- Untuk review detail, nanti ada admin/nutrisionis yang cek secara berkala
- Yang penting tetap upload — selama foto masuk, program garansi nggak gugur
- Intinya: selama paham konsep (protein cukup, nasi dikurangi, sayur ada, no gula), kamu udah on track
- Pola makan sehat itu tujuannya jadi lifestyle, bukan cuma 30 hari

### Target Garansi
- BB turun minimal 3 kg ATAU lingkar perut susut minimal 3 cm dalam 30 hari
- Kalau tidak tercapai → uang kembali 100% sesuai invoice

### Claim Garansi
Kalau mau claim: konfirmasi dulu ke customer, baru eskalasi ke admin.
"Foto-foto akan dianalisa admin. Proses 4 hari kerja, admin akan chat langsung."

### H+31 — Undian
Setiap 3 bulan ada undian peserta dengan penurunan BB terbanyak.
Hadiah: 3 box Lelixir gratis atau Rp 500.000.

---

## HARGA
- 1 Box = Rp 145.000
- 2 Box = Rp 285.000
- 3 Box = Rp 425.000 (recommended untuk program garansi)

## LINK TOKO
SELALU tambahkan: "Cek aja dulu, sering ada promo flash sale dan free produk."
- Jaksel: Spencer https://s.shopee.co.id/9ALdD7gJI8 | Mealblend https://s.shopee.co.id/20sSgZn5yr
- Jakbar: Hotto https://s.shopee.co.id/7VDPEOPBXg | Spencers https://s.shopee.co.id/3B4Q4efrzq
- Jakut: Purnomo https://s.shopee.co.id/902D10RiTH | Hotto_id https://s.shopee.co.id/20sSgZn5yr
- Sby Timur: Lala https://s.shopee.co.id/3g0gf3iVQE | Sby Barat: Healthy https://s.shopee.co.id/9zukCuzXzV
- Sby Pusat (Mall): OWL https://s.shopee.co.id/8V5wQ0na9y
- Jogja: 242you https://s.shopee.co.id/6Ai1e2oWVx

---

## PRODUK
Lelixir, Blackcurrant, 10 sachet @30ml, 15 kkal, 2g gula Stevia. BPOM HALAL HACCP. Double Action: Metabolism Booster + Detox Usus.
Ingredients: L-Carnitine, Guarana, Green Tea (booster) | Polydextrose, Inulin, Aloe Vera, Prune, Spirulina (detox) | Blackcurrant, Red Beet, Mushroom, Vit&Min, Steviol (pendukung).
Konsumsi: setelah makan siang/malam. Jangan perut kosong.
Kondisi: Hamil/Menyusui TIDAK. Maag aman setelah makan. Hipertensi monitor. Diabetes aman.

## DETOX AWAL
Awal-awal BAB lebih sering / warna lebih gelap = NORMAL. Tanda detoksifikasi usus berjalan. Rutin 2 minggu: lebih segar, cerah, susut.

## LEGALITAS
BPOM 272882011400050 | Halal ID32410029283580925 | PT Aimfood | PT Mega Bintang Sembilan
Bukti BPOM: https://drive.google.com/file/d/1dOpe3MfK0RkvEFmwwBPqecuYCxwxyCm3/view?usp=sharing
Bukti Halal: https://drive.google.com/file/d/1YBhfqc60AAI2JmPu5SCI-sy0ubP3FeYy/view?usp=sharing

## KOMPETITOR
"Double Action, satu-satunya yang fokus lingkar perut." Vs obat: "Bukan obat, bekerja alami/holistik."
Rebound: "Perbaiki dasar metabolisme, hasilnya sustainable." Ketergantungan: "Alami seperti buah naga."

## EXPIRED DATE
ED dekat (2-3 bulan): aman, HACCP terjaga. Terima ED < 60 hari dari distributor resmi: boleh tukar. Lewat ED: penurunan khasiat.

---

## NUTRISI & POLA MAKAN
7 prinsip: 1) Hindari gula tambahan 2) Jeda makan = nol kalori (air, teh tawar, kopi hitam) 3) Karbo ½ porsi 4) Perbanyak serat 5) Perbanyak protein 6) Air 2L/hari 7) IF + Lelixir = kombinasi terbaik
Buah: HARUS utuh (bukan jus). Hindari durian. Pisang hanya pagi.
Hindari: es teh manis, jus buah, snacking, gorengan deep fry, minuman kemasan manis.
Lakukan: nasi ½, protein + sayur banyak, air 2L, Lelixir setelah makan, buah utuh, tidur 7-8 jam, jalan kaki 30 menit.

## OLAHRAGA
L1: jalan kaki 15-30 menit. L2: cardio + resistance. L3: HIIT. L4: HIIT + HYROX. Konsistensi > intensitas.

---

## MEAL PLAN — FORMAT PENYAJIAN

Sajikan PER 2 HARI. Akhiri selalu dengan: "mau lanjut 2 hari berikutnya? tinggal bilang ya"
Dosis Lelixir: target 1-6 kg = 1 sachet setelah siang | target 7 kg+ = 2 sachet siang + malam.
Format: PAGI | BUAH | SIANG + Lelixir | MALAM (+Lelixir kalau 2 sachet) | Tips singkat

Jangan: brand lain, ayam rebus (kecuali diminta), snacking di jeda, jus buah.
Harus: Lelixir disebut, makanan enak dan variatif, berbeda setiap hari.

### DATABASE PROTEIN
Telur (rebus/scramble/omelette/dadar), Dada Ayam Panggang, Ayam Bakar Kecap (less sugar), Paha Ayam Sautee, Salmon Panggang, Dori Pan Sear, Kakap Bakar Sambal Matah, Tuna Steak, Udang Garlic Butter, Cumi Bakar, Beef Steak Sirloin, Yakiniku, Rendang (less santan), Tempe Bacem (less sugar), Tahu Crispy AF, Chicken Katsu AF, Gurame Bakar, Ayam Geprek AF, Smoked Salmon, Greek Yogurt, Bebek AF, Pecel Lele AF, Ayam Rica-Rica, Sate Ayam, Opor Ayam (less santan), Pecel Ayam, Ayam Penyet AF, Sop Iga, Rawon, Empal Gentong (less santan), Gulai Ikan, Capcay Seafood, Sup Ikan Batam, Ayam BBQ, Pepes Ikan Mas, Tom Yum Udang, Thai Basil Chicken.

### DATABASE KARBO (selalu ½ porsi)
Nasi Putih, Nasi Merah, Nasi Shirataki, Roti Whole Wheat, Sourdough, Oatmeal, Ubi Jalar, Kentang Rebus, Spaghetti WW, Penne WW, Tortilla Wrap WW, Quinoa.

### DATABASE SAYUR
Brokoli, Bayam, Kangkung, Sawi/Pak Choy, Kacang Panjang, Wortel, Terong, Zucchini, Paprika, Timun, Asparagus, Mixed Salad, Labu Siam, Jamur, Edamame.

### DATABASE BUAH (UTUH!)
Boleh: Apel, Pir, Jeruk, Strawberry, Blueberry, Kiwi, Pepaya (sedikit), Alpukat, Dragon Fruit, Anggur (10-15 butir).
Pagi saja: Pisang (max 1), Semangka (sedikit), Mangga (sedikit). Hindari: Durian.

### SARAPAN VARIASI
Telur+Sourdough+Kopi | Overnight Oat (oat+yogurt+buah+chia)+Telur | Scrambled+Roti WW+Alpukat | Telur+Tortilla Wrap | Smoothie Bowl+Telur | Poached Eggs+Sourdough+Smoked Salmon | Telur+Ubi Jalar | French Toast WW | Egg Wrap (dadar+ayam suwir+paprika)

### 30 HARI MEAL PLAN DATABASE
W1D1: Pagi=Telur Rebus 2+Sourdough+Kopi. Buah=Apel. Siang=Nasi½+Ayam Bakar Kecap+Kangkung+Lelixir. Malam=Nasi Merah½+Kakap Sambal Matah+Labu Siam.
W1D2: Pagi=Overnight Oat (yogurt+strawberry+chia)+Telur Rebus. Buah=Pir. Siang=Nasi½+Dori Pan Sear+Brokoli+Lelixir. Malam=Spaghetti WW½+Udang Garlic Butter+Salad.
W1D3: Pagi=Scrambled+Roti WW+Alpukat+Kopi. Buah=Kiwi. Siang=Nasi½+Ayam Geprek AF+Sawi+Lelixir. Malam=Nasi Merah½+Salmon Lemon+Asparagus.
W1D4: Pagi=Overnight Oat (almond+blueberry)+Telur Rebus. Buah=Jeruk. Siang=Nasi½+Cumi Bakar Kecap+Kacang Panjang+Lelixir. Malam=Kentang Rebus+Beef Steak+Mushroom+Paprika.
W1D5: Pagi=Telur Orak-Arik+Tortilla Wrap+Kopi. Buah=Dragon Fruit. Siang=Nasi½+Tempe Bacem+Terong Balado+Bayam+Lelixir. Malam=Nasi Shirataki+Tuna Sear+Edamame+Salad.
W1D6: Pagi=Overnight Oat (pisang+PB+cinnamon)+Kopi. Buah=Anggur 10-15. Siang=Chicken Katsu AF+Nasi½+Salad Paprika+Lelixir. Malam=Penne WW Aglio Olio+Udang+Brokoli.
W1D7: Pagi=Poached Eggs+Sourdough+Smoked Salmon+Alpukat+Kopi. Buah=Strawberry. Siang=Nasi Merah½+Gurame Bakar Rica+Urap+Lelixir. Malam=Quinoa Bowl+Yakiniku+Zucchini+Jamur.
W2D8: Pagi=Telur Rebus 2+Ubi Jalar+Kopi. Buah=Pir. Siang=Nasi½+Pecel Ayam+Bayam+Kacang Panjang+Lelixir. Malam=Nasi Merah½+Salmon Teriyaki+Pak Choy.
W2D9: Pagi=Overnight Oat (yogurt+kiwi+granola)+Telur Rebus. Buah=Apel. Siang=Wrap WW Ayam Panggang+Paprika+Selada+Lelixir. Malam=Nasi½+Rendang Less Santan+Labu Siam.
W2D10: Pagi=Scrambled+Roti WW+Tomat+Kopi. Buah=Jeruk. Siang=Nasi½+Tahu Crispy AF+Kangkung Terasi+Lelixir. Malam=Spaghetti Bolognese WW+Salad.
W2D11: Pagi=Overnight Oat (susu oat+apel+cinnamon+almond)+Telur Rebus. Buah=Blueberry. Siang=Nasi Merah½+Ayam Taliwang+Plecing Kangkung+Lelixir. Malam=Kentang Mashed+Ayam Panggang Herbs+Asparagus+Brokoli.
W2D12: Pagi=Telur Dadar 2+Sourdough+Alpukat+Kopi. Buah=Dragon Fruit. Siang=Rice Bowl Nasi½+Salmon Sear+Edamame+Nori+Lelixir. Malam=Nasi Shirataki+Udang Saus Padang+Wortel+Buncis.
W2D13: Pagi=Smoothie Bowl (yogurt+blueberry+oat+chia)+Telur Rebus. Buah=Pepaya. Siang=Nasi½+Sop Iga Sapi+Sayuran+Lelixir. Malam=Zucchini Noodles+Pesto Chicken+Tomat.
W2D14: Pagi=Eggs Benedict+Sourdough+Smoked Salmon+Kopi. Buah=Strawberry+Blueberry. Siang=Nasi Merah½+Ayam Penyet AF+Lalapan+Lelixir. Malam=Steak Sirloin+Sweet Potato Mash+Mushroom+Asparagus.
W3D15: Pagi=Telur Rebus 2+Roti WW+Selai Kacang+Kopi. Buah=Kiwi. Siang=Nasi½+Ikan Bawal Bakar+Terong+Sayur Asem+Lelixir. Malam=Nasi Merah½+Ayam BBQ+Coleslaw.
W3D16: Pagi=Overnight Oat (almond+pir+walnut+cinnamon)+Telur Rebus. Buah=Apel. Siang=Nasi½+Capcay Seafood+Lelixir. Malam=Penne Arrabbiata+Grilled Chicken+Salad.
W3D17: Pagi=Egg Wrap (dadar+ayam suwir+paprika+keju)+Kopi. Buah=Jeruk. Siang=Nasi Merah½+Pepes Ikan Mas+Kacang Panjang+Lalapan+Lelixir. Malam=Tom Yum Udang+Nasi Shirataki.
W3D18: Pagi=Overnight Oat (yogurt+dragon fruit+granola)+Telur Rebus. Buah=Pir. Siang=Nasi½+Ayam Rica-Rica+Bayam+Lelixir. Malam=Tortilla Wrap Beef Yakiniku+Selada+Timun+Paprika.
W3D19: Pagi=Scrambled+Sourdough+Tomat+Mushroom Sautee+Kopi. Buah=Anggur. Siang=Nasi½+Sate Ayam+Lontong½+Acar+Lelixir. Malam=Salmon Bowl Quinoa+Alpukat+Edamame+Nori.
W3D20: Pagi=Smoothie Bowl (yogurt+strawberry+oat+almond)+Telur Rebus. Buah=Blueberry. Siang=Nasi Merah½+Gulai Kakap+Daun Singkong+Lelixir. Malam=Chicken Caesar Salad+Sourdough 1 slice.
W3D21: Pagi=Poached Egg+Bayam Sautee+English Muffin+Kopi. Buah=Dragon Fruit. Siang=Nasi½+Rawon Daging+Tauge+Telur Asin+Lelixir. Malam=Tuna Tataki Bowl Shirataki+Timun+Wortel+Sesame.
W4D22: Pagi=Telur Rebus 2+Ubi Jalar+Alpukat+Kopi. Buah=Apel. Siang=Nasi½+Opor Ayam (less santan)+Labu Siam+Lelixir. Malam=Nasi Merah½+Dori Saus Lemon Butter+Brokoli+Wortel.
W4D23: Pagi=Overnight Oat (susu oat+mangga+kelapa serut+chia)+Telur Rebus. Buah=Kiwi. Siang=Nasi Merah½+Bebek AF+Lalapan+Sambal+Lelixir. Malam=Spaghetti Aglio Olio+Cumi Sautee+Paprika+Zucchini.
W4D24: Pagi=French Toast WW (telur+cinnamon)+Kopi. Buah=Pir. Siang=Nasi½+Pecel Lele AF+Sambal Terasi+Lalapan+Lelixir. Malam=Thai Basil Chicken+Nasi Shirataki+Buncis.
W4D25: Pagi=Overnight Oat (yogurt+apel+cinnamon+pecan)+Telur Rebus. Buah=Jeruk. Siang=Wrap WW Tuna Salad+Selada+Tomat+Timun+Lelixir. Malam=Nasi Merah½+Empal Gentong (less santan)+Kangkung.
W4D26: Pagi=Scrambled+Smoked Salmon+Sourdough+Alpukat+Kopi. Buah=Strawberry. Siang=Nasi½+Sup Ikan Batam+Sayuran+Lelixir. Malam=Steak Tenderloin+Sweet Potato Mash+Asparagus+Mushroom.
W4D27: Pagi=Smoothie Bowl (yogurt+mixed berry+oat+almond+chia)+Telur Rebus. Buah=Pepaya. Siang=Nasi Merah½+Nasi Campur Bali (ayam suwir+sate lilit+lawar)+Lelixir. Malam=Prawn Pad Thai (shirataki)+Tauge+Kacang+Lime.
W4D28: Pagi=Eggs Benedict+Smoked Salmon+Sourdough+Kopi. Buah=Anggur+Blueberry. Siang=Nasi Kuning½+Ayam Goreng Bumbu Kuning+Perkedel AF+Urap+Lelixir. Malam=Surf&Turf Beef Steak+Udang Grill+Caesar Salad+Brokoli.
D29-30: Ulangi menu favorit dari W1-W4, atau variasi baru dari database.

---

## LARANGAN
- Klaim menyembuhkan penyakit
- Bilang aman untuk hamil/menyusui
- Janji hasil pasti (pakai kata "biasanya" atau "umumnya")
- Jelek-jelekkan kompetitor langsung
- Brand lain di meal plan
- Ayam rebus (kecuali customer minta)
- Snack di jeda makan
- Jus buah
- Topik di luar kesehatan/Lelixir
- Jawaban terlalu panjang
- Jualan di chat pertama
- Bilang AI/bot
- Eskalasi tanpa konfirmasi customer
- Emoticon berlebihan
"""

# ---------------------------------------------------------------------------
# FLASK APP
# ---------------------------------------------------------------------------

app = Flask(__name__)
init_db()

sched_started = False
def start_sched():
    global sched_started
    if not sched_started:
        sched_started = True
        threading.Thread(target=scheduler, daemon=True).start()
        print("[SCHED] Started")
start_sched()

def ask_claude(nomor, pesan):
    riwayat = get_history(nomor)

    g = get_garansi(nomor)
    ctx = ""
    if g and g["status"] == "active":
        ctx = f"\n[GARANSI AKTIF] Nama: {g['nama']}, mulai: {g['tanggal_mulai']}, checkin: {g['total_checkin']}, streak: {g['streak']}, miss: {g['miss_count']}/2."
    elif g and g["status"] == "failed":
        ctx = f"\n[GARANSI GUGUR] Nama: {g['nama']}, miss: {g['miss_count']}x."
    elif has_garansi(nomor):
        ctx = "\n[INFO] Customer sudah pernah ikut program garansi."

    pesan_with_ctx = pesan + ctx
    save_message(nomor, "user", pesan_with_ctx)
    riwayat.append({"role": "user", "content": pesan_with_ctx})

    for _ in range(3):
        try:
            r = requests.post(
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
            if r.status_code == 200:
                j = r.json()["content"][0]["text"]
                save_message(nomor, "assistant", j)
                return j
            elif r.status_code == 529:
                time.sleep(5)
            else:
                print(f"[ERR] {r.status_code}: {r.text}")
                break
        except Exception as e:
            print(f"[ERR Claude] {e}")
            time.sleep(3)

    return "Maaf, sistem lagi sibuk. Coba lagi dalam 1-2 menit ya."

def proc_tag(nomor, jawaban):
    m = re.search(r'\[DAFTAR_GARANSI:(.+?)\]', jawaban)
    if m:
        nm = m.group(1).strip()
        if not has_garansi(nomor):
            reg_garansi(nomor, nm)
            print(f"[GAR] {nm} ({nomor})")
        jawaban = re.sub(r'\s*\[DAFTAR_GARANSI:.+?\]\s*', '', jawaban).strip()
    return jawaban

@app.route("/webhook", methods=["POST"])
def webhook():
    data  = request.json or request.form.to_dict()
    nomor = data.get("sender", "")
    pesan = data.get("message", "")

    print(f"\n[{now_wib().strftime('%H:%M:%S')}] {nomor}: {pesan[:80]}")

    if not nomor or not pesan or "@g.us" in nomor:
        return jsonify({"s": "ignored"}), 200

    catat_customer(nomor)

    if data.get("type", "text") != "text":
        g = get_garansi(nomor)
        if g and g["status"] == "active":
            j = checkin(nomor)
            if j == 1:
                msg = "Foto pertama hari ini masuk, thanks! Jangan lupa foto makan malam dan sachet Lelixir-nya ya."
            elif j == 2:
                msg = "Foto ke-2 masuk. Satu lagi untuk complete hari ini."
            elif j == 3:
                msg = "3 foto udah masuk — checkin hari ini complete! Good job."
            else:
                msg = "Foto diterima!"
            send_wa(nomor, msg)
            return jsonify({"s": "checkin"}), 200
        send_wa(nomor, "Foto diterima ya. Saya terbatas baca file di sini, kalau ada pertanyaan boleh diketik.")
        return jsonify({"s": "non-text"}), 200

    jawaban = ask_claude(nomor, pesan)
    jawaban = proc_tag(nomor, jawaban)
    send_wa(nomor, jawaban)
    return jsonify({"s": "replied"}), 200

@app.route("/dashboard")
def dashboard():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT nomor, first_chat AT TIME ZONE 'Asia/Jakarta', last_chat AT TIME ZONE 'Asia/Jakarta',
               chat_count, followup_h1_sent, followup_3_sent, followup_10_sent
        FROM customers ORDER BY last_chat DESC
    """)
    custs = c.fetchall()
    c.execute("""
        SELECT nomor, nama, tanggal_mulai, status, total_checkin, streak, miss_count, followup_30_sent
        FROM garansi ORDER BY tanggal_mulai DESC
    """)
    gars = c.fetchall()
    conn.close()

    def f(n): return f"+{n[:2]} {n[2:5]}-{n[5:9]}-{n[9:]}" if len(n) >= 12 else n
    def badge(s):
        colors = {"active": "#28a745", "failed": "#dc3545", "pending": "#6c757d"}
        col = colors.get(s, "#6c757d")
        return f'<span style="background:{col};color:#fff;padding:2px 8px;border-radius:10px;font-size:12px">{s.capitalize()}</span>'
    def tick(v): return "✅" if v else "⏳"
    def fmt_dt(v): return str(v)[:16] if v else "-"

    cr = "".join([
        f'<tr style="background:{"#f8f9fa" if i%2==0 else "#fff"}"><td style="padding:10px 14px;font-family:monospace;font-size:14px">{f(r[0])}</td><td style="padding:10px 14px;font-size:13px">{fmt_dt(r[1])}</td><td style="padding:10px 14px;font-size:13px">{fmt_dt(r[2])}</td><td style="padding:10px 14px;text-align:center;font-weight:600">{r[3]}</td><td style="padding:10px 14px;text-align:center">{tick(r[4])}</td><td style="padding:10px 14px;text-align:center">{tick(r[5])}</td><td style="padding:10px 14px;text-align:center">{tick(r[6])}</td></tr>'
        for i, r in enumerate(custs)
    ])
    gr = "".join([
        f'<tr style="background:{"#f8f9fa" if i%2==0 else "#fff"}"><td style="padding:10px 14px;font-family:monospace;font-size:14px">{f(r[0])}</td><td style="padding:10px 14px;font-weight:500">{r[1]}</td><td style="padding:10px 14px;font-size:13px">{str(r[2])[:10] if r[2] else "-"}</td><td style="padding:10px 14px;text-align:center">{badge(r[3])}</td><td style="padding:10px 14px;text-align:center;font-weight:600">{r[4]}</td><td style="padding:10px 14px;text-align:center;font-weight:600">{r[5]}</td><td style="padding:10px 14px;text-align:center;color:#dc3545;font-weight:600">{r[6]}/2</td><td style="padding:10px 14px;text-align:center">{tick(r[7])}</td></tr>'
        for i, r in enumerate(gars)
    ])

    ac = len([g for g in gars if g[3] == 'active'])
    fc = len([g for g in gars if g[3] == 'failed'])

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Lelixir Dashboard</title>
    <style>body{{font-family:-apple-system,sans-serif;margin:0;padding:20px;background:#f0f2f5}}.ct{{max-width:1200px;margin:0 auto}}h1{{color:#d63384;font-size:24px}}.sub{{color:#6c757d;margin-bottom:25px;font-size:14px}}.stats{{display:flex;gap:15px;margin-bottom:25px;flex-wrap:wrap}}.sc{{background:#fff;border-radius:12px;padding:20px;flex:1;min-width:120px;box-shadow:0 1px 3px rgba(0,0,0,.1)}}.sn{{font-size:32px;font-weight:700;color:#d63384}}.sl{{font-size:13px;color:#6c757d}}.sec{{background:#fff;border-radius:12px;padding:20px;margin-bottom:20px;box-shadow:0 1px 3px rgba(0,0,0,.1);overflow-x:auto}}.sec h2{{font-size:18px;margin:0 0 15px}}table{{width:100%;border-collapse:collapse;min-width:600px}}th{{background:#f8f9fa;padding:10px 14px;text-align:left;font-size:12px;text-transform:uppercase;color:#6c757d;border-bottom:2px solid #dee2e6;white-space:nowrap}}td{{border-bottom:1px solid #f0f0f0}}.rf{{color:#6c757d;font-size:12px;text-align:center;margin-top:15px}}</style></head>
    <body><div class="ct"><h1>Lelixir Dashboard</h1><p class="sub">v3.2 | {now_wib().strftime("%d/%m/%Y %H:%M")} WIB</p>
    <div class="stats"><div class="sc"><div class="sn">{len(custs)}</div><div class="sl">Customer</div></div><div class="sc"><div class="sn">{len(gars)}</div><div class="sl">Garansi</div></div><div class="sc"><div class="sn">{ac}</div><div class="sl">Aktif</div></div><div class="sc"><div class="sn" style="color:#dc3545">{fc}</div><div class="sl">Gagal</div></div></div>
    <div class="sec"><h2>Customer ({len(custs)})</h2><table><tr><th>WA</th><th>First Chat</th><th>Last Chat</th><th>Chat</th><th>H+1</th><th>D3</th><th>D10</th></tr>{cr}</table></div>
    <div class="sec"><h2>Program Pasti Langsing ({len(gars)})</h2><table><tr><th>WA</th><th>Nama</th><th>Mulai</th><th>Status</th><th>Checkin</th><th>Streak</th><th>Miss</th><th>H+31</th></tr>{gr}</table></div>
    <p class="rf">Refresh untuk data terbaru</p></div></body></html>"""

@app.route("/garansi-status/<nomor>")
def cek_gar(nomor):
    g = get_garansi(nomor)
    return (jsonify(g), 200) if g else (jsonify({"error": "Tidak terdaftar"}), 404)

@app.route("/")
def home():
    return jsonify({"status": "active", "app": "LELIXIR v3.2", "scheduler": sched_started}), 200

@app.route("/health")
def health():
    return jsonify({"status": "healthy", "scheduler": sched_started, "time_wib": now_wib().strftime("%Y-%m-%d %H:%M:%S")}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
