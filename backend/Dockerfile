# Multi-stage build for the Django backend.
# Stage 1 builds wheels; stage 2 is a slim non-root runtime image.

FROM python:3.11-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update --yes --quiet \
    && apt-get install --yes --quiet --no-install-recommends \
        build-essential libpq-dev libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt


FROM python:3.11-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

# libpq5 is the runtime counterpart of libpq-dev needed by psycopg.
# GeoDjango additionally needs the GEOS, GDAL and PROJ shared libraries.
RUN apt-get update --yes --quiet \
    && apt-get install --yes --quiet --no-install-recommends \
        libpq5 binutils libproj-dev gdal-bin libgeos-c1v5 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash app

COPY --from=builder /wheels /wheels
COPY requirements.txt .
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

WORKDIR /app
COPY --chown=app:app . .

USER app

EXPOSE 8000

# WSGI default (templates-first). For ASGI/WebSockets swap to:
#   daphne -b 0.0.0.0 -p 8000 core.asgi:application
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", \
     "--access-logfile", "-", "core.wsgi:application"]
