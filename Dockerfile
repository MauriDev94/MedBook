# syntax=docker/dockerfile:1
#
# Portable Dockerfile for MedBook — alternative to the Render-native deploy
# defined in render.yaml (buildCommand/startCommand + gunicorn). This image
# is NOT used by Render; it exists for portability (run anywhere Docker
# runs) and to demonstrate multi-stage, non-root, slim Docker practices.
#
# Build:
#   docker build -t medbook:latest .
#
# Run (env vars must be supplied at runtime — never baked into the image):
#   docker run --rm -p 8000:8000 \
#     -e SECRET_KEY=... \
#     -e ALLOWED_HOSTS=localhost,127.0.0.1 \
#     -e DATABASE_URL=postgres://user:pass@host:5432/medbook \
#     -e DJANGO_SETTINGS_MODULE=config.settings.production \
#     medbook:latest

# ---------------------------------------------------------------------------
# Stage 1: builder — install Python deps and run collectstatic
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System deps needed to build psycopg2-binary's transitive requirements and
# other compiled wheels. Kept isolated to the builder stage only.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first so this layer is cached unless requirements change.
COPY requirements/ requirements/
RUN pip install --no-cache-dir --prefix=/install -r requirements/production.txt

# Copy the application code (see .dockerignore for exclusions).
COPY . .

# collectstatic needs a working Django settings import, including a
# SECRET_KEY and ALLOWED_HOSTS — none of these are real secrets, they only
# exist for this build-time step. The runtime container always gets its own
# SECRET_KEY from the environment (see config/settings/base.py).
ARG DJANGO_SETTINGS_MODULE=config.settings.production
ENV DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE} \
    SECRET_KEY=build-only-not-a-secret \
    ALLOWED_HOSTS=localhost \
    DATABASE_URL=sqlite:////tmp/build.sqlite3

RUN PYTHONPATH=/install/lib/python3.12/site-packages \
    PATH="/install/bin:${PATH}" \
    python manage.py collectstatic --noinput

# ---------------------------------------------------------------------------
# Stage 2: runtime — slim image, non-root user, only what's needed to run
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings.production \
    PATH="/usr/local/bin:${PATH}"

# Runtime needs libpq (psycopg2-binary links against it) but not the
# compiler toolchain from the builder stage.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

WORKDIR /app

# Bring in only the installed packages from the builder (no build tools,
# no pip cache, no requirements source files).
COPY --from=builder /install /usr/local
COPY --from=builder --chown=appuser:appuser /app/staticfiles /app/staticfiles
COPY --chown=appuser:appuser . .

USER appuser

EXPOSE 8000

# $PORT mirrors render.yaml's startCommand so the same image works on Render
# or any platform that injects PORT; defaults to 8000 for plain `docker run`.
ENV PORT=8000
CMD ["sh", "-c", "gunicorn config.wsgi:application --bind 0.0.0.0:${PORT} --workers 2 --timeout 120"]
