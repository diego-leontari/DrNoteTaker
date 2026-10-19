import os
from datetime import datetime

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from core.llm import clean_transcript, structure, write_notes
from core.research import research

load_dotenv()

app = FastAPI(title="Doctor Note Taker")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEMO_TRANSCRIPT_PATH = os.path.join(BASE_DIR, "demo_transcript.txt")


class NoteRequest(BaseModel):
    transcript: str
    patient_name: str
    patient_email: str
    doctor_email: str


class SendRequest(BaseModel):
    patient_name: str
    patient_email: str
    doctor_email: str
    doctor_html: str
    patient_html: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/demo")
def demo():
    with open(DEMO_TRANSCRIPT_PATH, "r", encoding="utf-8") as f:
        transcript = f.read()
    return {"transcript": transcript}


# Mailer import with fallback stub so work can continue without PC B.
try:
    from mailer.send import send_email  # type: ignore
except ImportError:  # pragma: no cover - fallback used before merge

    def send_email(to: str, subject: str, html: str) -> dict:  # noqa: ARG001
        print(f"[STUB] email to {to}: {subject}")
        return {"ok": True, "error": None}


@app.post("/api/send")
def send(req: SendRequest):
    date = datetime.now().strftime("%B %d, %Y")
    doctor_result = send_email(
        req.doctor_email,
        f"Clinical note – {req.patient_name} – {date}",
        req.doctor_html,
    )
    patient_result = send_email(
        req.patient_email,
        f"Your visit summary – {date}",
        req.patient_html,
    )
    return {
        "ok": True,
        "doctor": {"ok": bool(doctor_result.get("ok", False)), "error": doctor_result.get("error")},
        "patient": {"ok": bool(patient_result.get("ok", False)), "error": patient_result.get("error")},
    }


@app.get("/api/stt-config")
def stt_config():
    """Tell the frontend which live speech engine to use (Soniox if a key is configured)."""
    return {"provider": "soniox" if os.getenv("SONIOX_API_KEY") else "browser"}


@app.post("/api/soniox-key")
def soniox_key():
    """Mint a short-lived Soniox key for the browser. The real SONIOX_API_KEY never leaves the server."""
    import httpx
    from fastapi import HTTPException

    api_key = os.getenv("SONIOX_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="SONIOX_API_KEY is not configured")
    try:
        resp = httpx.post(
            "https://api.soniox.com/v1/auth/temporary-api-key",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"usage_type": "transcribe_websocket", "expires_in_seconds": 300},
            timeout=15,
        )
    except httpx.HTTPError as exc:
        print(f"[soniox] temporary key request failed: {exc}")
        raise HTTPException(status_code=502, detail="Could not reach Soniox")
    if resp.status_code >= 400:
        print(f"[soniox] temporary key rejected: HTTP {resp.status_code} {resp.text[:200]}")
        raise HTTPException(status_code=502, detail=f"Soniox rejected the key request (HTTP {resp.status_code})")
    data = resp.json()
    return {"api_key": data.get("api_key"), "expires_at": data.get("expires_at")}


class CleanRequest(BaseModel):
    transcript: str


@app.post("/api/clean")
def clean(req: CleanRequest):
    """Polish a raw microphone transcript: fix misheard medical terms, add speaker labels."""
    cleaned = clean_transcript(req.transcript)
    return {"transcript": cleaned, "changed": cleaned.strip() != req.transcript.strip()}


@app.post("/api/note")
def note(req: NoteRequest):
    warnings: list = []

    # 1. LLM structures the transcript into JSON + a clinical question.
    structured = structure(req.transcript)

    # 2. Parallel researches the clinical question.
    research_data = research(structured.get("clinical_question", ""), structured)
    if not research_data:
        warnings.append("Web research unavailable; differential diagnosis may be incomplete.")
        research_data = {
            "differential_diagnosis": [],
            "suggested_tests": [],
            "suggested_management": [],
            "red_flags": [],
            "sources": [],
        }

    # 3. LLM writes the doctor note (SOAP, HTML) and patient summary (HTML).
    doctor_html, patient_html = write_notes(structured, research_data)

    return {
        "doctor_html": doctor_html,
        "patient_html": patient_html,
        "research": research_data,
        "warnings": warnings,
    }


# Mount static frontend LAST so API routes take precedence.
STATIC_DIR = os.path.join(BASE_DIR, "static")
if os.path.isdir(STATIC_DIR):
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")