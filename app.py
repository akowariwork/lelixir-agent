"""
===========================================================
LELIXIR AI AGENT v2.8
===========================================================
- Garansi updated: 3kg / 3cm
- ED policy: tukar dari distributor resmi
- Halal link updated: bpjph.halal.go.id
- Bukti BPOM & Halal via Google Drive
- Surabaya Pusat (OWL Mall)
- Dashboard HTML, Follow-up H+1/D3/D10/G30
- Auto-retry 3x
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

FOLLOWUP_H1_GREETING = [
    "Hai Kak! Kemarin sempat chat ya, makasih sudah mampir 😊\n\nPerkenalkan, saya Health Assistant Lelixir — asisten gizi pribadi kakak yang siap bantu 24 jam.\n\nKakak bisa nanya apa aja ke saya lho, misalnya:\n✅ Cara pakai Lelixir supaya hasilnya maksimal\n✅ Buatkan meal plan harian yang enak dan gampang\n✅ Tips olahraga ringan yang cocok buat kakak\n✅ Soal nutrisi, diet, atau intermittent fasting\n\nJangan sungkan ya Kak — saya senang banget kalau bisa bantu kakak langsing dengan cara yang cepat, aman, dan nyaman! 💪",
    "Halo Kak! Salam kenal, saya Health Assistant Lelixir 😊\n\nKemarin kakak sempat chat tapi mungkin belum sempat tanya lebih lanjut — santai aja Kak!\n\nSaya bisa bantu banyak hal lho:\n✅ Konsultasi cara memaksimalkan Lelixir\n✅ Buatkan meal plan yang disesuaikan target kakak\n✅ Kasih tips diet & olahraga yang simpel dan do-able\n✅ Jawab soal nutrisi, IF, atau kesehatan pencernaan\n\nAnggap aja saya teman yang paham gizi — tanya apapun, kapan aja! Saya siap bantu kakak dapat hasil terbaik ✨",
    "Hi Kak! Kemarin sempat mampir chat ya 😊\n\nSaya Health Assistant Lelixir — asisten gizi kakak yang standby 24 jam. Kalau kakak lagi cari cara langsing yang cepat, aman, dan nyaman — saya bisa bantu banget!\n\nMisalnya:\n✅ Cara pakai Lelixir yang paling efektif\n✅ Dibuatkan meal plan harian (termasuk kalau lagi IF)\n✅ Olahraga apa yang paling gampang tapi hasilnya kelihatan\n✅ Nanya soal nutrisi atau kesehatan secara umum\n\nSemua boleh Kak, jangan sungkan! Chat aja kapan pun, saya dengan senang hati bantu 🙌"
]

FOLLOWUP_HARI_3 = [
    "Hai Kak! Gimana, udah sempat coba Lelixir nya? Di awal-awal biasanya BAB akan terasa lebih sering dan lebih banyak — itu pertanda bagus! Proses detoksifikasi usus mulai bekerja. Tetap semangat ya! 💪",
    "Halo Kak! Udah mulai rutin minum Lelixir nya? Kalau BAB jadi lebih sering, tenang — itu tanda positif! Usus kakak sedang dibersihkan. Lanjutkan terus ya! 🙌",
    "Hi Kak! Checking in nih, sudah 3 hari. Semoga Lelixir nya sudah dicoba! Coba rutin 2 minggu ya Kak, hasilnya mulai kelihatan — badan segar, kulit cerah, perut menyusut! Semangat!"
]

FOLLOWUP_HARI_10 = [
    "Hai Kak! Gimana progress nya? Kalau stock menipis, re-stock biar nggak putus. Banyak customer lingkar perutnya susut 5-8 cm dalam 30 hari! Cek toko terdekat, sering ada flash sale dan free produk!",
    "Halo Kak! Stock nya pasti udah menipis ya? Hasil terbaik di 30 hari rutin! Cek Shopee Mall OWL Kak, sering ada promo flash sale! 💪",
    "Hi Kak! Semoga Lelixir sudah terasa manfaatnya. Kalau stock mau habis, jangan putus — konsistensi kuncinya. Cek marketplace terdekat, sering ada flash sale! Semangat!"
]

FOLLOWUP_GARANSI_30 = [
    "Hai Kak {nama}! 🎉\n\nUdah 30 hari sejak kakak daftar Program Pasti Langsing! Selamat udah konsisten! 💪\n\nGimana Kak, udah turun berapa kg dan berapa cm lingkar perutnya?\n\nTolong kirim:\n1. Foto timbangan terbaru\n2. Foto ukur lingkar perut terbaru\n\nFoto dan progress kakak akan di-review oleh admin ya.\n\nApakah kakak merasa ada progress? Cerita dong!"
]

DB_PATH = "lelixir_customers.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS customers (
        nomor TEXT PRIMARY KEY, first_chat TEXT, last_chat TEXT, chat_count INTEGER DEFAULT 0,
        followup_h1_sent INTEGER DEFAULT 0, followup_3_sent INTEGER DEFAULT 0, followup_10_sent INTEGER DEFAULT 0)""")
    c.execute("""CREATE TABLE IF NOT EXISTS garansi (
        nomor TEXT PRIMARY KEY, nama TEXT, tanggal_daftar TEXT, tanggal_mulai TEXT,
        status TEXT DEFAULT 'pending', total_checkin INTEGER DEFAULT 0, last_checkin_date TEXT,
        streak INTEGER DEFAULT 0, followup_30_sent INTEGER DEFAULT 0)""")
    c.execute("""CREATE TABLE IF NOT EXISTS checkin_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT, nomor TEXT, tanggal TEXT, jumlah_foto INTEGER DEFAULT 0, timestamp TEXT)""")
    conn.commit()
    conn.close()

def catat_customer(nomor):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute("SELECT chat_count FROM customers WHERE nomor = ?", (nomor,))
    row = c.fetchone()
    if row:
        c.execute("UPDATE customers SET last_chat=?, chat_count=? WHERE nomor=?", (now, row[0]+1, nomor))
    else:
        c.execute("INSERT INTO customers VALUES (?,?,?,1,0,0,0)", (nomor, now, now))
    conn.commit()
    conn.close()

def get_customers_for_h1_followup():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    yesterday = (datetime.now() - timedelta(days=1)).isoformat()[:10]
    c.execute("SELECT nomor FROM customers WHERE date(first_chat)=? AND chat_count<=3 AND followup_h1_sent=0", (yesterday,))
    r = [row[0] for row in c.fetchall()]
    conn.close()
    return r

def get_customers_for_followup(hari, field):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    target = (datetime.now() - timedelta(days=hari)).isoformat()[:10]
    prev = (datetime.now() - timedelta(days=hari+1)).isoformat()[:10]
    c.execute(f"SELECT nomor FROM customers WHERE date(first_chat)<=? AND date(first_chat)>=? AND {field}=0", (target, prev))
    r = [row[0] for row in c.fetchall()]
    conn.close()
    return r

def tandai_followup(nomor, field):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(f"UPDATE customers SET {field}=1 WHERE nomor=?", (nomor,))
    conn.commit()
    conn.close()

def get_garansi_status(nomor):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM garansi WHERE nomor=?", (nomor,))
    row = c.fetchone()
    conn.close()
    if row:
        return {"nomor":row[0],"nama":row[1],"tanggal_daftar":row[2],"tanggal_mulai":row[3],"status":row[4],"total_checkin":row[5],"last_checkin_date":row[6],"streak":row[7],"followup_30_sent":row[8] if len(row)>8 else 0}
    return None

def get_garansi_for_followup_30():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    target = (datetime.now() - timedelta(days=30)).isoformat()[:10]
    prev = (datetime.now() - timedelta(days=31)).isoformat()[:10]
    c.execute("SELECT nomor,nama FROM garansi WHERE date(tanggal_mulai)<=? AND date(tanggal_mulai)>=? AND status='active' AND followup_30_sent=0", (target, prev))
    r = [(row[0],row[1]) for row in c.fetchall()]
    conn.close()
    return r

def tandai_garansi_30(nomor):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE garansi SET followup_30_sent=1 WHERE nomor=?", (nomor,))
    conn.commit()
    conn.close()

def daftar_garansi(nomor, nama):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.now().isoformat()
    mulai = (datetime.now() + timedelta(days=1)).isoformat()[:10]
    c.execute("INSERT INTO garansi VALUES (?,?,?,?,'active',0,'',0,0) ON CONFLICT(nomor) DO UPDATE SET nama=?,tanggal_daftar=?,tanggal_mulai=?,status='active',total_checkin=0,last_checkin_date='',streak=0,followup_30_sent=0",
              (nomor,nama,now,mulai,nama,now,mulai))
    conn.commit()
    conn.close()

def catat_checkin(nomor):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    today = datetime.now().isoformat()[:10]
    now = datetime.now().isoformat()
    c.execute("SELECT jumlah_foto FROM checkin_log WHERE nomor=? AND tanggal=?", (nomor, today))
    row = c.fetchone()
    if row:
        nc = row[0]+1
        c.execute("UPDATE checkin_log SET jumlah_foto=?, timestamp=? WHERE nomor=? AND tanggal=?", (nc,now,nomor,today))
    else:
        nc = 1
        c.execute("INSERT INTO checkin_log (nomor,tanggal,jumlah_foto,timestamp) VALUES (?,?,1,?)", (nomor,today,now))
    g = get_garansi_status(nomor)
    if g and g["status"]=="active":
        ld = g["last_checkin_date"]
        if ld == today:
            streak = g["streak"]
        else:
            streak = g["streak"]+1 if (ld==(datetime.now()-timedelta(days=1)).isoformat()[:10] or ld=="") else 1
        c.execute("UPDATE garansi SET total_checkin=?,last_checkin_date=?,streak=? WHERE nomor=?", (g["total_checkin"]+1,today,streak,nomor))
    conn.commit()
    conn.close()
    return nc

def kirim_wa(nomor, pesan):
    try:
        r = requests.post("https://api.fonnte.com/send", headers={"Authorization":FONNTE_API_KEY}, json={"target":nomor,"message":pesan,"typing":True}, timeout=15)
        if r.status_code==200: print(f"[OK] {nomor}"); return True
        else: print(f"[ERR] Fonnte {r.status_code}"); return False
    except Exception as e: print(f"[ERR] {e}"); return False

def jalankan_followup():
    while True:
        try:
            now = datetime.now()
            if 9 <= now.hour <= 20:
                print(f"[SCHED] {now.strftime('%Y-%m-%d %H:%M')}")
                for n in get_customers_for_h1_followup():
                    kirim_wa(n, random.choice(FOLLOWUP_H1_GREETING)); tandai_followup(n,"followup_h1_sent"); print(f"[H1] {n}"); time.sleep(2)
                for n in get_customers_for_followup(3,"followup_3_sent"):
                    kirim_wa(n, random.choice(FOLLOWUP_HARI_3)); tandai_followup(n,"followup_3_sent"); print(f"[D3] {n}"); time.sleep(2)
                for n in get_customers_for_followup(10,"followup_10_sent"):
                    kirim_wa(n, random.choice(FOLLOWUP_HARI_10)); tandai_followup(n,"followup_10_sent"); print(f"[D10] {n}"); time.sleep(2)
                for n,nm in get_garansi_for_followup_30():
                    kirim_wa(n, FOLLOWUP_GARANSI_30[0].replace("{nama}",nm)); tandai_garansi_30(n); print(f"[G30] {n}"); time.sleep(2)
        except Exception as e: print(f"[SCHED ERR] {e}")
        time.sleep(3600)

SYSTEM_PROMPT = """# AI AGENT LELIXIR v2.8

## IDENTITAS
Health Assistant Lelixir — asisten kesehatan & CS WhatsApp resmi. 2 skill (Sales + Health) switch otomatis + Program Garansi 30 Hari.

## ATURAN IDENTITAS
- JANGAN PERNAH bilang AI/bot/chatbot
- "Saya Health Assistant Lelixir"
- File: "Saya memiliki keterbatasan untuk membaca/mengirim file. Boleh diketik aja ya Kak"
- Peserta garansi kirim foto: "Ok terima kasih Kak, foto diterima!"

## FITUR (hanya kalau DITANYA)
Asisten gizi 24/7. Meal Plan, Workout Plan, Konsultasi Kondisi Khusus, Edukasi Gula & Insulin, Pendamping Program 30 Hari.

## PRINSIP CHAT
1. 90% sudah beli. Fokus SUPPORT.
2. Soft sell setelah beberapa kali chat.
3. Jadwal Lelixir DI AWAL meal plan. Target 1-6 kg: 1 sachet. Target 7 kg+: 2 sachet.
4. Akhiri dengan SEMANGAT.

## DETOX USUS (customer baru)
Usus simpan endapan 2-10 kg. Awal: warna kehitaman, bau menyengat — NORMAL. Endapan bikin asam lambung. Rutin 2 minggu: segar, cerah, susut. Cek testi Shopee Mall OWL.

---

## PROGRAM GARANSI 30 HARI PASTI LANGSING

Tawarkan setelah jawab pertanyaan PERTAMA customer baru.
Juga kalau customer tanya garansi/jaminan.

Syarat:
1. Beli 3 Box Lelixir (30 sachet)
2. Kirim foto stock 3 box + resi belanja Shopee
3. Nama lengkap
4. Foto timbangan BB + lingkar perut (cm) saat ini
5. Mulai besok, 30 hari kirim 4 foto/hari (sarapan, siang, malam, sachet Lelixir)
6. Tidak boleh putus 1 hari pun
7. Setelah 30 hari kirim foto timbangan + lingkar perut terbaru

**GARANSI: Kalau BB tidak turun minimal 3 kg ATAU lingkar perut tidak susut minimal 3 cm dalam 30 hari, uang 3 box dikembalikan 100%.**

Gugur jika 1 hari tidak kirim foto lengkap.

Kalau MAU: minta kelengkapan.
Kirim nama: konfirmasi, mulai besok, 4 foto/hari.
Kirim foto: "Ok terima kasih Kak, foto diterima!"
Setelah 30 hari: tanya progress, review admin.
Claim: "Foto 4x/hari 30 hari akan dianalisa Admin. Kalau terpenuhi, 4 hari admin akan chat perihal pengembalian." Eskalasi.
Puas: apresiasi + soft sell re-stock.

---

# SKILL 1: SALES

## HARGA
1 Box = Rp 145.000 | 2 Box = Rp 285.000 | 3 Box = Rp 425.000 (RECOMMENDED)

## LINK
SELALU: "Cek aja dulu Kak, sering ada promo flash sale dan free produk!"

JAKARTA:
Jaksel: Spencer Mealblend https://s.shopee.co.id/9ALdD7gJI8 | Mealblend Store https://s.shopee.co.id/20sSgZn5yr
Jakbar: Hotto Purto https://s.shopee.co.id/7VDPEOPBXg | Spencers Mealblend https://s.shopee.co.id/3B4Q4efrzq
Jakut: Purnomo Jaya https://s.shopee.co.id/902D10RiTH | Hotto_id https://s.shopee.co.id/20sSgZn5yr

SURABAYA:
Surabaya Timur: Lala Healthy https://s.shopee.co.id/3g0gf3iVQE
Surabaya Barat: Healthy Mealblend https://s.shopee.co.id/9zukCuzXzV
Surabaya Pusat (Shopee Mall): OWL Mall https://s.shopee.co.id/8V5wQ0na9y

JOGJA/JATENG: 242you https://s.shopee.co.id/6Ai1e2oWVx

## KOMPETITOR: jangan jelek-jelekkan. "Double Action, satu-satunya fokus lingkar perut." Vs obat: "Bukan obat, lebih aman, holistik alami."
## REBOUND: "Perbaiki dasar, bukan penekan nafsu makan, sustainable."
## KETERGANTUNGAN: "Alami, kayak buah naga. 1-2 bulan rutin bisa stop, minum occasionally."

## EXPIRED DATE (ED)

Kalau tanya ED dekat (2-3 bulan): "Masih sangat aman Kak! Standard produksi sesuai HACCP, produk sebelum tanggal ED 100% aman. Yang penting kemasan baik, segel utuh, penyimpanan benar."

Kalau terima produk ED kurang dari 60 hari DARI TOKO DISTRIBUTOR RESMI LELIXIR: "Kalau kakak menerima produk dengan ED kurang dari 60 hari dari toko distributor resmi Lelixir, kakak bisa komplain untuk tukar produk ya Kak. Itu kebijakan Lelixir untuk menjaga kepuasan customer."

Kalau tanya produk lewat ED: "Yang terjadi penurunan khasiat, bukan menjadi berbahaya — selama kemasan baik, segel utuh, penyimpanan benar. Tapi kami sarankan konsumsi sebelum ED supaya manfaat optimal."

## LEGALITAS & BUKTI SERTIFIKASI

BPOM: 272882011400050
Halal: ID32410029283580925
Produksi: PT Aimfood Manufacturing Indonesia
Distribusi: PT Mega Bintang Sembilan

Kalau customer tanya soal BPOM atau Halal, jawaban UTAMA kasih link bukti langsung:
- Bukti BPOM: https://drive.google.com/file/d/1dOpe3MfK0RkvEFmwwBPqecuYCxwxyCm3/view?usp=sharing
- Bukti Halal: https://drive.google.com/file/d/1YBhfqc60AAI2JmPu5SCI-sy0ubP3FeYy/view?usp=sharing

Contoh: "Lelixir sudah terdaftar BPOM dan bersertifikat Halal Kak. Ini buktinya: [kasih link di atas]"

Kalau customer mau cek/verifikasi sendiri lebih lanjut, BARU kasih link website:
- Cek BPOM: https://cekbpom.pom.go.id
- Cek Halal: https://bpjph.halal.go.id/search/sertifikat?nama_produk

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
Pendukung: Blackcurrant 11.25%, Red Beet, Mushroom, Vit Min Premix, Steviol Glycosides.

## KONSUMSI: Setelah makan siang/malam, 15-30 menit. Jangan perut kosong.
## KONDISI: Hamil/Menyusui TIDAK. Maag AMAN setelah makan. Hipertensi monitor. Diabetes aman.

## NUTRISI
1. HINDARI GULA — paling penting.
2. JEDA MAKAN NOL KALORI — air putih, teh tawar, kopi tanpa gula SAJA.
3. KURANGI KARBO — 1/2 sayur + 1/4 protein + 1/4 karbo.
4. SERAT KUNCI. 5. PROTEIN CUKUP. 6. AIR 2L. 7. IF + Lelixir + kurangi gula = terbaik.
Ref internal (JANGAN sebut): GGL.

## MEAL PLAN
JANGAN: sebut brand lain, bilang ayam rebus, snack berkalori di jeda.
HARUS: Lelixir di AWAL, bahasa makanan enak (ayam goreng tanpa tepung, telur goreng/scramble, ikan bakar/goreng, tempe tahu goreng).

TEMPLATE:
LELIXIR: 1-6 kg = 1 sachet setelah siang. 7 kg+ = 2 sachet siang + malam.
Sarapan: telur + sayur + 1/2 karbo. Jeda NOL KALORI.
Siang: protein + sayur + 1/2 nasi -> LELIXIR. Jeda NOL KALORI.
Malam: protein + sayur, karbo skip -> LELIXIR (2x). Jalan kaki 15-30 min. STOP makan.

## OLAHRAGA: L1 jalan kaki. L2 cardio+resistance. L3 HIIT. L4 HIIT+HYROX. Konsistensi > intensitas.

## YANG TIDAK BOLEH
- Jangan klaim menyembuhkan
- Jangan aman hamil/menyusui
- Jangan hasil pasti
- Jangan jelek-jelekkan kompetitor
- Jangan sebut brand lain di meal plan
- Jangan ayam rebus
- Jangan snack berkalori di jeda
- Jangan di luar topik, jangan panjang
- Jangan sebut GGL
- Jangan jualan chat pertama
- JANGAN bilang AI/bot"""

app = Flask(__name__)
riwayat_chat = {}
MAKS_RIWAYAT = 20
init_db()

def tanya_claude(nomor, pesan):
    if nomor not in riwayat_chat: riwayat_chat[nomor] = []
    riwayat = riwayat_chat[nomor]
    g = get_garansi_status(nomor)
    ctx = f"\n[GARANSI] {g['nama']}, mulai {g['tanggal_mulai']}, checkin {g['total_checkin']}, streak {g['streak']}." if g and g["status"]=="active" else ""
    riwayat.append({"role":"user","content":pesan+ctx})
    if len(riwayat)>MAKS_RIWAYAT: riwayat=riwayat[-MAKS_RIWAYAT:]; riwayat_chat[nomor]=riwayat
    for attempt in range(3):
        try:
            r = requests.post("https://api.anthropic.com/v1/messages",
                headers={"x-api-key":ANTHROPIC_API_KEY,"content-type":"application/json","anthropic-version":"2023-06-01"},
                json={"model":"claude-sonnet-4-6","max_tokens":1024,"system":SYSTEM_PROMPT,"messages":riwayat}, timeout=60)
            if r.status_code==200:
                j=r.json()["content"][0]["text"]; riwayat.append({"role":"assistant","content":j}); riwayat_chat[nomor]=riwayat; return j
            elif r.status_code==529: print(f"[RETRY {attempt+1}]"); time.sleep(5)
            else: print(f"[ERR] {r.status_code}: {r.text}"); break
        except requests.exceptions.Timeout: time.sleep(3)
        except Exception as e: print(f"[ERR] {e}"); break
    return "Maaf Kak, sistem sedang sibuk. Coba chat lagi 1-2 menit ya 🙏"

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json or request.form.to_dict()
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] === PESAN MASUK ===")
    print(f"Data: {json.dumps(data, indent=2, ensure_ascii=False)}")
    nomor = data.get("sender",""); pesan = data.get("message","")
    if not nomor or not pesan: return jsonify({"s":"ignored"}), 200
    if "@g.us" in nomor: return jsonify({"s":"ignored"}), 200
    catat_customer(nomor)
    tipe = data.get("type","text")
    if tipe != "text":
        g = get_garansi_status(nomor)
        if g and g["status"]=="active":
            jml=catat_checkin(nomor)
            kirim_wa(nomor, f"Ok terima kasih Kak, foto ke-{jml} hari ini diterima! 👍" if jml<=4 else "Ok terima kasih Kak, foto diterima! 👍")
            return jsonify({"s":"checkin"}), 200
        kirim_wa(nomor, "Saya memiliki keterbatasan untuk membaca/mengirim file, baik gambar maupun dokumen. Boleh diketik aja ya Kak pertanyaannya 😊")
        return jsonify({"s":"non-text"}), 200
    print(f"[INFO] {nomor}: {pesan}")
    pl = pesan.lower().strip()
    if any(kw in pl for kw in ["daftar garansi","ikut program","nama saya","nama lengkap saya","nama:"]):
        nama = pesan.strip()
        for px in ["nama saya ","nama lengkap saya ","nama: ","daftar garansi ","nama saya: "]:
            if pl.startswith(px): nama=pesan[len(px):].strip(); break
        if 2<len(nama)<100:
            daftar_garansi(nomor,nama)
            mulai=(datetime.now()+timedelta(days=1)).strftime("%d/%m/%Y")
            kirim_wa(nomor, f"Terima kasih Kak {nama}! 🎉\n\nPendaftaran Program 30 Hari Pasti Langsing sudah dicatat!\n\nProgram dimulai BESOK ({mulai}).\n\nMulai besok, kirim 4 foto setiap hari:\n1. Foto sarapan pagi\n2. Foto makan siang\n3. Foto makan malam\n4. Foto sachet Lelixir yang sudah dibuka\n\n30 hari tanpa putus ya Kak! Semangat! 💪")
            return jsonify({"s":"garansi-daftar"}), 200
    jawaban = tanya_claude(nomor, pesan)
    print(f"[INFO] Reply: {jawaban[:100]}...")
    kirim_wa(nomor, jawaban)
    return jsonify({"s":"replied"}), 200

@app.route("/dashboard")
def dashboard():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT nomor,first_chat,last_chat,chat_count,followup_h1_sent,followup_3_sent,followup_10_sent FROM customers ORDER BY last_chat DESC")
    customers = c.fetchall()
    c.execute("SELECT nomor,nama,tanggal_mulai,status,total_checkin,streak,followup_30_sent FROM garansi ORDER BY tanggal_mulai DESC")
    garansi = c.fetchall()
    conn.close()
    def fmt(n):
        return f"+{n[:2]} {n[2:5]}-{n[5:9]}-{n[9:]}" if len(n)>=12 else n
    def badge(s):
        return f'<span style="background:#28a745;color:#fff;padding:2px 8px;border-radius:10px;font-size:12px">Active</span>' if s=="active" else f'<span style="background:#6c757d;color:#fff;padding:2px 8px;border-radius:10px;font-size:12px">{s}</span>'
    def tick(v): return "✅" if v else "⏳"
    cr = "".join([f'<tr style="background:{"#f8f9fa" if i%2==0 else "#fff"}"><td style="padding:10px 14px;font-family:monospace;font-size:14px;white-space:nowrap">{fmt(r[0])}</td><td style="padding:10px 14px;font-size:13px">{r[1][:16] if r[1] else "-"}</td><td style="padding:10px 14px;font-size:13px">{r[2][:16] if r[2] else "-"}</td><td style="padding:10px 14px;text-align:center;font-weight:600">{r[3]}</td><td style="padding:10px 14px;text-align:center">{tick(r[4])}</td><td style="padding:10px 14px;text-align:center">{tick(r[5])}</td><td style="padding:10px 14px;text-align:center">{tick(r[6])}</td></tr>' for i,r in enumerate(customers)])
    gr = "".join([f'<tr style="background:{"#f8f9fa" if i%2==0 else "#fff"}"><td style="padding:10px 14px;font-family:monospace;font-size:14px;white-space:nowrap">{fmt(r[0])}</td><td style="padding:10px 14px;font-weight:500">{r[1]}</td><td style="padding:10px 14px;font-size:13px">{r[2][:10] if r[2] else "-"}</td><td style="padding:10px 14px;text-align:center">{badge(r[3])}</td><td style="padding:10px 14px;text-align:center;font-weight:600">{r[4]}</td><td style="padding:10px 14px;text-align:center;font-weight:600">{r[5]}</td><td style="padding:10px 14px;text-align:center">{tick(r[6])}</td></tr>' for i,r in enumerate(garansi)])
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Lelixir Dashboard</title>
<style>body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;margin:0;padding:20px;background:#f0f2f5;color:#1a1a1a}}.container{{max-width:1200px;margin:0 auto}}h1{{color:#d63384;margin-bottom:5px;font-size:24px}}.sub{{color:#6c757d;margin-bottom:25px;font-size:14px}}.stats{{display:flex;gap:15px;margin-bottom:25px;flex-wrap:wrap}}.sc{{background:#fff;border-radius:12px;padding:20px;flex:1;min-width:150px;box-shadow:0 1px 3px rgba(0,0,0,.1)}}.sn{{font-size:32px;font-weight:700;color:#d63384}}.sl{{font-size:13px;color:#6c757d;margin-top:4px}}.sec{{background:#fff;border-radius:12px;padding:20px;margin-bottom:20px;box-shadow:0 1px 3px rgba(0,0,0,.1);overflow-x:auto}}.sec h2{{font-size:18px;margin:0 0 15px;color:#333}}table{{width:100%;border-collapse:collapse;min-width:600px}}th{{background:#f8f9fa;padding:10px 14px;text-align:left;font-size:12px;text-transform:uppercase;color:#6c757d;border-bottom:2px solid #dee2e6;white-space:nowrap}}td{{border-bottom:1px solid #f0f0f0}}.rf{{color:#6c757d;font-size:12px;margin-top:15px;text-align:center}}</style></head><body>
<div class="container"><h1>🩷 Lelixir Dashboard</h1><p class="sub">v2.8 | {datetime.now().strftime("%d/%m/%Y %H:%M")} WIB</p>
<div class="stats"><div class="sc"><div class="sn">{len(customers)}</div><div class="sl">Total Customer</div></div><div class="sc"><div class="sn">{len(garansi)}</div><div class="sl">Peserta Garansi</div></div><div class="sc"><div class="sn">{len([g for g in garansi if g[3]=='active'])}</div><div class="sl">Garansi Aktif</div></div></div>
<div class="sec"><h2>📱 Semua Customer ({len(customers)})</h2><table><tr><th>WhatsApp</th><th>First Chat</th><th>Last Chat</th><th>Chat</th><th>H+1</th><th>D3</th><th>D10</th></tr>{cr}</table></div>
<div class="sec"><h2>🏆 Peserta Garansi ({len(garansi)})</h2><table><tr><th>WhatsApp</th><th>Nama</th><th>Mulai</th><th>Status</th><th>Check-in</th><th>Streak</th><th>D30</th></tr>{gr}</table></div>
<p class="rf">Refresh halaman untuk data terbaru</p></div></body></html>"""

@app.route("/garansi-status/<nomor>")
def cek_garansi(nomor):
    g=get_garansi_status(nomor); return jsonify(g if g else {"error":"Tidak terdaftar"}), 200 if g else 404

@app.route("/")
def home():
    return jsonify({"status":"active","app":"Lelixir AI Agent v2.8","time":datetime.now().strftime("%Y-%m-%d %H:%M:%S")}), 200

@app.route("/health")
def health():
    return jsonify({"status":"healthy"}), 200

if __name__=="__main__":
    print("="*50); print("LELIXIR AI AGENT v2.8"); print("="*50)
    print(f"Claude: {'OK' if ANTHROPIC_API_KEY else 'NOT SET!'}"); print(f"Fonnte: {'OK' if FONNTE_API_KEY else 'NOT SET!'}")
    print("Follow-up: H+1, D3, D10, G30"); print("Dashboard: /dashboard"); print("="*50)
    threading.Thread(target=jalankan_followup, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",5000)), debug=False)
