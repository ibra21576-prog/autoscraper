FROM python:3.11-slim

WORKDIR /app

# Python Dependencies zuerst (Cache-Layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright Chromium + alle System-Deps installieren
RUN playwright install --with-deps chromium

COPY . .

# Datenbank-Ordner erstellen
RUN mkdir -p instance

EXPOSE 5000

# 1 Worker damit Scheduler nicht doppelt läuft, preload damit alles einmal startet
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--timeout", "120", "--preload", "app:app"]
