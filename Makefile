.PHONY: install env services up down migrate superuser collect enrich rates run worker beat test lint format typecheck check

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

test:
	uv run pytest --cov

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff check --fix .
	uv run ruff format .

typecheck:
	uv run mypy .

check: lint typecheck test
