"""Isolated local speech-to-text service. No host port. Model cached in volume."""
import io
import os
import tempfile
import threading
from pathlib import Path
from fastapi import FastAPI, File, UploadFile, HTTPException
from faster_whisper import WhisperModel

app = FastAPI(title='JARVIS Whisper transcription')
model = None
lock = threading.RLock()

def load_model():
    global model
    if model is None:
        with lock:
            if model is None:
                model = WhisperModel(os.getenv('WHISPER_MODEL','base.en'),
                    device=os.getenv('WHISPER_DEVICE','cpu'),
                    compute_type=os.getenv('WHISPER_COMPUTE_TYPE','int8'),
                    download_root='/models')
    return model

@app.get('/health')
def health():
    return {'ready': True, 'model_loaded': model is not None}

@app.post('/transcribe')
async def transcribe(file: UploadFile = File(...)):
    raw = await file.read(8*1024*1024+1)
    if not raw or len(raw)>8*1024*1024:
        raise HTTPException(413,'Recording empty or too large')
    # PyAV decoder in faster-whisper accepts a binary file-like object for WebM/Opus.
    try:
        with lock:
            segments, info = load_model().transcribe(io.BytesIO(raw), beam_size=3,
                language='en', vad_filter=True, condition_on_previous_text=False)
            result = ' '.join(s.text.strip() for s in segments).strip()
        return {'text':result[:4000], 'language':info.language}
    except Exception as exc:
        import traceback
        traceback.print_exc()
        raise HTTPException(422,'Unable to transcribe recording; check audio format and voice logs') from exc


# Free local Piper text-to-speech. No outgoing TTS API calls.
import wave
from fastapi.responses import Response
from pydantic import BaseModel, Field
from piper.voice import PiperVoice
import re

PIPER_FOLDER=Path('/voices/piper')
PIPER_PATTERN=re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,90}$')
_piper_cache={}
class SpeakRequest(BaseModel):
    voice:str=Field(min_length=1,max_length=91)
    text:str=Field(min_length=1,max_length=1200)
    speed:float=Field(default=1,ge=.7,le=1.3)

@app.post('/speak')
def speak_piper(req:SpeakRequest):
    if not PIPER_PATTERN.fullmatch(req.voice) or '..' in req.voice:
        raise HTTPException(400,'Invalid voice name')
    model=PIPER_FOLDER/(req.voice+'.onnx')
    config=PIPER_FOLDER/(req.voice+'.onnx.json')
    if not model.is_file() or not config.is_file():raise HTTPException(404,'Model or configuration missing')
    try:
        with lock:
            key=(str(model),model.stat().st_mtime_ns,config.stat().st_mtime_ns)
            if key not in _piper_cache:
                _piper_cache.clear()
                _piper_cache[key]=PiperVoice.load(str(model),config_path=str(config))
            buff=io.BytesIO()
            with wave.open(buff,'wb') as wf:
                _piper_cache[key].synthesize_wav(req.text,wf)
            return Response(buff.getvalue(),media_type='audio/wav')
    except Exception as exc:
        import traceback
        traceback.print_exc()
        raise HTTPException(422,'Piper voice synthesis failed; see voice logs') from exc
