
# ---- React UI ----
FROM node:22-alpine AS ui
WORKDIR /ui
COPY src/ui/package*.json ./
RUN npm ci
COPY src/ui/ ./
RUN npm run build

# ---- Python runtime ----
FROM python:3.12-slim
WORKDIR /app
COPY . .
COPY --from=ui /ui/dist ./src/ui/dist
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev
EXPOSE 8000
CMD uv run uvicorn closetllm.api:app --host 0.0.0.0 --port ${PORT:-8000}