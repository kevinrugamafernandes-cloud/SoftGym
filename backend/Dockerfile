FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# .dockerignore excluye .env: los secretos nunca quedan dentro de la imagen.
COPY . .

RUN adduser --disabled-password --gecos "" appuser && chown -R appuser /app
USER appuser

# Render inyecta $PORT (10000); en local, 8000. --proxy-headers: la IP real del cliente
# (para el límite de intentos de login) llega detrás del proxy de Render.
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
