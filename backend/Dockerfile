FROM python:3.12-slim

WORKDIR /app

# Install system deps for cryptography + sentence-transformers
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Run migrations then start the server.
# --reload is intentionally omitted, dev only.
# Workers default to 2; override via UVICORN_WORKERS env var.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${UVICORN_WORKERS:-2}"]
