# ────────────────────────────────────────────────────────────────
# Piccadily Industrial Historian — Unified Web Dockerfile
# Multi-stage build: React/Vite Frontend + FastAPI Backend
# ────────────────────────────────────────────────────────────────

# --- Stage 1: Build React Frontend ---
FROM node:20-alpine AS frontend-builder

WORKDIR /build

# Install dependencies using lockfile
COPY frontend/package*.json ./
RUN npm ci

# Copy frontend source and build static files
COPY frontend/ ./
RUN npm run build

# --- Stage 2: Build Python Backend Dependencies ---
FROM python:3.11-slim AS backend-builder

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

# Install python requirements
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Stage 3: Runtime Environment ---
FROM python:3.11-slim

WORKDIR /app

# Copy installed Python packages from the builder stage
COPY --from=backend-builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=backend-builder /usr/local/bin /usr/local/bin

# Copy FastAPI application source code
COPY backend/app /app/app

# Copy compiled frontend static assets from Stage 1 into /app/static
COPY --from=frontend-builder /build/dist /app/static

EXPOSE 8000

# Perform healthcheck against local API health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/ping')" || exit 1

# Start FastAPI application using production Uvicorn options
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2", \
     "--loop", "uvloop", \
     "--http", "httptools", \
     "--log-level", "warning", \
     "--no-access-log"]
