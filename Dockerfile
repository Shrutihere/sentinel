# --- Stage 1: build the React dashboard ---
FROM node:22-slim AS frontend
WORKDIR /app/dashboard
COPY dashboard/package.json dashboard/package-lock.json ./
RUN npm ci
COPY dashboard/ ./
RUN npm run build

# --- Stage 2: the Python API (also serves the built dashboard) ---
FROM python:3.12-slim AS backend
WORKDIR /app
RUN pip install --no-cache-dir uv

# Install dependencies + the package (needs pyproject, README, and src).
COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN uv pip install --system --no-cache .

# Runtime data + the compiled dashboard.
COPY policy.yaml ./
COPY eval/ ./eval/
COPY --from=frontend /app/dashboard/dist ./dashboard/dist

ENV SENTINEL_CORS_ORIGINS='["*"]' \
    SENTINEL_STATIC_DIR=dashboard/dist
EXPOSE 8000
CMD ["uvicorn", "sentinel.main:app", "--host", "0.0.0.0", "--port", "8000"]
