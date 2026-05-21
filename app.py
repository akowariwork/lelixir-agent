"""
===========================================================
LELIXIR AI AGENT — WhatsApp Auto-Reply via Fonnte + Claude
===========================================================

Analogi sederhana:
- File ini = MANAJER TOKO
- Fonnte = PINTU MASUK (terima pesan WA customer)
- Claude = KARYAWAN PINTAR (bikin jawaban)
- System Prompt = BUKU PANDUAN KARYAWAN

Alur:
Customer WA → Fonnte tangkap → Script ini terima →
Script kirim ke Claude + buku panduan → Claude jawab →
Script kirim balik via Fonnte → Customer terima balasan

===========================================================
"""

# =====================================================
# BAGIAN 1: IMPORT (Alat-alat yang dibutuhkan)
# =====================================================
# Ini kayak "bawa peralatan kerja" sebelum mulai
# Flask = bikin server kecil yang bisa terima pesan dari Fonnte
# requests = alat untuk kirim/terima data ke Claude & Fonnte
# os = baca pengaturan rahasia (API key dll)
# json = baca/tulis data format JSON
# datetime = catat waktu

from flask import Flask, request, jsonify
import requests
import os
import json
from datetime import datetime

# =====================================================
# BAGIAN 2: PENGATURAN RAHASIA (API Keys)
# =====================================================
# Ini kayak "kunci toko" — jangan kasih ke siapapun!
# Nanti di server, kita simpan ini sebagai "Environment Variables"
# supaya nggak kelihatan di kode

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "ISI_API_KEY_CLAUDE_KAMU_DISINI")
FONNTE_API_KEY = os.environ.get("FONNTE_API_KEY", "ISI_API_KEY_FONNTE_KAMU_DISINI")

# Nomor WA admin manusia (untuk eskalasi)
ADMIN_WA_NUMBER = os.environ.get("ADMIN_WA_NUMBER", "628xxxxxxxxxx")

# =====================================================
# BAGIAN 3: BUKU PANDUAN KARYAWAN (System Prompt)
# =====================================================
# Ini isi dari file FINAL_system_prompt_lelixir_agent.md
# yang sudah kamu buat. PASTE seluruh isinya di sini.
# System prompt inilah yang bikin AI jawab sesuai
# karakter Lelixir — bukan jawab ngawur.

SYSTEM_PROMPT = """

PASTE SELURUH ISI FILE "FINAL_system_prompt_lelixir_agent.md" DI SINI.

Hapus baris ini dan ganti dengan isi file-nya.
Pastikan diapit tanda petik tiga (triple quotes) seperti ini.

"""

# =====================================================
# BAGIAN 4: BUAT SERVER (Toko-nya)
# =====================================================
# Flask = toko kecil yang buka 24 jam
# Dia siap terima "tamu" (pesan) kapan saja

app = Flask(__name__)

# Simpan riwayat chat supaya AI ingat konteks percakapan
# Key = nomor WA customer, Value = list pesan sebelumnya
# Catatan: ini disimpan di memori, kalau server restart, hilang
riwayat_chat = {}

# Maksimal berapa pesan yang disimpan per customer
# (supaya nggak kepenuhan memori)
MAKS_RIWAYAT = 20


# =====================================================
# BAGIAN 5: FUNGSI TANYA KE CLAUDE (Karyawan Pintar)
# =====================================================
# Fungsi ini kirim pesan customer ke Claude API,
# beserta buku panduan + riwayat chat sebelumnya,
# lalu terima jawaban dari Claude.

def tanya_claude(nomor_customer, pesan_customer):
    """
    Kirim pesan ke Claude dan dapat jawaban.
    
    Analogi: Manajer toko lari ke karyawan pintar,
    kasih pertanyaan customer + buku panduan,
    lalu bawa jawaban balik.
    """
    
    # --- Ambil riwayat chat customer ini (kalau ada) ---
    if nomor_customer not in riwayat_chat:
        riwayat_chat[nomor_customer] = []
    
    riwayat = riwayat_chat[nomor_customer]
    
    # --- Tambah pesan baru customer ke riwayat ---
    riwayat.append({
        "role": "user",
        "content": pesan_customer
    })
    
    # --- Potong riwayat kalau sudah kepanjangan ---
    if len(riwayat) > MAKS_RIWAYAT:
        riwayat = riwayat[-MAKS_RIWAYAT:]
        riwayat_chat[nomor_customer] = riwayat
    
    # --- Kirim ke Claude API ---
    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "content-type": "application/json",
                "anthropic-version": "2023-06-01"
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 1024,
                "system": SYSTEM_PROMPT,
                "messages": riwayat
            },
            timeout=30
        )
        
        # --- Cek apakah berhasil ---
        if response.status_code == 200:
            data = response.json()
            jawaban = data["content"][0]["text"]
            
            # Simpan jawaban Claude ke riwayat
            riwayat.append({
                "role": "assistant",
                "content": jawaban
            })
            riwayat_chat[nomor_customer] = riwayat
            
            return jawaban
        else:
            print(f"[ERROR] Claude API error: {response.status_code}")
            print(f"[ERROR] Detail: {response.text}")
            return "Maaf Kak, sistem kami sedang maintenance sebentar ya. Coba chat lagi dalam beberapa menit 🙏"
    
    except requests.exceptions.Timeout:
        print("[ERROR] Claude API timeout")
        return "Maaf Kak, sistem lagi sibuk nih. Coba chat lagi dalam 1-2 menit ya 🙏"
    
    except Exception as e:
        print(f"[ERROR] Unexpected error: {str(e)}")
        return "Maaf Kak, ada gangguan teknis. Tim kami sudah ditandai. Coba lagi sebentar ya 🙏"


# =====================================================
# BAGIAN 6: FUNGSI KIRIM BALAS VIA FONNTE
# =====================================================
# Setelah dapat jawaban dari Claude, kirim balik
# ke customer lewat Fonnte (WhatsApp).

def kirim_wa(nomor_tujuan, pesan):
    """
    Kirim pesan WhatsApp via Fonnte API.
    
    Analogi: Manajer toko lari ke pintu depan
    dan kasih jawaban ke customer yang nunggu.
    """
    
    try:
        response = requests.post(
            "https://api.fonnte.com/send",
            headers={
                "Authorization": FONNTE_API_KEY
            },
            json={
                "target": nomor_tujuan,
                "message": pesan,
                "typing": True  # Efek "sedang mengetik..." sebelum kirim
            },
            timeout=15
        )
        
        if response.status_code == 200:
            print(f"[OK] Pesan terkirim ke {nomor_tujuan}")
            return True
        else:
            print(f"[ERROR] Fonnte error: {response.status_code}")
            print(f"[ERROR] Detail: {response.text}")
            return False
    
    except Exception as e:
        print(f"[ERROR] Gagal kirim WA: {str(e)}")
        return False


# =====================================================
# BAGIAN 7: WEBHOOK — PINTU MASUK PESAN
# =====================================================
# Ini "pintu masuk" toko kamu.
# Setiap kali ada customer chat WA, Fonnte akan
# "ketuk pintu" di URL ini dan kasih info pesannya.

@app.route("/webhook", methods=["POST"])
def webhook():
    """
    Terima pesan masuk dari Fonnte.
    
    Alur:
    1. Fonnte kirim data pesan ke sini
    2. Kita baca: siapa yang kirim, isi pesannya apa
    3. Kita tanya ke Claude
    4. Kita kirim jawaban balik via Fonnte
    """
    
    # --- Baca data dari Fonnte ---
    data = request.json or request.form.to_dict()
    
    # Debug: print data yang masuk (hapus ini di production)
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] === PESAN MASUK ===")
    print(f"Data: {json.dumps(data, indent=2, ensure_ascii=False)}")
    
    # --- Ambil info penting ---
    nomor_pengirim = data.get("sender", "")
    pesan_masuk = data.get("message", "")
    
    # --- Abaikan kalau kosong atau dari grup ---
    if not nomor_pengirim or not pesan_masuk:
        return jsonify({"status": "ignored", "reason": "empty"}), 200
    
    # Abaikan pesan dari grup (opsional)
    if "@g.us" in nomor_pengirim:
        return jsonify({"status": "ignored", "reason": "group"}), 200
    
    # --- Handle pesan non-teks (gambar, voice note, dll) ---
    tipe_pesan = data.get("type", "text")
    if tipe_pesan != "text":
        kirim_wa(
            nomor_pengirim,
            "Maaf ya Kak, saat ini saya hanya bisa bantu via chat teks 😊 "
            "Boleh diketik pertanyaannya? Nanti saya jawab selengkap mungkin!"
        )
        return jsonify({"status": "replied", "type": "non-text"}), 200
    
    # --- Proses pesan ---
    print(f"[INFO] Dari: {nomor_pengirim}")
    print(f"[INFO] Pesan: {pesan_masuk}")
    
    # Tanya ke Claude (karyawan pintar)
    jawaban = tanya_claude(nomor_pengirim, pesan_masuk)
    
    print(f"[INFO] Jawaban AI: {jawaban[:100]}...")
    
    # Kirim jawaban ke customer via Fonnte
    kirim_wa(nomor_pengirim, jawaban)
    
    return jsonify({"status": "replied"}), 200


# =====================================================
# BAGIAN 8: HEALTH CHECK (Cek toko buka atau tutup)
# =====================================================
# Endpoint sederhana untuk cek apakah server jalan

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "active",
        "app": "Lelixir AI Agent",
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy"}), 200


# =====================================================
# BAGIAN 9: JALANKAN SERVER
# =====================================================
# Ini tombol ON untuk buka toko

if __name__ == "__main__":
    print("=" * 50)
    print("🚀 LELIXIR AI AGENT — SERVER STARTED")
    print("=" * 50)
    print(f"⏰ Waktu: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🔑 Claude API Key: {'✅ Set' if ANTHROPIC_API_KEY != 'ISI_API_KEY_CLAUDE_KAMU_DISINI' else '❌ BELUM SET!'}")
    print(f"🔑 Fonnte API Key: {'✅ Set' if FONNTE_API_KEY != 'ISI_API_KEY_FONNTE_KAMU_DISINI' else '❌ BELUM SET!'}")
    print("=" * 50)
    
    # Jalankan server di port 5000
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
