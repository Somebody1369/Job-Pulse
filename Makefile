.PHONY: install env services up down migrate superuser collect enrich rates run worker beat bot bot-account test e2e lint format typecheck schema check

install:
	uv sync

env:
	test -f .env || cp .env.example .env

services:
	docker compose up -d --wait db redis

up:
	docker compose up -d --build --wait

down:
	docker compose down

migrate:
	uv run python manage.py migrate

superuser:
	uv run python manage.py createsuperuser

collect:
	uv run python manage.py collect_vacancies

enrich:
	uv run python manage.py enrich_vacancies

rates:
	uv run python manage.py update_exchange_rates

run:
	uv run python manage.py runserver

worker:
	uv run celery --app config worker --loglevel INFO

beat:
	uv run celery --app config beat --loglevel INFO

bot-account:
	uv run python manage.py create_bot_account

bot:
	uv run python -m bot

test:
	uv run pytest --cov

e2e:
	uv run pytest -m e2e

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff check --fix .
	uv run ruff format .

typecheck:
	uv run mypy .

schema:
	uv run python manage.py spectacular --validate --fail-on-warn --file /dev/null

check: lint typecheck schema test
