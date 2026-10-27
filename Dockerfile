# syntax=docker/dockerfile:1
#
# MedBook's production image: Render's `medbook-demo` service (render.yaml)
# builds it from this file since Paso 32 (#145). Multi-stage, non-root,
# Alpine. Its CMD, scripts/start-production.sh, migrates, seeds the demo
# doctors, generates slots and starts gunicorn.
#
# Build:
#   docker build -t medbook:latest .
#
# Run (env vars must be supplied at runtime — never baked into the image;
# the boot runs migrate against DATABASE_URL):
#   docker run --rm -p 8000:8000 \
#     -e SECRET_KEY="<your-secret-key>" \
#     -e ALLOWED_HOSTS=localhost,127.0.0.1 \
#     -e DATABASE_URL="postgres://<user>:<password>@<host>:5432/medbook" \
#     -e DJANGO_SETTINGS_MODULE=config.settings.production \
#     medbook:latest

# ---------------------------------------------------------------------------
# Stage 1: builder — Python deps, Tailwind CSS and collectstatic
# ---------------------------------------------------------------------------
FROM python:3.12-alpine AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Every dependency ships a musllinux wheel (psycopg2-binary bundles libpq),
# so no compiler toolchain is needed. libstdc++ is required by the standalone
# Tailwind CLI (a Bun binary) and only lives in this stage.
RUN apk add --no-cache libstdc++

# Install Python deps first so this layer is cached unless requirements change.
COPY requirements/ requirements/
RUN pip install --no-cache-dir --prefix=/install -r requirements/production.txt

# Tailwind standalone CLI, musl build. django-tailwind-cli would download the
# glibc build (it does not detect musl), so the binary is fetched here,
# checked against the release's sha256sums.txt and used via TAILWIND_CLI_PATH.
# Keep TAILWIND_VERSION in sync with TAILWIND_CLI_VERSION in
# config/settings/base.py.
ARG TAILWIND_VERSION=4.3.3
ARG TARGETARCH
RUN case "${TARGETARCH:-amd64}" in \
        amd64) arch=x64; sha256=a04d34ceacc8f52cbe8920ad846cdeb61d3d0021dba32db0d1f77c9d9fad7a6c ;; \
        arm64) arch=arm64; sha256=71ea4be79c9de9827545682df3e040053fb535d37c71ed2cfdedf9385a0868e0 ;; \
        *) echo "Unsupported architecture: ${TARGETARCH}" >&2; exit 1 ;; \
    esac \
    && wget -qO /usr/local/bin/tailwindcss \
        "https://github.com/tailwindlabs/tailwindcss/releases/download/v${TAILWIND_VERSION}/tailwindcss-linux-${arch}-musl" \
    && echo "${sha256}  /usr/local/bin/tailwindcss" | sha256sum -c - \
    && chmod +x /usr/local/bin/tailwindcss

# Copy the application code (see .dockerignore for exclusions).
COPY . .

ARG DJANGO_SETTINGS_MODULE=config.settings.production
ENV DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE} \
    TAILWIND_CLI_PATH=/usr/local/bin/tailwindcss \
    PYTHONPATH=/install/lib/python3.12/site-packages \
    PATH="/install/bin:${PATH}"

# Django needs a working settings import, including SECRET_KEY and
# ALLOWED_HOSTS. They are set only for this RUN (never as ENV), and the key
# is random and thrown away with the builder stage; the runtime container
# always gets its own SECRET_KEY from the environment.
# Tailwind first: the manifest storage used by collectstatic needs the CSS.
RUN SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(50))')" \
    && export SECRET_KEY \
        ALLOWED_HOSTS=localhost \
        DATABASE_URL=sqlite:////tmp/build.sqlite3 \
    && python manage.py tailwind build \
    && python manage.py collectstatic --noinput

# ---------------------------------------------------------------------------
# Stage 2: runtime — Alpine, non-root user, only what's needed to run
# ---------------------------------------------------------------------------
FROM python:3.12-alpine AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings.production

# No system packages: the wheels bundle their native libraries (libpq too).
RUN addgroup -g 1000 appuser \
    && adduser -D -u 1000 -G appuser -s /bin/sh appuser

WORKDIR /app

# Bring in only the installed packages from the builder (no Tailwind CLI,
# no pip cache, no requirements source files).
COPY --from=builder /install /usr/local
COPY --from=builder --chown=appuser:appuser /app/staticfiles /app/staticfiles
COPY --chown=appuser:appuser . .

USER appuser

EXPOSE 8000

# Binds $PORT when the platform sets it (Render: 10000), else 8000. Render
# uses this CMD because the service defines no dockerCommand.
CMD ["/bin/sh", "scripts/start-production.sh"]
