FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN pip install --no-cache-dir fastapi==0.115.12 uvicorn==0.34.2 python-multipart==0.0.20 faster-whisper==1.1.1 "requests>=2.32,<3" "av==12.3.0" "piper-tts>=1.2,<2"
COPY app/voice/service.py /app/service.py
EXPOSE 8091
CMD ["uvicorn","service:app","--host","0.0.0.0","--port","8091"]
