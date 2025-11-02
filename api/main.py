# api/main.py
"""Entry-point FastAPI untuk EduAI.
Mount static web/ (frontend), register router ai_controller.
"""

import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# setup logging sederhana
LOGDIR = os.getenv("LOG_DIR", "logs")
os.makedirs(LOGDIR, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(LOGDIR, "app.log"),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("eduai")

# import router
from api.ai_controller import router as ai_router

app = FastAPI(title="EduAI API", version="1.0")

# CORS - ubah allow_origins di production menjadi domain spesifik
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# buat direktori data (selaras dengan ai_controller)
LKPD_DIR = os.getenv("LKPD_DIR", "data/lkpd_outputs")
ANSWERS_DIR = os.getenv("ANSWERS_DIR", "data/answers")
os.makedirs(LKPD_DIR, exist_ok=True)
os.makedirs(ANSWERS_DIR, exist_ok=True)

# include API router
app.include_router(ai_router, prefix="/api", tags=["AI"])

# Mount frontend static files (web/)
WEB_DIR = os.getenv("WEB_DIR", "web")
if os.path.isdir(WEB_DIR):
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
else:
    logger.warning(f"Direktori web not found: {WEB_DIR}. Static files tidak dimount.")

# root health check
@app.get("/healthz")
def healthz():
    return {"status": "ok", "service": "EduAI API"}

# startup event logging
@app.on_event("startup")
def startup_event():
    logger.info("EduAI API starting up...")
    # optional: log environment info (jangan log API keys)
    logger.info(f"LKPD_DIR={LKPD_DIR} | ANSWERS_DIR={ANSWERS_DIR} | WEB_DIR={WEB_DIR}")
