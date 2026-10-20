FROM mcr.microsoft.com/playwright/python:v1.58.0-noble
WORKDIR /browser
RUN pip install --no-cache-dir fastapi==0.115.14 uvicorn==0.35.0 pydantic==2.11.7 playwright==1.58.0
COPY app/browser/service.py /browser/service.py
ENV PYTHONUNBUFFERED=1
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
CMD ["uvicorn", "service:app", "--host", "0.0.0.0", "--port", "8780"]
