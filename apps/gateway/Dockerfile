FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY pyproject.toml ./
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./
COPY scripts/manage_operators.py ./scripts/
RUN pip install --no-cache-dir ".[ml,postgres]"
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin mirage
USER mirage

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host :: --port ${PORT:-8000} --no-proxy-headers"]
