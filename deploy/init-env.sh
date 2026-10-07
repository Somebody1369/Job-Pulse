#!/bin/sh
# Creates .env for production from .env.production.example with random secrets.
set -eu
cd "$(dirname "$0")/.."

if [ -e .env ]; then
    echo ".env already exists" >&2
    exit 1
fi

sed \
    -e "s/^DJANGO_SECRET_KEY=.*/DJANGO_SECRET_KEY=$(openssl rand -hex 32)/" \
    -e "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$(openssl rand -hex 24)/" \
    -e "s/^BOT_API_PASSWORD=.*/BOT_API_PASSWORD=$(openssl rand -hex 24)/" \
    .env.production.example > .env
chmod 600 .env
echo "Created .env, now set DOMAIN and SCRAPER_USER_AGENT in it"
