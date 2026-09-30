"""Transcripción de voz compatible con la API de OpenAI (/v1/audio/transcriptions).

Corre Whisper en CPU con faster-whisper. El modelo se carga en la primera petición y se libera
tras un rato sin uso, para no ocupar RAM en una VPS compartida con otros proyectos.
"""

import io
import logging
import os
import threading
import time

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import PlainTextResponse
from faster_whisper import WhisperModel

log = logging.getLogger("kcalia.stt")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

MODEL_NAME = os.getenv("WHISPER_MODEL", "small")
MODEL_DIR = os.getenv("WHISPER_MODEL_DIR", "/models")
COMPUTE = os.getenv("WHISPER_COMPUTE", "int8")
THREADS = int(os.getenv("WHISPER_THREADS", "3"))
IDLE_SECONDS = int(os.getenv("WHISPER_IDLE_SECONDS", "600"))
API_KEY = os.getenv("STT_API_KEY", "")
MAX_BYTES = 15 * 1024 * 1024

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

_model: WhisperModel | None = None
_last_used = 0.0
_lock = threading.Lock()  # una transcripción a la vez: es trabajo de CPU


def _load() -> WhisperModel:
    global _model, _last_used
    if _model is None:
        started = time.time()
        _model = WhisperModel(MODEL_NAME, device="cpu", compute_type=COMPUTE, cpu_threads=THREADS, download_root=MODEL_DIR, local_files_only=True)
        log.info("Modelo %s cargado en %.1f s", MODEL_NAME, time.time() - started)
    _last_used = time.time()
    return _model


def _janitor() -> None:
    global _model
    while True:
        time.sleep(30)
        with _lock:
            if _model is not None and time.time() - _last_used > IDLE_SECONDS:
                _model = None
                log.info("Modelo descargado tras %s s sin uso", IDLE_SECONDS)


threading.Thread(target=_janitor, daemon=True).start()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model": MODEL_NAME, "loaded": _model is not None}


@app.post("/v1/audio/transcriptions")
def transcriptions(
    request: Request,
    file: UploadFile = File(...),
    model: str = Form(default=""),  # se acepta por compatibilidad; el modelo lo fija WHISPER_MODEL
    language: str | None = Form(default=None),
    prompt: str | None = Form(default=None),
    response_format: str = Form(default="json"),
    temperature: float = Form(default=0.0),
):
    if API_KEY and request.headers.get("authorization") != f"Bearer {API_KEY}":
        raise HTTPException(401, "Clave no válida")
    data = file.file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "Audio demasiado grande")
    if not data:
        raise HTTPException(400, "Audio vacío")

    with _lock:
        whisper = _load()
        started = time.time()
        segments, info = whisper.transcribe(
            io.BytesIO(data),
            language=language or None,
            initial_prompt=prompt or None,
            temperature=temperature,
            beam_size=3,
            vad_filter=True,
            condition_on_previous_text=False,
        )
        text = " ".join(segment.text.strip() for segment in segments).strip()
        global _last_used
        _last_used = time.time()
    log.info("Transcrito %.1f s de audio en %.1f s (%s)", info.duration, time.time() - started, info.language)

    if response_format == "text":
        return PlainTextResponse(text)
    if response_format == "verbose_json":
        return {"text": text, "language": info.language, "duration": info.duration}
    return {"text": text}
