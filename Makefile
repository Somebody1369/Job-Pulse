.PHONY: install env db up down migrate superuser collect run test lint format typecheck check

install:
	uv sync

env:
	test -f .env || cp .env.example .env

db:
	docker compose up -d --wait db

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

run:
	uv run python manage.py runserver

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
