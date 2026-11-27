# TaxMantri backend — build from the repository root:
#   docker build -f backend/Dockerfile -t taxmantri-api .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# OCR system dependencies: Tesseract (scanned PDFs/images), Poppler (pdf2image),
# libmagic (MIME sniffing of uploads).
RUN apt-get update \
 && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng poppler-utils libmagic1 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt backend/requirements.lock backend/
RUN pip install -r backend/requirements.lock

COPY backend/ backend/
COPY knowledge_base/ knowledge_base/

RUN useradd --create-home --uid 10001 app && chown -R app /app
USER app

ENV PORT=8000
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s \
  CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/api/health', timeout=4)" || exit 1

# Migrations run inside the app's lifespan hook; one worker keeps RAM low on free tiers.
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT} --workers 1"]
