# JobPulse

JobPulse collects vacancies from Ukrainian IT job boards, normalizes them and stores them in PostgreSQL for search and market analytics.

## Features

- Collects vacancies from the public RSS feeds of **DOU** and **Djinni**
- Extracts the company, locations, salary range and remote option from DOU vacancy titles
- Converts vacancy HTML into clean text while keeping paragraphs and list items
- Detects 65 technologies from a skill dictionary with aliases and case-sensitive rules, for example `Postgres` → PostgreSQL, `ASP.NET` → .NET, but never `go` → Go
- Deduplicates vacancies per source and merges categories when a vacancy appears in several feeds
- Records every collection run with its status, counts, duration and error
- Provides a Django admin to browse vacancies, companies, skills and run history

## Tech stack

Python 3.13 · Django 6.1 · PostgreSQL 18 · Requests · BeautifulSoup + lxml · Docker · uv · pytest · ruff · mypy (strict) · GitHub Actions

## Architecture

```
 RSS feeds ─► HttpClient ─► Collectors ─► VacancyIngestor ─► PostgreSQL ─► Django admin
              retries,      DouCollector   companies,
              throttling,   DjinniCollector skills, dedup,
              User-Agent    BeautifulSoup   ScrapeRun log
```

```
config/        Django settings and URLs
core/          HTTP client shared by all integrations
vacancies/
  collectors/  RSS and HTML parsing, one collector per job board
  services.py  Ingestion and collection orchestration
  skills.py    Skill detection
  models.py    Source, Company, Skill, Vacancy, ScrapeRun
tests/         pytest suite with recorded feed fixtures
```

Main design decisions:

- **One collector per source.** A collector turns a feed into `VacancyData` objects and knows nothing about the database. You add a new job board by writing a collector class and registering it.
- **Atomic ingestion.** A batch of vacancies is saved in a single transaction, so a failed run never leaves partial data.
- **PostgreSQL features where they help.** Categories and locations are stored in `ArrayField`, a GIN index serves category filters, and a unique constraint on `(source, external_id)` prevents duplicates.

## Data sources

JobPulse uses only data that job boards publish for automated consumption.

| Source | Access | Status |
|---|---|---|
| DOU | RSS `jobs.dou.ua/vacancies/feeds/` | Used |
| Djinni | RSS `djinni.co/jobs/rss/` | Used |
| Upwork, Indeed, Fiverr, LinkedIn | Terms of service or robots.txt forbid scraping | Not used |

Every request carries an identifiable `User-Agent`. Requests to the same host are throttled, and temporary errors (429, 5xx) are retried with exponential backoff that respects `Retry-After`. JobPulse never collects candidates' personal data.

## Getting started

### Docker

```bash
cp .env.example .env
docker compose up -d --build --wait
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py collect_vacancies
```

Open http://localhost:8000/admin/.

### Local development

Requires [uv](https://docs.astral.sh/uv/) and Docker for PostgreSQL.

```bash
make install
make env
make db
make migrate
make collect
make run
```

## Collecting vacancies

```bash
python manage.py collect_vacancies
python manage.py collect_vacancies --source dou
python manage.py collect_vacancies --source djinni --category Python --category Java
```

The command exits with a non-zero code if any source fails, so it can run under cron or a task scheduler.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `DJANGO_SECRET_KEY` | — | Django secret key |
| `DJANGO_DEBUG` | `false` | Debug mode |
| `DJANGO_ALLOWED_HOSTS` | empty | Comma-separated host names |
| `DATABASE_URL` | — | PostgreSQL connection URL |
| `VACANCY_CATEGORIES` | `Python` | Default categories to collect |
| `SCRAPER_USER_AGENT` | `JobPulse/0.1` | User-Agent sent to job boards, should include a contact |
| `SCRAPER_MIN_INTERVAL` | `1.0` | Minimum delay between requests to the same host, in seconds |
| `SCRAPER_MAX_RETRIES` | `3` | Retries for 429 and 5xx responses |
| `SCRAPER_CONNECT_TIMEOUT` / `SCRAPER_READ_TIMEOUT` | `5` / `30` | Request timeouts, in seconds |
| `POSTGRES_PORT` | `5433` | Host port of the Compose database |

## Quality

```bash
make check
```

Runs ruff, mypy in strict mode and the pytest suite with a 90% coverage gate. Current coverage is 100%. GitHub Actions runs the same checks against PostgreSQL, verifies that migrations are up to date and builds the Docker image.

## Roadmap

1. ~~Collection from DOU and Djinni, data model, admin~~
2. Salary normalization with NBU exchange rates, cross-source deduplication, scheduled collection with Celery
3. Market analytics: Djinni market snapshots, DOU salary surveys, trend tables and charts
4. REST API with Django REST Framework
5. Telegram bot with subscriptions and market reports
6. More sources: Greenhouse, Lever, Remotive, Freelancehunt, Work.ua
7. Candidate profiles and vacancy matching
8. End-to-end tests with Selenium
