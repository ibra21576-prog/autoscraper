FROM python:3.11-slim

WORKDIR /app

# Nur die Basis-Dependencies (ohne Playwright - zu groß für Free Tier)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p instance

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--timeout", "120", "app:app"]
