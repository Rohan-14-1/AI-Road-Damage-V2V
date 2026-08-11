# ─────────────────────────────────────────────────────────────────
#  AI Road Damage Detection — Docker image
#  Serves both the FastAPI backend and the static frontend.
#
#  Build:  docker build -t roadai .
#  Run:    docker run -p 8000:8000 roadai
#  Open:   http://localhost:8000
# ─────────────────────────────────────────────────────────────────

FROM python:3.11-slim

# System deps for OpenCV headless
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Working directory mirrors the repo structure:
#   /app/backend/   ← backend code (uvicorn runs here)
#   /app/frontend/  ← static HTML/CSS/JS
WORKDIR /app

# Install Python dependencies first (cached layer)
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy backend
COPY backend/ backend/

# Copy frontend
COPY frontend/ frontend/

# Create storage directories
RUN mkdir -p backend/storage/uploads backend/storage/processed

# Expose port (overridable via $PORT env var)
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT:-8000}/health')" || exit 1

# Run uvicorn from the backend directory
# main.py expects frontend at parents[2] / "frontend" = /app/frontend ✓
WORKDIR /app/backend
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
