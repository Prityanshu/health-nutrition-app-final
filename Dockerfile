# ---------------------------------------------------------------------------
# Stage 1: build the React frontend.
#
# A separate Node stage rather than installing Node into the final image -
# the built output is a handful of static files, and nothing about running
# them needs a JS toolchain sitting in the production container.
# ---------------------------------------------------------------------------
FROM node:18-alpine AS frontend-build

WORKDIR /frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ---------------------------------------------------------------------------
# Stage 2: the FastAPI backend, serving the build from stage 1.
#
# main.py mounts frontend/build at "/" if it exists (see main.py's
# FRONTEND_BUILD check) - copying it in here is what makes this one image
# serve both the site and the API from a single origin, same as
# scripts/serve-public.sh does for local Tailscale Funnel hosting.
# ---------------------------------------------------------------------------
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ app/
COPY scripts/ scripts/
COPY config/ config/
COPY main.py .
COPY --from=frontend-build /frontend/build ./frontend/build

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash app
RUN chown -R app:app /app
USER app

# Expose port (use PORT env var for cloud platforms)
EXPOSE 8000

# Host platforms like Render assign the listen port via $PORT at runtime
# and it varies per platform, so it has to be read at container start
# (shell form) rather than baked into the exec-form CMD. Falls back to
# 8000 so `docker run` with no PORT set still works locally.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]