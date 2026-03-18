# ── Stage 1: build deps ─────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install CPU-only torch FIRST (avoids pulling 800MB CUDA build)
RUN pip install --upgrade pip \
    && pip install --prefix=/install --no-cache-dir \
        torch==2.2.2 --index-url https://download.pytorch.org/whl/cpu

# Install everything else
RUN pip install --prefix=/install --no-cache-dir -r requirements.txt

# Pre-download the embedding model so cold starts are instant
RUN PYTHONPATH=/install/lib/python3.12/site-packages \
    python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"


# ── Stage 2: runtime image ───────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/install/bin:$PATH" \
    PYTHONPATH="/install/lib/python3.12/site-packages" \
    # Model already baked in — skip re-download
    SENTENCE_TRANSFORMERS_HOME="/install/lib/python3.12/site-packages/sentence_transformers/models_cache"

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /install
# Copy cached model
COPY --from=builder /root/.cache /root/.cache

WORKDIR /app
COPY . .

RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser \
    && chown -R appuser:appgroup /app
USER appuser

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && gunicorn app.main:app \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers ${GUNICORN_WORKERS:-2} \
    --bind 0.0.0.0:8000 \
    --timeout 120 \
    --keep-alive 5 \
    --access-logfile - \
    --error-logfile -"]
