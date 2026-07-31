# ---- Builder stage ----
    FROM python:3.12-slim AS builder

    COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
    
    WORKDIR /app
    
    ENV UV_COMPILE_BYTECODE=1 \
        UV_LINK_MODE=copy
    
    COPY pyproject.toml uv.lock ./
    RUN uv sync --frozen --no-install-project --no-dev
    
    COPY . .
    RUN uv sync --frozen --no-dev
    
    # ---- Runtime stage ----
    FROM python:3.12-slim
    
    WORKDIR /app
    
    RUN groupadd -r appuser && useradd -r -g appuser appuser
    
    COPY --from=builder --chown=appuser:appuser /app /app
    
    ENV PATH="/app/.venv/bin:$PATH"
    
    USER appuser
    
    EXPOSE 8000
    
    CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]