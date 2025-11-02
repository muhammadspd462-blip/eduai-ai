"""
api/schemas.py
-----------------------------------------
Berisi model data (schema) untuk validasi input/output API menggunakan Pydantic.
Digunakan oleh: ai_controller.py, db.py, main.py
"""

from pydantic import BaseModel
from typing import List, Optional


# ======================================================
# 🧾 Schema untuk Soal LKPD
# ======================================================
class QuestionOption(BaseModel):
    A: Optional[str] = None
    B: Optional[str] = None
    C: Optional[str] = None
    D: Optional[str] = None


class QuestionItem(BaseModel):
    id: str
    type: str               # "PG" = pilihan ganda, "IS" = isian singkat
    question: str
    options: Optional[QuestionOption] = None
    answer: Optional[str] = None
    score: Optional[float] = 10.0


class LKPDModel(BaseModel):
    title: str
    theme: str
    difficulty: str
    questions: List[QuestionItem]


# ======================================================
# 🧍 Schema untuk Jawaban Siswa
# ======================================================
class AnswerItem(BaseModel):
    id: str
    jawaban: str


class AnswerRequest(BaseModel):
    lkpd_id: str
    name: str
    answers: List[AnswerItem]


# ======================================================
# 📊 Schema untuk Hasil Evaluasi
# ======================================================
class EvaluationResult(BaseModel):
    name: str
    score: float
    max_score: float
    feedback: str


# ======================================================
# 🧩 Schema respons umum
# ======================================================
class LKPDResponse(BaseModel):
    status: str
    data: LKPDModel


class MessageResponse(BaseModel):
    status: str
    message: str
