FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /bin/uv

WORKDIR /app

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-dev

COPY . .

RUN DJANGO_SECRET_KEY=collectstatic \
    DATABASE_URL=postgres://collectstatic@localhost/collectstatic \
    python manage.py collectstatic --noinput \
    && useradd --system --uid 1000 --no-create-home app

USER app

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application"]
