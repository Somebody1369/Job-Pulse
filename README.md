# JobPulse

JobPulse collects vacancies from Ukrainian IT job boards, normalizes them and turns them, together with public market statistics and salary surveys, into a market analytics dashboard.

![Market overview](docs/dashboard-market.png)

## Features

- Collects vacancies from the public RSS feeds of **DOU** and **Djinni** and from the public job board APIs of **Greenhouse** and **Lever** used by Ajax Systems, Kyivstar, ELEKS, airSlate, PandaDoc and Flo Health
- Reads schema.org `JobPosting` data from Djinni job pages to add the company, locations, remote option, published salary, required experience and English level
- Parses salary ranges such as `$1200–2800`, `від 40 000 грн` or `up to 2500 EUR` and converts them to USD with official **NBU** exchange rates
- Detects 65 technologies from a skill dictionary with aliases, case-sensitive rules and stop phrases, for example `Postgres` → PostgreSQL and `ASP.NET` → .NET, but never `go` or `Go-to-market` → Go
- Recognizes the same company and the same vacancy across job boards, so `Precoro Inc.` on DOU and `Precoro` on Djinni are one employer
- Full-text search with stemming, phrases, `OR` and `-exclusions`, ranked by title and description matches
- Captures daily Djinni market statistics for 24 categories: active candidates, open vacancies, expected and offered salaries, applications per vacancy
- Imports five DOU salary surveys (2024–2026, 64k responses) and computes medians and quartiles in PostgreSQL
- Analytics dashboard with competition, trends, salaries by seniority and experience, salary dynamics and skill demand, each table exportable to CSV and Excel
- Versioned REST API with filters, full-text search, OpenAPI documentation and JWT-protected endpoints for subscriptions and notifications
- Telegram bot that sends new vacancies matching a subscription, answers market and salary questions and delivers a weekly report rendered with Selenium
- Records every collection and enrichment run with its status, counts, duration and error
- Provides a Django admin to browse vacancies, companies, skills, exchange rates and run history

## Tech stack

Python 3.13 · Django 6.1 · Django REST Framework · PostgreSQL 18 · Celery + Redis · aiogram 3 · httpx · Requests · BeautifulSoup + lxml · Selenium · Chart.js · openpyxl · Docker · Caddy · uv · pytest · ruff · mypy (strict) · GitHub Actions

## Architecture

```
                 ┌──────────────────── Celery beat ────────────────────┐
                 ▼                  ▼                 ▼                ▼
 RSS feeds ─► Collectors   Job pages ─► Enricher   NBU API   Djinni statistics
                 │                  │                 │                │
                 └─► VacancyIngestor┴─► PostgreSQL ◄──┴────────────────┘
                                         ▲      │
                     DOU salary surveys ─┘      ├─► Analytics dashboard, CSV, Excel
                                                ├─► REST API ◄─► Telegram bot
                                                └─► Django admin
```

```
config/        Django settings, URLs and the Celery app
core/          HTTP client, robots.txt policy, advisory locks, percentile aggregates
market/        Exchange rates, Djinni market snapshots, DOU salary surveys
analytics/     Dashboard queries, page, charts and exports
api/           REST API: serializers, filters, permissions, OpenAPI schema
bot/           Telegram bot: API client, handlers, notifications, weekly schedule
subscriptions/ Subscribers, subscriptions and delivered notifications
vacancies/
  collectors/  RSS, HTML and JSON-LD parsing, one collector per job board
  services.py  Ingestion, enrichment and run tracking
  salary.py    Salary parsing and formatting
  dedup.py     Company and vacancy fingerprints
  skills.py    Skill detection
  tasks.py     Scheduled Celery tasks
tests/         pytest suite with recorded feeds and job pages
```

Main design decisions:

- **One collector per source.** A collector turns a feed or a page into plain data objects and knows nothing about the database. You add a job board by writing a collector class and registering it.
- **Unknown is not empty.** A feed that does not provide a field never erases what a job page already filled in, while an explicit "no salary" from the source does clear it.
- **Atomic ingestion.** A batch of vacancies is saved in one transaction, so a failed run never leaves partial data.
- **The database does the heavy lifting.** The search vector is a generated column with a GIN index, categories and locations are arrays, constraints reject duplicates and inverted salary ranges, `DISTINCT ON` picks the latest rate, snapshot and posting, `PERCENTILE_CONT` computes salary quartiles, and advisory locks stop scheduled runs from overlapping.
- **One table definition, three outputs.** Each dashboard table is described once and rendered as HTML, CSV and Excel, so exports always match the page.

## REST API

Interactive documentation is available at http://localhost:8000/api/docs/ and the OpenAPI schema at `/api/schema/`.

| Endpoint | Access | Purpose |
|---|---|---|
| `GET /api/v1/vacancies/` | Public | Vacancies with `q`, `skills`, `source`, `company`, `category`, `remote`, `english_level`, `min_salary_usd`, `published_after` and `ordering` |
| `GET /api/v1/skills/`, `/skills/demand/` | Public | Skills with vacancy counts and their demand trend |
| `GET /api/v1/companies/` | Public | Companies with search |
| `GET /api/v1/market/overview/`, `/market/snapshots/` | Public | Latest Djinni statistics per category and their history |
| `GET /api/v1/salaries/`, `/salaries/dynamics/` | Public | DOU salary percentiles by seniority or experience, medians across surveys |
| `POST /api/v1/auth/token/` | Bot account | JWT access and refresh tokens |
| `/api/v1/subscribers/…` | Bot account | Subscribers and their subscriptions |
| `GET`/`POST /api/v1/notifications/` | Bot account | New matching vacancies and delivery acknowledgements |

```bash
curl "http://localhost:8000/api/v1/vacancies/?skills=python,django&remote=true&min_salary_usd=3000"
```

Public endpoints are rate limited. Bot endpoints require an account with the `access_bot_api` permission, created with `create_bot_account`.

## Telegram bot

The bot is a separate asyncio process built with aiogram 3. It never touches the database and works only through the REST API with its own JWT-authenticated account.

| Command | What it does |
|---|---|
| `/subscribe` | Step-by-step subscription: skills, remote only, minimum salary, required experience |
| `/subscriptions` | Pause, resume or delete subscriptions |
| `/search django remote` | Top vacancies from full-text search |
| `/market python` | Candidates, vacancies, competition and salary ranges on Djinni |
| `/salary python 3` | DOU salary percentiles, highlighting the matching experience |
| `/report`, `/weekly` | The dashboard as an image now or every Monday at 10:00 |
| `/forget` | Delete the user's subscriptions and data |

Every few minutes the bot asks the API for new vacancies matching active subscriptions, sends them and acknowledges the deliveries, so a vacancy posted on both DOU and Djinni arrives once. Users who block the bot are forgotten automatically.

To run it:

1. Create a bot with [@BotFather](https://t.me/BotFather) and put the token into `TELEGRAM_BOT_TOKEN` in `.env`.
2. Set `BOT_API_PASSWORD` in `.env` and create the API account with `make bot-account`.
3. Start it with `make bot` locally or `docker compose --profile bot up -d` in Docker.

## Data sources

JobPulse uses only data that sources publish for automated consumption.

| Source | Access | Status |
|---|---|---|
| DOU | RSS `jobs.dou.ua/vacancies/feeds/` | Used |
| Djinni | RSS `djinni.co/jobs/rss/` and `JobPosting` data on job pages | Used |
| Greenhouse | Public Job Board API `boards-api.greenhouse.io` | Used for configured company boards |
| Lever | Public Postings API `api.lever.co/v0/postings` | Used for configured company boards |
| Djinni | Public salary statistics page `djinni.co/salaries/` | Used |
| DOU | Raw salary survey files published in `github.com/devua/csv` | Used |
| National Bank of Ukraine | Official exchange rate API | Used |
| Upwork, Indeed, Fiverr, LinkedIn | Terms of service or robots.txt forbid scraping | Not used |
| Remotive | Terms forbid showing its listings to collect sign-ups, which is what bot subscriptions do | Not used |

Every request carries an identifiable `User-Agent`. Job pages are fetched only when robots.txt allows it. Requests to the same host are throttled, and temporary errors (429, 5xx) are retried with exponential backoff that respects `Retry-After`. Djinni's estimated salaries for similar vacancies are ignored: only salaries published by the employer are stored. JobPulse never collects candidates' personal data.

## Getting started

### Docker

```bash
make env
docker compose up -d --build --wait
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py update_exchange_rates
docker compose exec web python manage.py collect_vacancies
docker compose exec web python manage.py capture_market_snapshots
docker compose exec web python manage.py import_salary_surveys
```

Open http://localhost:8000/ for the dashboard and http://localhost:8000/admin/ for the data. The `worker` and `beat` services keep the data up to date from then on.

### Local development

Requires [uv](https://docs.astral.sh/uv/) and Docker for PostgreSQL and Redis.

```bash
make install
make env
make services
make migrate
make rates
make collect
make run
```

Run `make worker` and `make beat` in separate terminals to enable the schedule.

## Commands

| Command | Purpose |
|---|---|
| `collect_vacancies [-s SOURCE] [-c CATEGORY]` | Read job board feeds |
| `enrich_vacancies [-s SOURCE] [--limit N]` | Fetch job pages for vacancies that have not been enriched yet |
| `update_exchange_rates [--date YYYY-MM-DD]` | Load NBU exchange rates |
| `rematch_skills` | Recalculate vacancy skills after editing the skill dictionary |
| `capture_market_snapshots [-c CATEGORY]` | Save today's Djinni market statistics |
| `import_salary_surveys [-s NAME]` | Import DOU salary surveys such as `2026_june` |
| `render_dashboard_report` | Save a screenshot of the dashboard for the weekly report |
| `create_bot_account [--username NAME]` | Create the API account for the Telegram bot, the password is taken from `BOT_API_PASSWORD` or generated |

Collection commands exit with a non-zero code if any source fails, so they can also run under cron.

## Schedule

| Task | When (Europe/Kyiv) |
|---|---|
| Collect vacancies | Every hour at :05 |
| Enrich vacancies | Every hour at :20 and :50 |
| Update exchange rates | 09:00 and 17:00 |
| Capture market snapshots | 23:30 |
| Render the dashboard report | Monday 09:00 |
| Send the weekly report (bot) | Monday 10:00 |
| Deliver vacancy notifications (bot) | Every 5 minutes |

## Configuration

| Variable | Default | Description |
|---|---|---|
| `DJANGO_SECRET_KEY` | — | Django secret key |
| `DJANGO_DEBUG` | `false` | Debug mode |
| `DJANGO_ALLOWED_HOSTS` | empty | Comma-separated host names |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | empty | Comma-separated origins such as `https://jobpulse.example.com` |
| `DJANGO_SECURE_COOKIES` | `false` | Send session and CSRF cookies over HTTPS only |
| `DATABASE_URL` | — | PostgreSQL connection URL |
| `CELERY_BROKER_URL` | `redis://localhost:6379/0` | Redis URL for Celery |
| `VACANCY_CATEGORIES` | `Python` | Categories to collect |
| `VACANCY_DETAILS_BATCH_SIZE` | `50` | Job pages fetched per source and run |
| `GREENHOUSE_BOARDS` / `LEVER_BOARDS` | 2 / 4 companies | Company boards to collect, `token` or `token=Company name` |
| `ATS_LOCATION_KEYWORDS` | Ukrainian cities, Europe, worldwide | Keeps company board jobs relevant to the Ukrainian market |
| `MARKET_CATEGORIES` | 24 categories | Djinni category codes to snapshot, an empty code is the whole market |
| `DOU_SALARY_SURVEYS` | `2024_june` … `2026_june` | DOU surveys to import |
| `SCRAPER_USER_AGENT` | `JobPulse/0.1` | User-Agent sent to job boards, should include a contact |
| `SCRAPER_MIN_INTERVAL` | `1.0` | Minimum delay between requests to the same host, in seconds |
| `SCRAPER_MAX_RETRIES` | `3` | Retries for 429 and 5xx responses |
| `SCRAPER_CONNECT_TIMEOUT` / `SCRAPER_READ_TIMEOUT` | `5` / `30` | Request timeouts, in seconds |
| `TELEGRAM_BOT_TOKEN` | — | Token from @BotFather |
| `BOT_API_USERNAME` / `BOT_API_PASSWORD` | `telegram-bot` / — | API account of the bot |
| `JOBPULSE_API_URL` | `http://localhost:8000/api/v1/` | API base URL used by the bot |
| `BOT_NOTIFY_INTERVAL` | `300` | Seconds between notification checks |
| `REPORT_DASHBOARD_URL` | `http://localhost:8000/analytics/` | Page captured for the weekly report |
| `API_ANON_RATE` / `API_USER_RATE` | `120/minute` / `600/minute` | API rate limits |
| `GUNICORN_WORKERS` / `GUNICORN_THREADS` | `2` / `1` | Gunicorn processes and threads per process |
| `POSTGRES_PORT` / `REDIS_PORT` | `5433` / `6379` | Host ports of the Compose services |

The production stack also reads `DOMAIN`, `POSTGRES_PASSWORD` and `CELERY_CONCURRENCY` (`2` by default), see [Deployment](#deployment).

## Deployment

`docker-compose.prod.yml` runs JobPulse on a single Linux server with Docker. Caddy is the only service exposed to the internet: it obtains a Let's Encrypt certificate, redirects HTTP to HTTPS and proxies requests to gunicorn. PostgreSQL and Redis are reachable only inside the Compose network, beat runs inside the Celery worker, logs are rotated and every service restarts after a failure or a reboot.

### Server size

| Server memory | Settings in `.env` |
|---|---|
| 2 GB or more | Defaults |
| 1 GB, for example the Google Cloud e2-micro free tier | `GUNICORN_WORKERS=1`, `GUNICORN_THREADS=4`, `CELERY_CONCURRENCY=1` and a 2 GB swap file |

With the 1 GB settings the services use about 600 MB once warm and up to about 760 MB while Chromium renders the weekly report, not counting the bot and the operating system. To add swap:

```bash
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### First deployment

1. Create a server with a public IP address, allow incoming ports 80 and 443 and point a domain at the server. A free [DuckDNS](https://www.duckdns.org/) subdomain works.
2. Install Docker, then log in again so that the group change applies, and clone the repository:

   ```bash
   curl -fsSL https://get.docker.com | sudo sh && sudo usermod -aG docker "$USER"
   git clone https://github.com/Somebody1369/Job-Pulse.git jobpulse && cd jobpulse
   ```

3. Create `.env` with random secrets, then set `DOMAIN`, `SCRAPER_USER_AGENT` and, on a 1 GB server, the sizing settings. `.env` sets `COMPOSE_FILE=docker-compose.prod.yml`, so every `docker compose` command in this directory uses the production stack.

   ```bash
   deploy/init-env.sh
   nano .env
   ```

4. Check that the sources answer from the server, since some sites block data center addresses. Every line should start with `200`:

   ```bash
   for url in https://djinni.co/jobs/rss/ https://djinni.co/salaries/ https://jobs.dou.ua/vacancies/feeds/ "https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange?json"; do curl -s -o /dev/null -w "%{http_code} $url\n" "$url"; done
   ```

5. Start the stack and load the initial data:

   ```bash
   docker compose up -d --build --wait
   docker compose exec web python manage.py createsuperuser
   docker compose exec web python manage.py update_exchange_rates
   docker compose exec web python manage.py collect_vacancies
   docker compose exec web python manage.py capture_market_snapshots
   docker compose exec web python manage.py import_salary_surveys
   ```

6. To run the Telegram bot, put its token into `TELEGRAM_BOT_TOKEN`, set `COMPOSE_PROFILES=bot` in `.env` and run:

   ```bash
   docker compose exec web python manage.py create_bot_account
   docker compose up -d --wait
   ```

`manage.py check --deploy` reports only `security.W004` and `security.W008`: Caddy sends the HSTS header and redirects HTTP to HTTPS, while Django keeps serving plain HTTP inside the Compose network for the worker and the bot.

### Updates

Migrations run when the `web` service starts:

```bash
git pull
docker compose up -d --build --wait
docker image prune -f
```

### Backups

`deploy/backup.sh` saves a compressed database dump into `backups/` and keeps the 14 newest, or `BACKUP_KEEP`. Schedule it with `crontab -e`, for example every night at 03:30:

```
30 3 * * * $HOME/jobpulse/deploy/backup.sh >> $HOME/jobpulse-backup.log 2>&1
```

The dumps live on the same disk as the database, so copy them elsewhere from time to time. To restore one:

```bash
docker compose exec -T db sh -c 'pg_restore --clean --if-exists --no-owner --username "$POSTGRES_USER" --dbname "$POSTGRES_DB"' < backups/jobpulse-20260101-033000.dump
```

### Free demo on Render

`render.yaml` describes a free demo on Render: the dashboard, API and admin run on a free web service with a free PostgreSQL 18 database in Frankfurt. Render has no free workers and free services sleep after 15 minutes without traffic, so the Scheduled tasks workflow in GitHub Actions collects the data instead of Celery. It collects vacancies every 3 hours, exchange rates at 06:00 and 14:00 UTC, market snapshots at 20:30 UTC and renders the dashboard report on Mondays at 06:00 UTC. The Telegram bot is not part of the demo.

1. In Render choose **New → Blueprint**, connect the repository and deploy it.
2. In the repository settings on GitHub, under **Secrets and variables → Actions**, add the secret `DATABASE_URL` with the External Database URL of `jobpulse-db`, the variable `JOBPULSE_URL` with the URL of the web service, for example `https://jobpulse.onrender.com`, and optionally the variable `SCRAPER_USER_AGENT`.
3. Run the Scheduled tasks workflow manually with the `all` task to load the initial data.
4. Create an admin account from your computer:

   ```bash
   DATABASE_URL='<External Database URL>' uv run python manage.py createsuperuser
   ```

The first request after a pause takes about a minute, the free database expires 30 days after creation unless it is upgraded, and GitHub disables scheduled workflows after 60 days without commits to the repository.

## Quality

```bash
make check
```

Runs ruff, mypy in strict mode, strict OpenAPI schema validation and the pytest suite with a 90% coverage gate. Current coverage is 100%. The suite includes an end-to-end test that drives a headless Chrome through Selenium against a live server, which you can run alone with `make e2e`. GitHub Actions runs the same checks against PostgreSQL, verifies that migrations are up to date and builds the Docker image.

![Salaries by experience and seniority](docs/dashboard-salaries.png)

## Roadmap

1. ~~Collection from DOU and Djinni, data model, admin~~
2. ~~Salary normalization, job page enrichment, cross-source deduplication, full-text search, scheduling~~
3. ~~Market analytics: Djinni market snapshots, DOU salary surveys, dashboard, exports, Selenium end-to-end test~~
4. ~~REST API with Django REST Framework, JWT and OpenAPI documentation~~
5. ~~Telegram bot with subscriptions, notifications and weekly reports rendered with Selenium~~
6. ~~More sources: Greenhouse and Lever company boards~~
7. Candidate profiles and vacancy matching
8. More end-to-end coverage and a demo deployment
