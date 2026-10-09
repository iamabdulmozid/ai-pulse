# AI Pulse — web/worker image (docs/tech/deployment.md)
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Tailwind standalone CLI (no Node pipeline).
RUN curl -fsSL -o /usr/local/bin/tailwindcss \
      https://github.com/tailwindlabs/tailwindcss/releases/latest/download/tailwindcss-linux-x64 \
    && chmod +x /usr/local/bin/tailwindcss

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Build Tailwind CSS, then collect static (manifest storage in prod).
RUN tailwindcss -i static/src/app.css -o static/dist/app.css --minify || true
ENV MANIFEST_STATIC=1
RUN python manage.py collectstatic --noinput || true

EXPOSE 8000
CMD ["uvicorn", "karbar_pulse.asgi:application", "--host", "0.0.0.0", "--port", "8000"]
