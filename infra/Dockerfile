FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install --no-install-recommends -y libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ /app/backend/
WORKDIR /app/backend

# La imagen no corre como root (OWASP A05, Práctica N.° 5).
RUN useradd --create-home --shell /usr/sbin/nologin aplicacion \
    && chown -R aplicacion:aplicacion /app
USER aplicacion

EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
