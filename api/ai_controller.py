# api/ai_controller.py
"""Backend router untuk EduAI — handle generate, submit, rekap, export CSV/XLSX, dll.
Didesain agar tahan terhadap error, race condition I/O, dan responsif.
"""

import os
import json
import csv
import tempfile
from io import BytesIO, StringIO
from datetime import datetime
from typing import List, Dict, Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse

# Import fungsi AI (pastikan api/gemini_config.py tersedia)
from api import gemini_config

router = APIRouter()

# Direktori (bisa disesuaikan lewat env)
LKPD_DIR = os.getenv("LKPD_DIR", "data/lkpd_outputs")
ANSWERS_DIR = os.getenv("ANSWERS_DIR", "data/answers")

# Pastikan direktori ada
os.makedirs(LKPD_DIR, exist_ok=True)
os.makedirs(ANSWERS_DIR, exist_ok=True)


# -------------------------
#  Helper utilities
# -------------------------
def _atomic_write_json(path: str, data: Any) -> None:
    """Tulis JSON secara atomic (tulis ke temp, lalu replace)."""
    dirn = os.path.dirname(path)
    os.makedirs(dirn, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="tmp", dir=dirn, suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)  # atomic replace
    except Exception:
        # Pastikan tmp file dihapus bila error
        try:
            os.remove(tmp)
        except Exception:
            pass
        raise


def _safe_load_json(path: str):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _compute_status(score: float) -> str:
    if score >= 85:
        return "Tinggi"
    if score >= 60:
        return "Cukup"
    return "Perlu Bimbingan"


# -------------------------
#  Endpoint: generate LKPD
# -------------------------
@router.post("/generate")
async def generate_endpoint(payload: Dict[str, Any]):
    """
    Request body (JSON) => { "theme": "Fotosintesis", "level": "mudah" }
    Response => { "id": "abc123", ...lkpd_data }
    """
    try:
        theme = payload.get("theme") or payload.get("tema")
        level = payload.get("level") or payload.get("tingkat") or payload.get("difficulty")
        if not theme or not level:
            raise HTTPException(status_code=400, detail="Parameter 'theme' dan 'level' wajib diisi.")

        # panggil AI generator (gemini_config.generate_lkpd)
        # generate_lkpd expected to return (data_dict, raw_text)
        lkpd_data, raw = gemini_config.generate_lkpd(theme, level)
        if not isinstance(lkpd_data, dict):
            raise HTTPException(status_code=500, detail="AI tidak menghasilkan data LKPD yang valid.")

        # buat id singkat
        lkpd_id = os.urandom(4).hex()
        path = os.path.join(LKPD_DIR, f"{lkpd_id}.json")

        # enrich metadata jika perlu
        lkpd_data.setdefault("title", lkpd_data.get("title", f"LKPD: {theme}"))
        lkpd_data["theme"] = theme
        lkpd_data["difficulty"] = level
        lkpd_data["generated_at"] = datetime.utcnow().isoformat()

        # pastikan questions diseragamkan (id, score, answer)
        qlist = lkpd_data.get("questions", [])
        for i, q in enumerate(qlist, start=1):
            if "id" not in q:
                q["id"] = str(i)
            if "score" not in q:
                q["score"] = q.get("bobot", 10)
            if "answer" not in q:
                q["answer"] = q.get("kunci", "") or ""

        # simpan LKPD (atomic)
        _atomic_write_json(path, lkpd_data)

        response = {"id": lkpd_id, **lkpd_data}
        return JSONResponse(response)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal generate LKPD: {e}")


# -------------------------
#  Endpoint: ambil LKPD
# -------------------------
@router.get("/lkpd/{lkpd_id}")
async def get_lkpd(lkpd_id: str):
    path = os.path.join(LKPD_DIR, f"{lkpd_id}.json")
    data = _safe_load_json(path)
    if not data:
        raise HTTPException(status_code=404, detail="LKPD tidak ditemukan.")
    return JSONResponse(content=data)


# -------------------------
#  Endpoint: submit jawaban siswa
# -------------------------
@router.post("/submit")
async def submit_answers(payload: Dict[str, Any]):
    """
    Body:
    {
      "lkpd_id": "...",
      "name": "Nama Siswa",
      "answers": [ { "id": "1", "jawaban": "A", ... }, ... ]
    }
    """
    try:
        lkpd_id = payload.get("lkpd_id")
        name = payload.get("name") or payload.get("nama")
        answers = payload.get("answers") or payload.get("jawaban") or []

        if not lkpd_id or not name:
            raise HTTPException(status_code=400, detail="Field 'lkpd_id' dan 'name' wajib diisi.")

        lkpd_path = os.path.join(LKPD_DIR, f"{lkpd_id}.json")
        lkpd_data = _safe_load_json(lkpd_path)
        if not lkpd_data:
            raise HTTPException(status_code=404, detail="LKPD tidak ditemukan.")

        # gunakan analyzer untuk menghitung score dan mendapatkan feedback
        try:
            result = gemini_config.analyze_answer_with_ai(lkpd_data, answers, name)
        except Exception as e:
            # fallback: hitung skor otomatis sederhana (PG compare)
            total = 0.0
            max_score = 0.0
            for q in lkpd_data.get("questions", []):
                k = (q.get("answer") or "").strip().upper()
                bobot = float(q.get("score", 10))
                max_score += bobot
                j = next((a.get("jawaban", "") for a in answers if str(a.get("id")) == str(q.get("id"))), "")
                if j and j.strip().upper() == k:
                    total += bobot
            score_pct = round((total / max_score) * 100, 2) if max_score > 0 else 0.0
            result = {
                "name": name,
                "score": score_pct,
                "feedback": "Feedback AI gagal (fallback otomatis terpakai).",
                "max_score": max_score,
                "computed_by": "fallback"
            }

        # tambah metadata
        result["submitted_at"] = datetime.utcnow().isoformat()
        result["answers"] = answers

        # simpan ke answers file (append)
        out_path = os.path.join(ANSWERS_DIR, f"{lkpd_id}.json")
        existing = _safe_load_json(out_path) or []
        existing.append(result)
        _atomic_write_json(out_path, existing)

        return JSONResponse({"message": "Jawaban tersimpan", "result": result})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal submit jawaban: {e}")


# -------------------------
#  Endpoint: list answers / rekap
# -------------------------
@router.get("/answers/{lkpd_id}")
async def list_answers(lkpd_id: str):
    path = os.path.join(ANSWERS_DIR, f"{lkpd_id}.json")
    data = _safe_load_json(path)
    if not data:
        # kembalikan array kosong supaya frontend mudah menangani
        return JSONResponse([])
    # Tambah summary fields per student
    out = []
    for r in data:
        score = float(r.get("score", 0) or 0)
        status = _compute_status(score)
        out.append({
            "name": r.get("name"),
            "score": score,
            "status": status,
            "submitted_at": r.get("submitted_at"),
            "feedback": r.get("feedback", ""),
            "total_questions": len(r.get("answers", []))
        })
    return JSONResponse(out)


# -------------------------
#  Endpoint: export CSV
# -------------------------
@router.get("/export/{lkpd_id}")
async def export_csv(lkpd_id: str):
    path = os.path.join(ANSWERS_DIR, f"{lkpd_id}.json")
    data = _safe_load_json(path)
    if not data:
        raise HTTPException(status_code=404, detail="Belum ada jawaban untuk LKPD ini.")

    # buat CSV di memori
    buf = StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Nama", "Nilai (%)", "Status", "Submitted At", "Feedback"])
    for r in data:
        score = float(r.get("score", 0) or 0)
        status = _compute_status(score)
        writer.writerow([r.get("name"), score, status, r.get("submitted_at", ""), r.get("feedback", "")])
    buf.seek(0)

    filename = f"rekap_{lkpd_id}.csv"
    return StreamingResponse(buf, media_type="text/csv",
                             headers={"Content-Disposition": f"attachment; filename={filename}"})


# -------------------------
#  Endpoint: export XLSX (in-memory)
# -------------------------
@router.get("/export-xlsx/{lkpd_id}")
async def export_xlsx(lkpd_id: str):
    try:
        from openpyxl import Workbook
    except Exception as e:
        raise HTTPException(status_code=500, detail="openpyxl belum terinstal. Tambahkan openpyxl ke requirements.")

    path = os.path.join(ANSWERS_DIR, f"{lkpd_id}.json")
    data = _safe_load_json(path)
    if not data:
        raise HTTPException(status_code=404, detail="Belum ada jawaban untuk LKPD ini.")

    wb = Workbook()
    ws = wb.active
    ws.title = "Rekap Nilai"

    ws.append(["Nama", "Nilai (%)", "Status", "Submitted At", "Feedback"])
    for r in data:
        score = float(r.get("score", 0) or 0)
        status = _compute_status(score)
        ws.append([r.get("name"), score, status, r.get("submitted_at", ""), r.get("feedback", "")])

    stream = BytesIO()
    wb.save(stream)
    stream.seek(0)

    filename = f"rekap_{lkpd_id}.xlsx"
    return StreamingResponse(stream, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f"attachment; filename={filename}"})


# -------------------------
#  Endpoint: list all LKPD ids
# -------------------------
@router.get("/all-ids")
async def all_ids():
    try:
        files = [f for f in os.listdir(LKPD_DIR) if f.endswith(".json")]
        ids = [os.path.splitext(f)[0] for f in files]
        return JSONResponse({"ids": ids})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal membaca list LKPD: {e}")


# -------------------------
#  Endpoint: list models (diagnostic)
# -------------------------
@router.get("/models")
async def list_models():
    try:
        info = gemini_config.list_available_models()
        return JSONResponse(info)
    except Exception as e:
        # jika gemini_config tidak implement list_available_models, beri fallback
        return JSONResponse({"ok": False, "error": str(e)})
