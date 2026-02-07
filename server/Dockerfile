FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir \
        "fastapi[standard]>=0.128.0" \
        "google-genai>=1.0.0" \
        "pydantic>=2.12.5" \
        "python-dotenv>=1.2.1" \
        "requests>=2.32.5" \
        "slowapi>=0.1.9" \
        "sqlalchemy>=2.0.45"

COPY . .

EXPOSE 8080

CMD uvicorn main:app --host 0.0.0.0 --port $PORT
