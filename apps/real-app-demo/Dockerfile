FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir .
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin mirage
USER mirage
EXPOSE 8001
CMD ["sh", "-c", "exec uvicorn app.main:app --host :: --port ${PORT:-8001}"]
