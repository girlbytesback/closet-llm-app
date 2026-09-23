# ---------- stage 1: build the React app ----------
FROM node:20-slim AS ui
WORKDIR /ui
COPY src/ui/package*.json ./
RUN npm ci
COPY src/ui ./
ARG VITE_SUPABASE_URL
ARG VITE_SUPABASE_PUBLISHABLE_KEY
RUN npm run build

# ---------- stage 2: the Python app ----------
FROM python:3.12-slim
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev
COPY src ./src
COPY --from=ui /ui/dist ./src/ui/dist
CMD uv run uvicorn closetllm.api:app --host 0.0.0.0 --port ${PORT:-8000}