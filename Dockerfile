# syntax=docker/dockerfile:1

FROM node:22-slim AS frontend-builder
WORKDIR /frontend
RUN npm install -g pnpm@10.34.3
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm build

FROM python:3.14-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project --no-dev

COPY src/ ./src/
RUN uv sync --locked --no-dev

COPY --from=frontend-builder /frontend/dist ./frontend/dist

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["uvicorn", "f1llm.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
