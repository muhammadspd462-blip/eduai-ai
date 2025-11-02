@echo off
echo ======================================
echo 🚀 Menjalankan Server EDUAI-AI
echo ======================================

REM Aktifkan virtual environment (jika ada)
IF EXIST .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
)

REM Jalankan FastAPI menggunakan uvicorn
uvicorn api.main:app --reload --port 8000

pause
