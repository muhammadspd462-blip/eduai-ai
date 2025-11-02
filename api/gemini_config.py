"""
api/gemini_config.py
--------------------------------------
Wrapper koneksi ke Google Gemini API
Aman, stabil, dan siap dipakai untuk LKPD generator & evaluator.
"""

import os
import time
import random
import google.generativeai as genai
from dotenv import load_dotenv

# ======================================================
# 🔐 LOAD API KEY
# ======================================================
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise ValueError("❌ GEMINI_API_KEY tidak ditemukan di file .env!")

try:
    genai.configure(api_key=API_KEY)
    model = genai.GenerativeModel("gemini-1.5-pro")
except Exception as e:
    raise RuntimeError(f"❌ Gagal inisialisasi koneksi ke Gemini API: {e}")

# ======================================================
# ⚙️ UTILITY: retry untuk koneksi API yang kadang timeout
# ======================================================
def safe_generate(prompt: str, max_retries: int = 3, delay: float = 2.0):
    """Pemanggilan API Gemini dengan retry otomatis"""
    for attempt in range(max_retries):
        try:
            response = model.generate_content(prompt)
            if response and response.text:
                return response.text
            else:
                raise ValueError("Respon kosong dari Gemini API.")
        except Exception as e:
            print(f"[WARN] Gagal koneksi Gemini (percobaan {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(delay + random.uniform(0, 1))
            else:
                raise RuntimeError(f"❌ Gagal menghubungi Gemini API setelah {max_retries} percobaan.")

# ======================================================
# 🧠 FUNGSI: GENERATE LKPD
# ======================================================
def generate_lkpd(theme: str, level: str):
    """
    Menghasilkan LKPD otomatis berdasarkan tema dan tingkat kesulitan.
    Return:
      (lkpd_data: dict, raw_text: str)
    """
    prompt = f"""
    Anda adalah asisten guru yang membuat LKPD (Lembar Kerja Peserta Didik).
    Buat LKPD dengan format JSON seperti berikut (JANGAN pakai markdown):

    {{
      "title": "LKPD [judul singkat]",
      "theme": "{theme}",
      "difficulty": "{level}",
      "questions": [
        {{
          "id": "1",
          "type": "PG",  // 'PG' = pilihan ganda, 'IS' = isian singkat
          "question": "Tuliskan pertanyaan di sini",
          "options": {{
            "A": "Pilihan A",
            "B": "Pilihan B",
            "C": "Pilihan C",
            "D": "Pilihan D"
          }},
          "answer": "A",
          "score": 10
        }}
      ]
    }}

    Buat minimal 5 soal bervariasi sesuai tema dan tingkat kesulitan.
    Format harus **JSON valid**, tanpa teks tambahan.
    """

    raw_output = safe_generate(prompt)

    # Cari blok JSON valid
    import re, json
    match = re.search(r"\{[\s\S]*\}", raw_output)
    if not match:
        raise ValueError("❌ Output dari Gemini tidak berisi JSON yang valid.")
    json_str = match.group(0)

    try:
        lkpd_data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"❌ Gagal parse JSON dari Gemini: {e}\nTeks mentah:\n{raw_output[:500]}")

    # Pastikan setiap soal punya ID
    for i, q in enumerate(lkpd_data.get("questions", []), 1):
        if "id" not in q:
            q["id"] = str(i)

    return lkpd_data, raw_output

# ======================================================
# 🧩 FUNGSI: ANALISA JAWABAN SISWA
# ======================================================
def analyze_answer_with_ai(lkpd_data: dict, student_answers: list, student_name: str):
    """
    Membandingkan jawaban siswa dengan kunci jawaban dari LKPD.
    Gunakan Gemini hanya untuk analisis penjelasan & penilaian subyektif.
    Return: dict {"name": ..., "total_score": ..., "feedback": ...}
    """
    # Hitung skor otomatis
    total_score = 0
    max_score = 0
    for q in lkpd_data.get("questions", []):
        kunci = q.get("answer", "").strip().upper()
        bobot = float(q.get("score", 10))
        max_score += bobot

        # cari jawaban siswa
        jawab = next((a["jawaban"] for a in student_answers if a["id"] == q["id"]), "")
        if jawab.strip().upper() == kunci:
            total_score += bobot

    nilai_akhir = round((total_score / max_score) * 100, 2) if max_score > 0 else 0.0

    # Analisis AI (opsional) — untuk feedback kualitatif
    summary_prompt = f"""
    Anda adalah guru yang memberikan umpan balik ringkas terhadap hasil siswa.
    Nama siswa: {student_name}
    Tema LKPD: {lkpd_data.get('theme')}
    Nilai akhir: {nilai_akhir}

    Berikan 2-3 kalimat umpan balik positif dan saran perbaikan.
    Gunakan bahasa Indonesia.
    """

    try:
        feedback = safe_generate(summary_prompt)
    except Exception:
        feedback = "Analisis AI gagal dijalankan. Nilai dihitung otomatis."

    result = {
        "name": student_name,
        "score": nilai_akhir,
        "feedback": feedback.strip(),
        "max_score": max_score,
    }

    return result
