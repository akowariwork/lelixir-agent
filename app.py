"""
LELIXIR AI AGENT v3.0
"""

from flask import Flask, request, jsonify
import requests, os, json, random, re, sqlite3, threading, time
from datetime import datetime, timedelta

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
FONNTE_API_KEY = os.environ.get("FONNTE_API_KEY", "")
ADMIN_WA_NUMBER = os.environ.get("ADMIN_WA_NUMBER", "628xxxxxxxxxx")

FOLLOWUP_H1 = [
    "Hai Kak! Kemarin sempat chat ya, makasih sudah mampir 😊\n\nPerkenalkan, saya Health Assistant Lelixir — asisten gizi pribadi kakak 24 jam.\n\nKakak bisa nanya apa aja:\n✅ Cara pakai Lelixir supaya hasil maksimal\n✅ Buatkan meal plan harian yang enak\n✅ Tips olahraga ringan\n✅ Nutrisi, diet, intermittent fasting\n\nJangan sungkan ya Kak! 💪",
    "Halo Kak! Salam kenal, saya Health Assistant Lelixir 😊\n\nSaya bisa bantu:\n✅ Konsultasi Lelixir\n✅ Meal plan sesuai target\n✅ Tips diet & olahraga simpel\n✅ Nutrisi, IF, pencernaan\n\nAnggap aja teman yang paham gizi — tanya apapun! ✨",
    "Hi Kak! Kemarin sempat mampir ya 😊\n\nSaya Health Assistant Lelixir — asisten gizi 24 jam.\n\n✅ Cara pakai Lelixir efektif\n✅ Meal plan (termasuk IF)\n✅ Olahraga gampang tapi kelihatan\n✅ Nutrisi & kesehatan umum\n\nSemua boleh, jangan sungkan! 🙌"
]
FOLLOWUP_D3 = [
    "Hai Kak! Udah coba Lelixir? Awal-awal BAB lebih sering — pertanda bagus! Detoksifikasi mulai bekerja. Semangat! 💪",
    "Halo Kak! BAB lebih sering = tanda positif! Usus sedang dibersihkan. Lanjutkan! 🙌",
    "Hi Kak! Sudah 3 hari. Rutin 2 minggu ya, hasilnya mulai kelihatan! Semangat!"
]
FOLLOWUP_D10 = [
    "Hai Kak! Gimana progress? Stock menipis? Re-stock biar nggak putus. Banyak customer susut 5-8 cm! Cek toko terdekat, sering flash sale!",
    "Halo Kak! Stock menipis ya? Hasil terbaik di 30 hari rutin! Cek Shopee Mall OWL! 💪",
    "Hi Kak! Stock mau habis? Jangan putus — konsistensi kuncinya. Cek marketplace, sering flash sale!"
]
FOLLOWUP_G30 = ["Hai Kak {nama}! 🎉\n\nUdah 30 hari Program Pasti Langsing! Selamat! 💪\n\nTurun berapa kg dan cm?\n\nKirim:\n1. Foto timbangan terbaru\n2. Foto lingkar perut terbaru\n\nAkan di-review admin. Ada progress? Cerita dong!"]
GARANSI_MISS = ["Hai Kak {nama} 😊\n\nKemarin nggak sempat upload foto ya? Sayang banget, program garansi gugur 😔\n\nTapi gpp, tetap semangat! Rutin Lelixir hasilnya pasti kelihatan. Banyak yang turun 2-3 kg di minggu pertama! 💪\n\nAda pertanyaan, saya masih bantu ya. Semangat! ✨"]

DB_PATH = "lelixir_customers.db"

def init_db():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS customers (nomor TEXT PRIMARY KEY, first_chat TEXT, last_chat TEXT, chat_count INTEGER DEFAULT 0, followup_h1_sent INTEGER DEFAULT 0, followup_3_sent INTEGER DEFAULT 0, followup_10_sent INTEGER DEFAULT 0)")
    c.execute("CREATE TABLE IF NOT EXISTS garansi (nomor TEXT PRIMARY KEY, nama TEXT, tanggal_daftar TEXT, tanggal_mulai TEXT, status TEXT DEFAULT 'pending', total_checkin INTEGER DEFAULT 0, last_checkin_date TEXT, streak INTEGER DEFAULT 0, followup_30_sent INTEGER DEFAULT 0, miss_notified INTEGER DEFAULT 0)")
    c.execute("CREATE TABLE IF NOT EXISTS checkin_log (id INTEGER PRIMARY KEY AUTOINCREMENT, nomor TEXT, tanggal TEXT, jumlah_foto INTEGER DEFAULT 0, timestamp TEXT)")
    conn.commit(); conn.close()

def catat_customer(nomor):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor(); now = datetime.now().isoformat()
    c.execute("SELECT chat_count FROM customers WHERE nomor=?", (nomor,)); row = c.fetchone()
    if row: c.execute("UPDATE customers SET last_chat=?, chat_count=? WHERE nomor=?", (now, row[0]+1, nomor))
    else: c.execute("INSERT INTO customers VALUES (?,?,?,1,0,0,0)", (nomor, now, now))
    conn.commit(); conn.close()

def get_fu_h1():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT nomor FROM customers WHERE date(first_chat)=? AND chat_count<=3 AND followup_h1_sent=0", ((datetime.now()-timedelta(days=1)).isoformat()[:10],))
    r = [row[0] for row in c.fetchall()]; conn.close(); return r

def get_fu(hari, field):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    t=(datetime.now()-timedelta(days=hari)).isoformat()[:10]; p=(datetime.now()-timedelta(days=hari+1)).isoformat()[:10]
    c.execute(f"SELECT nomor FROM customers WHERE date(first_chat)<=? AND date(first_chat)>=? AND {field}=0",(t,p))
    r=[row[0] for row in c.fetchall()]; conn.close(); return r

def mark_fu(nomor, field):
    conn=sqlite3.connect(DB_PATH); c=conn.cursor(); c.execute(f"UPDATE customers SET {field}=1 WHERE nomor=?",(nomor,)); conn.commit(); conn.close()

def get_garansi(nomor):
    conn=sqlite3.connect(DB_PATH); c=conn.cursor(); c.execute("SELECT * FROM garansi WHERE nomor=?",(nomor,)); row=c.fetchone(); conn.close()
    if row: return {"nomor":row[0],"nama":row[1],"tanggal_daftar":row[2],"tanggal_mulai":row[3],"status":row[4],"total_checkin":row[5],"last_checkin_date":row[6],"streak":row[7],"followup_30_sent":row[8] if len(row)>8 else 0,"miss_notified":row[9] if len(row)>9 else 0}
    return None

def check_miss():
    conn=sqlite3.connect(DB_PATH); c=conn.cursor(); y=(datetime.now()-timedelta(days=1)).isoformat()[:10]
    c.execute("SELECT nomor,nama FROM garansi WHERE status='active' AND miss_notified=0 AND date(tanggal_mulai)<=?",(y,))
    missed=[]
    for n,nm in c.fetchall():
        c.execute("SELECT jumlah_foto FROM checkin_log WHERE nomor=? AND tanggal=?",(n,y)); row=c.fetchone()
        if (row[0] if row else 0)<4: missed.append((n,nm)); c.execute("UPDATE garansi SET status='failed',miss_notified=1 WHERE nomor=?",(n,))
    conn.commit(); conn.close(); return missed

def has_garansi(nomor):
    conn=sqlite3.connect(DB_PATH); c=conn.cursor(); c.execute("SELECT status FROM garansi WHERE nomor=?",(nomor,)); row=c.fetchone(); conn.close(); return row is not None

def get_g30():
    conn=sqlite3.connect(DB_PATH); c=conn.cursor()
    t=(datetime.now()-timedelta(days=30)).isoformat()[:10]; p=(datetime.now()-timedelta(days=31)).isoformat()[:10]
    c.execute("SELECT nomor,nama FROM garansi WHERE date(tanggal_mulai)<=? AND date(tanggal_mulai)>=? AND status='active' AND followup_30_sent=0",(t,p))
    r=[(row[0],row[1]) for row in c.fetchall()]; conn.close(); return r

def mark_g30(nomor):
    conn=sqlite3.connect(DB_PATH); c=conn.cursor(); c.execute("UPDATE garansi SET followup_30_sent=1 WHERE nomor=?",(nomor,)); conn.commit(); conn.close()

def reg_garansi(nomor, nama):
    conn=sqlite3.connect(DB_PATH); c=conn.cursor(); now=datetime.now().isoformat(); mulai=(datetime.now()+timedelta(days=1)).isoformat()[:10]
    c.execute("INSERT INTO garansi VALUES (?,?,?,?,'active',0,'',0,0,0) ON CONFLICT(nomor) DO UPDATE SET nama=?,tanggal_daftar=?,tanggal_mulai=?,status='active',total_checkin=0,last_checkin_date='',streak=0,followup_30_sent=0,miss_notified=0",(nomor,nama,now,mulai,nama,now,mulai))
    conn.commit(); conn.close()

def checkin(nomor):
    conn=sqlite3.connect(DB_PATH); c=conn.cursor(); td=datetime.now().isoformat()[:10]; now=datetime.now().isoformat()
    c.execute("SELECT jumlah_foto FROM checkin_log WHERE nomor=? AND tanggal=?",(nomor,td)); row=c.fetchone()
    if row: nc=row[0]+1; c.execute("UPDATE checkin_log SET jumlah_foto=?,timestamp=? WHERE nomor=? AND tanggal=?",(nc,now,nomor,td))
    else: nc=1; c.execute("INSERT INTO checkin_log (nomor,tanggal,jumlah_foto,timestamp) VALUES (?,?,1,?)",(nomor,td,now))
    g=get_garansi(nomor)
    if g and g["status"]=="active":
        ld=g["last_checkin_date"]; s=g["streak"] if ld==td else (g["streak"]+1 if(ld==(datetime.now()-timedelta(days=1)).isoformat()[:10] or ld=="") else 1)
        c.execute("UPDATE garansi SET total_checkin=?,last_checkin_date=?,streak=? WHERE nomor=?",(g["total_checkin"]+1,td,s,nomor))
    conn.commit(); conn.close(); return nc

def send_wa(nomor, pesan):
    try:
        r=requests.post("https://api.fonnte.com/send",headers={"Authorization":FONNTE_API_KEY},json={"target":nomor,"message":pesan,"typing":True},timeout=15)
        if r.status_code==200: print(f"[OK] {nomor}"); return True
        print(f"[ERR] {r.status_code}"); return False
    except Exception as e: print(f"[ERR] {e}"); return False

def scheduler():
    print("[SCHED] Started")
    while True:
        try:
            now=datetime.now()
            if 9<=now.hour<=20:
                print(f"[SCHED] {now.strftime('%Y-%m-%d %H:%M')}")
                if now.hour==9:
                    for n,nm in check_miss(): send_wa(n,GARANSI_MISS[0].replace("{nama}",nm)); time.sleep(3)
                for n in get_fu_h1(): send_wa(n,random.choice(FOLLOWUP_H1)); mark_fu(n,"followup_h1_sent"); time.sleep(3)
                for n in get_fu(3,"followup_3_sent"): send_wa(n,random.choice(FOLLOWUP_D3)); mark_fu(n,"followup_3_sent"); time.sleep(3)
                for n in get_fu(10,"followup_10_sent"): send_wa(n,random.choice(FOLLOWUP_D10)); mark_fu(n,"followup_10_sent"); time.sleep(3)
                for n,nm in get_g30(): send_wa(n,FOLLOWUP_G30[0].replace("{nama}",nm)); mark_g30(n); time.sleep(3)
        except Exception as e: print(f"[SCHED ERR] {e}")
        time.sleep(3600)

SYSTEM_PROMPT = r"""# AI AGENT LELIXIR v3.0

## IDENTITAS
Health Assistant Lelixir. JANGAN bilang AI/bot. "Saya Health Assistant Lelixir"
File: "Saya memiliki keterbatasan untuk membaca/mengirim file. Boleh diketik aja ya Kak"

## PRINSIP
1. 90% sudah beli, fokus SUPPORT. 2. Soft sell setelah bbrp chat. 3. Lelixir DI AWAL meal plan. 4. Akhiri SEMANGAT.
5. ESKALASI: SELALU konfirmasi dulu sebelum eskalasi.

## DETOX USUS: Usus simpan endapan 2-10 kg. Awal kehitaman+bau = NORMAL. Rutin 2 minggu: segar, cerah, susut.

## GARANSI 30 HARI
Tawarkan setelah jawab pertanyaan PERTAMA customer baru. 1 peserta 1x saja. Lupa 1 hari = GUGUR.
Syarat: 3 Box, foto stock+resi, nama, foto BB+LP cm. 30 hari 4 foto/hari.
BB tidak turun 3 kg ATAU LP tidak susut 3 cm = uang kembali 100%.
MENDAFTARKAN: konfirmasi+nama -> [DAFTAR_GARANSI:Nama] di akhir. Sekali saja. Sudah pernah = tolak.
Claim: konfirmasi eskalasi -> "Foto dianalisa Admin. 4 hari admin chat pengembalian."
Gagal hari pertama: tawarkan eskalasi (konfirmasi dulu).

## HARGA: 1 Box Rp 145.000 | 2 Box Rp 285.000 | 3 Box Rp 425.000 (RECOMMENDED)

## LINK: SELALU "Cek aja dulu Kak, sering ada promo flash sale dan free produk!"
Jaksel: Spencer https://s.shopee.co.id/9ALdD7gJI8 | Mealblend https://s.shopee.co.id/20sSgZn5yr
Jakbar: Hotto https://s.shopee.co.id/7VDPEOPBXg | Spencers https://s.shopee.co.id/3B4Q4efrzq
Jakut: Purnomo https://s.shopee.co.id/902D10RiTH | Hotto_id https://s.shopee.co.id/20sSgZn5yr
Sby Timur: Lala https://s.shopee.co.id/3g0gf3iVQE | Sby Barat: Healthy https://s.shopee.co.id/9zukCuzXzV
Sby Pusat(Mall): OWL https://s.shopee.co.id/8V5wQ0na9y | Jogja: 242you https://s.shopee.co.id/6Ai1e2oWVx

## KOMPETITOR: "Double Action, satu-satunya fokus lingkar perut." Vs obat: "Bukan obat, holistik alami."
## REBOUND: "Perbaiki dasar, sustainable." KETERGANTUNGAN: "Alami, kayak buah naga."
## ED: Dekat 2-3bln aman HACCP. Terima ED<60hari dari distributor resmi: tukar. Lewat ED: penurunan khasiat.
## LEGALITAS: BPOM 272882011400050 | Halal ID32410029283580925 | PT Aimfood | PT Mega Bintang Sembilan
Bukti: BPOM https://drive.google.com/file/d/1dOpe3MfK0RkvEFmwwBPqecuYCxwxyCm3/view?usp=sharing | Halal https://drive.google.com/file/d/1YBhfqc60AAI2JmPu5SCI-sy0ubP3FeYy/view?usp=sharing
Verifikasi: BPOM https://cekbpom.pom.go.id | Halal https://bpjph.halal.go.id/search/sertifikat?nama_produk

## PRODUK: LELIXIR, Blackcurrant, 10 sachet @30ml, 15 kkal, 2g gula Stevia, BPOM HALAL HACCP. Double Action.
## INGREDIENTS: Booster(L-Carnitine,Guarana,Green Tea). Detox(Polydextrose,Inulin,Aloe Vera,Prune,Spirulina). Pendukung(Blackcurrant,Red Beet,Mushroom,VitMin,Steviol).
## KONSUMSI: Setelah makan siang/malam. Jangan perut kosong.
## KONDISI: Hamil/Menyusui TIDAK. Maag AMAN setelah makan. Hipertensi monitor. Diabetes aman.
## DISCLAIMER: "Ini saran edukatif, bukan pengganti konsultasi dokter."

## NUTRISI
1.HINDARI GULA 2.JEDA MAKAN NOL KALORI(air,teh tawar,kopi hitam) 3.KARBO 1/2 porsi 4.SERAT 5.PROTEIN 6.AIR 2L 7.IF+Lelixir=terbaik
BUAH harus UTUH(bukan jus!). Hindari durian. Pisang HANYA pagi.
HINDARI: gula, es teh manis, jus buah, snacking, durian, gorengan deep fry, minuman kemasan manis.
LAKUKAN: nasi 1/2, protein+sayur banyak, air 2L, Lelixir setelah makan(pengganti dessert), buah utuh, tidur 7-8jam, jalan kaki 30min.

## MEAL PLAN — PENYAJIAN PER 2 HARI

Kalau customer minta meal plan: sajikan per 2 HARI. Di akhir bilang "Kakak tinggal bilang 'ok lanjut' untuk 2 hari berikutnya ya! 😊"
Customer bilang lanjut -> kasih 2 hari berikutnya. 15 kali lanjut = 30 hari lengkap.
Di akhir hari 29-30: "Selamat Kak, meal plan 30 hari sudah lengkap! Semangat! 💪"

Dosis Lelixir: Target 1-6 kg = 1 sachet setelah siang. Target 7 kg+ = 2 sachet siang+malam.

FORMAT: 🌅PAGI | 🍎BUAH | ☀️SIANG+Lelixir | 🌙MALAM+Lelixir | 📝Tips

JANGAN: brand lain, ayam rebus(kecuali diminta), snack di jeda, jus buah.
HARUS: Lelixir di AWAL, makanan enak(ayam goreng tanpa tepung, telur goreng/scramble, ikan bakar, tempe goreng), bervariasi SETIAP HARI.

### DATABASE PROTEIN:
Telur(rebus/scramble/omelette/poached/dadar), Dada Ayam Panggang, Ayam Bakar Kecap(less sugar), Paha Ayam Sautee, Salmon Panggang, Dori Pan Sear, Kakap Bakar Sambal Matah, Tuna Steak, Udang Garlic Butter, Cumi Bakar, Beef Steak Sirloin, Yakiniku, Rendang(less santan), Tempe Bacem(less sugar), Tahu Crispy AF, Chicken Katsu AF, Gurame Bakar, Ayam Geprek AF, Smoked Salmon, Greek Yogurt, Bebek AF, Pecel Lele AF, Ayam Rica-Rica, Sate Ayam, Opor Ayam(less santan), Pecel Ayam, Ayam Penyet AF, Sop Iga, Rawon, Empal Gentong(less santan), Gulai Ikan, Capcay Seafood, Sup Ikan Batam, Ayam BBQ Homemade, Pepes Ikan Mas, Tom Yum Udang, Nasi Campur Bali style, Thai Basil Chicken.

### DATABASE KARBO (selalu 1/2):
Nasi Putih, Nasi Merah, Nasi Shirataki, Roti Whole Wheat, Sourdough, Oatmeal, Ubi Jalar, Kentang Rebus, Spaghetti WW, Penne WW, Tortilla Wrap WW, Quinoa.

### DATABASE SAYUR:
Brokoli, Bayam, Kangkung, Sawi/Pak Choy, Kacang Panjang, Wortel, Terong, Zucchini, Paprika, Timun Jepang, Asparagus, Mixed Salad, Labu Siam, Jamur, Edamame.

### DATABASE BUAH (UTUH!):
BOLEH: Apel, Pir, Jeruk, Strawberry, Blueberry, Kiwi, Pepaya(sedikit), Alpukat, Dragon Fruit, Anggur(10-15butir).
PAGI SAJA: Pisang(max 1), Semangka(sedikit), Mangga(sedikit). HINDARI: Durian.

### SARAPAN variasi:
Telur+Sourdough+Kopi | Overnight Oat(oat+yogurt+buah+chia)+Telur | Scrambled+Roti WW+Alpukat+Kopi | Telur+Tortilla Wrap+Kopi | Smoothie Bowl+Telur | Poached Eggs+Sourdough+Smoked Salmon | Telur+Ubi Jalar+Kopi | French Toast WW+Kopi | Egg Wrap(dadar+ayam suwir+paprika+keju)

### 30 HARI MEAL PLAN:

W1D1: Pagi=Telur Rebus2+Sourdough+Kopi. Buah=Apel. Siang=Nasi1/2+Ayam Bakar Kecap+Kangkung+Lelixir. Malam=NasiMerah1/2+Kakap Sambal Matah+Labu Siam+Lelixir.
W1D2: Pagi=OvernightOat(yogurt+strawberry+chia)+TelurRebus. Buah=Pir. Siang=Nasi1/2+Dori PanSear+Brokoli+Lelixir. Malam=SpaghettiWW1/2+Udang GarlicButter+Salad+Lelixir.
W1D3: Pagi=Scrambled+RotiWW+Alpukat+Kopi. Buah=Kiwi. Siang=Nasi1/2+AyamGeprekAF+Sawi+Lelixir. Malam=NasiMerah1/2+Salmon Lemon+Asparagus+Lelixir.
W1D4: Pagi=OvernightOat(almond+blueberry)+TelurRebus. Buah=Jeruk. Siang=Nasi1/2+CumiBarKecap+KacangPanjang+Lelixir. Malam=KentangRebus+BeefSteak+Mushroom+Paprika+Lelixir.
W1D5: Pagi=TelurOrakArik+TortillaWrap+Kopi. Buah=DragonFruit. Siang=Nasi1/2+TempeBacem+TerongBalado+Bayam+Lelixir. Malam=NasiShirataki+TunaSear+Edamame+Salad+Lelixir.
W1D6: Pagi=OvernightOat(pisang+PB+cinnamon)+Kopi. Buah=Anggur10-15. Siang=ChickenKatsuAF+Nasi1/2+SaladPaprikaTimun+Lelixir. Malam=PenneWW AglioOlio+Udang+Brokoli+Lelixir.
W1D7: Pagi=PoachedEggs+Sourdough+SmokedSalmon+Alpukat+Kopi. Buah=Strawberry. Siang=NasiMerah1/2+GurameBakarRicaRica+Urap+Lelixir. Malam=QuinoaBowl+Yakiniku+Zucchini+Jamur+Lelixir.

W2D8: Pagi=TelurRebus2+UbiJalar+Kopi. Buah=Pir. Siang=Nasi1/2+PecelAyam+Bayam+KacangPanjang+Lelixir. Malam=NasiMerah1/2+SalmonTeriyaki+PakChoy+Lelixir.
W2D9: Pagi=OvernightOat(yogurt+kiwi+granola)+TelurRebus. Buah=Apel. Siang=WrapWW AyamPanggang+Paprika+Selada+Lelixir. Malam=Nasi1/2+RendangLessSantan+LabuSiam+Lelixir.
W2D10: Pagi=Scrambled+RotiWW+TomatCherry+Kopi. Buah=Jeruk. Siang=Nasi1/2+TahuCrispyAF+KangkungTerasi+Lelixir. Malam=SpaghettiBologneseWW+Salad+Lelixir.
W2D11: Pagi=OvernightOat(susuOat+apel+kayuManis+almond)+TelurRebus. Buah=Blueberry. Siang=NasiMerah1/2+AyamTaliwang+PlecingKangkung+Lelixir. Malam=KentangMashed+AyamPanggangHerbs+Asparagus+Brokoli+Lelixir.
W2D12: Pagi=TelurDadar2+Sourdough+Alpukat+Kopi. Buah=DragonFruit. Siang=RiceBowl Nasi1/2+SalmonSear+Edamame+Kyuri+Nori+Lelixir. Malam=NasiShirataki+UdangSausPadang+WortelBuncis+Lelixir.
W2D13: Pagi=SmoothieBowl(yogurt+blueberry+oat+chia)+TelurRebus+Kopi. Buah=Pepaya. Siang=Nasi1/2+SopIgaSapi+Sayuran+Lelixir. Malam=ZucchiniNoodles+PestoChicken+Tomat+Lelixir.
W2D14: Pagi=EggsBenedict+Sourdough+SmokedSalmon+Kopi. Buah=Strawberry+Blueberry. Siang=NasiMerah1/2+AyamPenyetAF+Lalapan+Lelixir. Malam=SteakSirloin+SweetPotatoMash+Mushroom+Asparagus+Lelixir.

W3D15: Pagi=TelurRebus2+RotiWW+SelaiKacang+Kopi. Buah=Kiwi. Siang=Nasi1/2+IkanBawalBakar+Terong+SayurAsem+Lelixir. Malam=NasiMerah1/2+AyamBBQ+Coleslaw+Lelixir.
W3D16: Pagi=OvernightOat(almond+pir+walnut+cinnamon)+TelurRebus. Buah=Apel. Siang=Nasi1/2+CapcaySeafood+Lelixir. Malam=PenneArrabbiata+GrilledChicken+Salad+Lelixir.
W3D17: Pagi=EggWrap(dadar+ayamSuwir+paprika+keju)+Kopi. Buah=Jeruk. Siang=NasiMerah1/2+PepesIkanMas+KacangPanjang+Lalapan+Lelixir. Malam=TomYumUdang+NasiShirataki+Lelixir.
W3D18: Pagi=OvernightOat(yogurt+dragonFruit+granola)+TelurRebus+Kopi. Buah=Pir. Siang=Nasi1/2+AyamRicaRica+BayamJagung+Lelixir. Malam=TortillaWrap BeefYakiniku+Selada+Timun+Paprika+Lelixir.
W3D19: Pagi=Scrambled+Sourdough+Tomat+MushroomSautee+Kopi. Buah=Anggur. Siang=Nasi1/2+SateAyam+Lontong1/2+Acar+Lelixir. Malam=SalmonBowl Quinoa+Alpukat+Edamame+Nori+Lelixir.
W3D20: Pagi=SmoothieBowl(yogurt+strawberry+oat+almond)+TelurRebus+Kopi. Buah=Blueberry. Siang=NasiMerah1/2+GulaiKakap+DaunSingkong+Lelixir. Malam=ChickenCaesarSalad+Sourdough1slice+Lelixir.
W3D21: Pagi=EggsFlorentine(PoachedEgg+BayamSautee+EnglishMuffin)+Kopi. Buah=DragonFruit. Siang=Nasi1/2+RawonDaging+Tauge+TelurAsin+Lelixir. Malam=TunaTatakiBowl Shirataki+Kyuri+Wortel+Sesame+Lelixir.

W4D22: Pagi=TelurRebus2+UbiJalar+Alpukat+Kopi. Buah=Apel. Siang=Nasi1/2+OporAyam(lessSantan)+LabuSiam+Lelixir. Malam=NasiMerah1/2+DoriSausLemonButter+Brokoli+Wortel+Lelixir.
W4D23: Pagi=OvernightOat(susuOat+mangga+kelapaSerut+chia)+TelurRebus. Buah=Kiwi. Siang=NasiMerah1/2+BebekAF+Lalapan+Sambal+Lelixir. Malam=SpaghettiAglioOlio+CumiSautee+Paprika+Zucchini+Lelixir.
W4D24: Pagi=FrenchToast(WW+telur+cinnamon)+Kopi. Buah=Pir. Siang=Nasi1/2+PecelLeleAF+SambalTerasi+Lalapan+Lelixir. Malam=ThaiBasilChicken+NasiShirataki+Buncis+Lelixir.
W4D25: Pagi=OvernightOat(yogurt+apel+kayuManis+pecan)+TelurRebus+Kopi. Buah=Jeruk. Siang=WrapWW TunaSalad+Selada+Tomat+Timun+Lelixir. Malam=NasiMerah1/2+EmpalGentong(lessSantan)+Kangkung+Lelixir.
W4D26: Pagi=Scrambled+SmokedSalmon+Sourdough+Alpukat+Kopi. Buah=Strawberry. Siang=Nasi1/2+SupIkanBatam+Sayuran+Lelixir. Malam=SteakTenderloin+SweetPotatoMash+Asparagus+Mushroom+Lelixir.
W4D27: Pagi=SmoothieBowl(yogurt+mixedBerry+oat+almond+chia)+TelurRebus. Buah=Pepaya. Siang=NasiMerah1/2+NasiCampurBali(ayamSuwir+sateLilit+lawar)+Lelixir. Malam=PrawnPadThai(shirataki)+Tauge+Kacang+Lime+Lelixir.
W4D28: Pagi=EggsBenedict+SmokedSalmon+Sourdough+Kopi. Buah=Anggur+Blueberry. Siang=NasiKuning1/2+AyamGorengBumbuKuning+PerkedAF+Urap+Lelixir. Malam=Surf&Turf BeefSteak+UdangGrill+CaesarSalad+Brokoli+Lelixir.

D29-30: Ulangi menu favorit dari W1-W4 yang paling disukai, atau variasi baru dari database.

Sajikan 2 hari per chat. Akhiri: "Kakak tinggal bilang 'ok lanjut' untuk 2 hari berikutnya ya! 😊"
Hari 29-30: "Selamat Kak, meal plan 30 hari lengkap! Semangat! 💪"
Lelixir = dessert pengganti manis setelah makan. Manis segar, satisfying, bantu craving gula!

## OLAHRAGA: L1 jalan kaki 15-30min. L2 cardio+resistance. L3 HIIT. L4 HIIT+HYROX. Konsistensi>intensitas.

## LARANGAN: klaim menyembuhkan, aman hamil/menyusui, hasil pasti, jelek-jelekkan kompetitor, brand lain di meal plan, ayam rebus, snack di jeda, jus buah, luar topik, panjang, GGL, jualan chat pertama, bilang AI/bot, eskalasi tanpa konfirmasi."""

app = Flask(__name__)
riwayat_chat = {}
MAKS_RIWAYAT = 20
init_db()
sched_started = False
def start_sched():
    global sched_started
    if not sched_started: sched_started=True; threading.Thread(target=scheduler,daemon=True).start(); print("[SCHED] ✅ Started")
start_sched()

def ask_claude(nomor, pesan):
    if nomor not in riwayat_chat: riwayat_chat[nomor]=[]
    riwayat=riwayat_chat[nomor]; g=get_garansi(nomor); ctx=""
    if g and g["status"]=="active": ctx=f"\n[GARANSI AKTIF] {g['nama']}, mulai {g['tanggal_mulai']}, checkin {g['total_checkin']}, streak {g['streak']}."
    elif g and g["status"]=="failed": ctx=f"\n[GARANSI GAGAL] {g['nama']}."
    if has_garansi(nomor): ctx+="\n[INFO] Sudah pernah ikut garansi."
    riwayat.append({"role":"user","content":pesan+ctx})
    if len(riwayat)>MAKS_RIWAYAT: riwayat=riwayat[-MAKS_RIWAYAT:]; riwayat_chat[nomor]=riwayat
    for _ in range(3):
        try:
            r=requests.post("https://api.anthropic.com/v1/messages",headers={"x-api-key":ANTHROPIC_API_KEY,"content-type":"application/json","anthropic-version":"2023-06-01"},json={"model":"claude-sonnet-4-6","max_tokens":1024,"system":SYSTEM_PROMPT,"messages":riwayat},timeout=60)
            if r.status_code==200: j=r.json()["content"][0]["text"]; riwayat.append({"role":"assistant","content":j}); riwayat_chat[nomor]=riwayat; return j
            elif r.status_code==529: time.sleep(5)
            else: print(f"[ERR] {r.status_code}: {r.text}"); break
        except: time.sleep(3)
    return "Maaf Kak, sistem sedang sibuk. Coba chat lagi 1-2 menit ya 🙏"

def proc_tag(nomor, jawaban):
    m=re.search(r'\[DAFTAR_GARANSI:(.+?)\]',jawaban)
    if m:
        nm=m.group(1).strip()
        if not has_garansi(nomor): reg_garansi(nomor,nm); print(f"[GAR] {nm}({nomor})")
        jawaban=re.sub(r'\s*\[DAFTAR_GARANSI:.+?\]\s*','',jawaban).strip()
    return jawaban

@app.route("/webhook",methods=["POST"])
def webhook():
    data=request.json or request.form.to_dict()
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] === PESAN MASUK ===")
    nomor=data.get("sender",""); pesan=data.get("message","")
    if not nomor or not pesan or "@g.us" in nomor: return jsonify({"s":"ignored"}),200
    catat_customer(nomor)
    if data.get("type","text")!="text":
        g=get_garansi(nomor)
        if g and g["status"]=="active":
            j=checkin(nomor); send_wa(nomor,f"Ok terima kasih Kak, foto ke-{j} hari ini diterima! 👍" if j<=4 else "Ok terima kasih Kak, foto diterima! 👍")
            return jsonify({"s":"checkin"}),200
        send_wa(nomor,"Saya memiliki keterbatasan untuk membaca/mengirim file. Boleh diketik aja ya Kak 😊")
        return jsonify({"s":"non-text"}),200
    print(f"[INFO] {nomor}: {pesan}")
    jawaban=ask_claude(nomor,pesan); jawaban=proc_tag(nomor,jawaban)
    print(f"[INFO] Reply: {jawaban[:100]}..."); send_wa(nomor,jawaban)
    return jsonify({"s":"replied"}),200

@app.route("/dashboard")
def dashboard():
    conn=sqlite3.connect(DB_PATH); c=conn.cursor()
    c.execute("SELECT nomor,first_chat,last_chat,chat_count,followup_h1_sent,followup_3_sent,followup_10_sent FROM customers ORDER BY last_chat DESC"); custs=c.fetchall()
    c.execute("SELECT nomor,nama,tanggal_mulai,status,total_checkin,streak,followup_30_sent FROM garansi ORDER BY tanggal_mulai DESC"); gars=c.fetchall()
    conn.close()
    def f(n): return f"+{n[:2]} {n[2:5]}-{n[5:9]}-{n[9:]}" if len(n)>=12 else n
    def b(s):
        if s=="active": return '<span style="background:#28a745;color:#fff;padding:2px 8px;border-radius:10px;font-size:12px">Active</span>'
        if s=="failed": return '<span style="background:#dc3545;color:#fff;padding:2px 8px;border-radius:10px;font-size:12px">Failed</span>'
        return f'<span style="background:#6c757d;color:#fff;padding:2px 8px;border-radius:10px;font-size:12px">{s}</span>'
    def t(v): return "✅" if v else "⏳"
    cr="".join([f'<tr style="background:{"#f8f9fa" if i%2==0 else "#fff"}"><td style="padding:10px 14px;font-family:monospace;font-size:14px;white-space:nowrap">{f(r[0])}</td><td style="padding:10px 14px;font-size:13px">{r[1][:16]}</td><td style="padding:10px 14px;font-size:13px">{r[2][:16]}</td><td style="padding:10px 14px;text-align:center;font-weight:600">{r[3]}</td><td style="padding:10px 14px;text-align:center">{t(r[4])}</td><td style="padding:10px 14px;text-align:center">{t(r[5])}</td><td style="padding:10px 14px;text-align:center">{t(r[6])}</td></tr>' for i,r in enumerate(custs)])
    gr="".join([f'<tr style="background:{"#f8f9fa" if i%2==0 else "#fff"}"><td style="padding:10px 14px;font-family:monospace;font-size:14px;white-space:nowrap">{f(r[0])}</td><td style="padding:10px 14px;font-weight:500">{r[1]}</td><td style="padding:10px 14px;font-size:13px">{r[2][:10] if r[2] else "-"}</td><td style="padding:10px 14px;text-align:center">{b(r[3])}</td><td style="padding:10px 14px;text-align:center;font-weight:600">{r[4]}</td><td style="padding:10px 14px;text-align:center;font-weight:600">{r[5]}</td><td style="padding:10px 14px;text-align:center">{t(r[6])}</td></tr>' for i,r in enumerate(gars)])
    ac=len([g for g in gars if g[3]=='active']); fc=len([g for g in gars if g[3]=='failed'])
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Lelixir</title><style>body{{font-family:-apple-system,sans-serif;margin:0;padding:20px;background:#f0f2f5}}.ct{{max-width:1200px;margin:0 auto}}h1{{color:#d63384;font-size:24px}}.sub{{color:#6c757d;margin-bottom:25px;font-size:14px}}.stats{{display:flex;gap:15px;margin-bottom:25px;flex-wrap:wrap}}.sc{{background:#fff;border-radius:12px;padding:20px;flex:1;min-width:120px;box-shadow:0 1px 3px rgba(0,0,0,.1)}}.sn{{font-size:32px;font-weight:700;color:#d63384}}.sl{{font-size:13px;color:#6c757d}}.sec{{background:#fff;border-radius:12px;padding:20px;margin-bottom:20px;box-shadow:0 1px 3px rgba(0,0,0,.1);overflow-x:auto}}.sec h2{{font-size:18px;margin:0 0 15px}}table{{width:100%;border-collapse:collapse;min-width:600px}}th{{background:#f8f9fa;padding:10px 14px;text-align:left;font-size:12px;text-transform:uppercase;color:#6c757d;border-bottom:2px solid #dee2e6;white-space:nowrap}}td{{border-bottom:1px solid #f0f0f0}}.rf{{color:#6c757d;font-size:12px;text-align:center;margin-top:15px}}</style></head><body><div class="ct"><h1>🩷 Lelixir Dashboard</h1><p class="sub">v3.0 | {datetime.now().strftime("%d/%m/%Y %H:%M")} WIB</p><div class="stats"><div class="sc"><div class="sn">{len(custs)}</div><div class="sl">Customer</div></div><div class="sc"><div class="sn">{len(gars)}</div><div class="sl">Garansi</div></div><div class="sc"><div class="sn">{ac}</div><div class="sl">Aktif</div></div><div class="sc"><div class="sn" style="color:#dc3545">{fc}</div><div class="sl">Gagal</div></div></div><div class="sec"><h2>📱 Customer ({len(custs)})</h2><table><tr><th>WA</th><th>First</th><th>Last</th><th>Chat</th><th>H+1</th><th>D3</th><th>D10</th></tr>{cr}</table></div><div class="sec"><h2>🏆 Garansi ({len(gars)})</h2><table><tr><th>WA</th><th>Nama</th><th>Mulai</th><th>Status</th><th>Checkin</th><th>Streak</th><th>D30</th></tr>{gr}</table></div><p class="rf">Refresh untuk data terbaru</p></div></body></html>"""

@app.route("/garansi-status/<nomor>")
def cek_gar(nomor): g=get_garansi(nomor); return jsonify(g if g else {"error":"Tidak terdaftar"}),200 if g else 404

@app.route("/")
def home(): return jsonify({"status":"active","app":"v3.0","scheduler":sched_started}),200

@app.route("/health")
def health(): return jsonify({"status":"healthy","scheduler":sched_started}),200

if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",5000)),debug=False)
