FROM python:3.11-slim

WORKDIR /app

# Dependencias de sistema mínimas para psycopg2
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1

# Railway inyecta $PORT en runtime; con shell form el $PORT se expande.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
