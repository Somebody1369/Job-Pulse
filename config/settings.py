from datetime import timedelta
from pathlib import Path

import django_stubs_ext
import environ
from celery.schedules import crontab

django_stubs_ext.monkeypatch()

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env.str("DJANGO_SECRET_KEY")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS: list[str] = env.list("DJANGO_ALLOWED_HOSTS", default=[])
CSRF_TRUSTED_ORIGINS: list[str] = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "rest_framework",
    "rest_framework_simplejwt",
    "django_filters",
    "drf_spectacular",
    "analytics",
    "api",
    "market",
    "subscriptions",
    "vacancies",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {"default": env.db("DATABASE_URL")}
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DATABASE_CONN_MAX_AGE", default=60)
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Europe/Kyiv"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "default"},
    },
    "root": {"handlers": ["console"], "level": env.str("LOG_LEVEL", default="INFO")},
}

SCRAPER_USER_AGENT: str = env.str("SCRAPER_USER_AGENT", default="JobPulse/0.1")
SCRAPER_CONNECT_TIMEOUT: float = env.float("SCRAPER_CONNECT_TIMEOUT", default=5.0)
SCRAPER_READ_TIMEOUT: float = env.float("SCRAPER_READ_TIMEOUT", default=30.0)
SCRAPER_MAX_RETRIES: int = env.int("SCRAPER_MAX_RETRIES", default=3)
SCRAPER_BACKOFF_FACTOR: float = env.float("SCRAPER_BACKOFF_FACTOR", default=1.0)
SCRAPER_MIN_INTERVAL: float = env.float("SCRAPER_MIN_INTERVAL", default=1.0)

VACANCY_CATEGORIES: list[str] = env.list("VACANCY_CATEGORIES", default=["Python"])
VACANCY_DETAILS_BATCH_SIZE: int = env.int("VACANCY_DETAILS_BATCH_SIZE", default=50)
GREENHOUSE_BOARDS: list[str] = env.list("GREENHOUSE_BOARDS", default=["pandadoc", "flohealth"])
LEVER_BOARDS: list[str] = env.list(
    "LEVER_BOARDS",
    default=["ajax=Ajax Systems", "kyivstar=Kyivstar", "eleks=ELEKS", "airslate=airSlate"],
)
ATS_LOCATION_KEYWORDS: list[str] = env.list(
    "ATS_LOCATION_KEYWORDS",
    default=[
        "ukraine",
        "україна",
        "kyiv",
        "київ",
        "lviv",
        "львів",
        "kharkiv",
        "dnipro",
        "odesa",
        "europe",
        "emea",
        "worldwide",
        "anywhere",
    ],
)
DOU_SALARY_SURVEYS: list[str] = env.list(
    "DOU_SALARY_SURVEYS",
    default=["2024_june", "2024_dec", "2025_june", "2025_dec", "2026_june"],
)
REPORT_DASHBOARD_URL: str = env.str(
    "REPORT_DASHBOARD_URL", default="http://localhost:8000/analytics/"
)
REPORT_CHROME_BINARY: str = env.str("REPORT_CHROME_BINARY", default="")
REPORT_CHROMEDRIVER: str = env.str("REPORT_CHROMEDRIVER", default="")
REPORT_CHROME_ARGUMENTS: list[str] = env.list("REPORT_CHROME_ARGUMENTS", default=[])
REPORT_HISTORY_SIZE: int = env.int("REPORT_HISTORY_SIZE", default=10)
MARKET_CATEGORIES: list[str] = env.list(
    "MARKET_CATEGORIES",
    default=[
        "",
        "python",
        "javascript",
        "react",
        "java",
        "dotnet",
        "node_js",
        "php",
        "golang",
        "cpp",
        "ios",
        "android",
        "flutter",
        "fullstack",
        "qa",
        "qa_automation",
        "dev_ops",
        "data_engineer",
        "data_science",
        "ml_ai",
        "data_analyst",
        "project_manager",
        "product_manager",
        "design",
    ],
)

CELERY_BROKER_URL: str = env.str("CELERY_BROKER_URL", default="redis://localhost:6379/0")
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_IGNORE_RESULT = True
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_TIME_LIMIT = 30 * 60
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BEAT_SCHEDULE = {
    "collect-vacancies": {
        "task": "vacancies.tasks.collect_vacancies",
        "schedule": crontab(minute="5"),
    },
    "enrich-vacancies": {
        "task": "vacancies.tasks.enrich_vacancies",
        "schedule": crontab(minute="20,50"),
    },
    "update-exchange-rates": {
        "task": "market.tasks.update_exchange_rates",
        "schedule": crontab(hour="9,17", minute="0"),
    },
    "capture-market-snapshots": {
        "task": "market.tasks.capture_market_snapshots",
        "schedule": crontab(hour="23", minute="30"),
    },
    "render-dashboard-report": {
        "task": "analytics.tasks.render_dashboard_report",
        "schedule": crontab(day_of_week="mon", hour="9", minute="0"),
    },
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_PAGINATION_CLASS": "api.pagination.StandardPagination",
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "anon": env.str("API_ANON_RATE", default="120/minute"),
        "user": env.str("API_USER_RATE", default="600/minute"),
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "JobPulse API",
    "DESCRIPTION": (
        "Vacancies from Ukrainian IT job boards, Djinni market statistics and DOU salary "
        "surveys. Subscriber endpoints are reserved for the Telegram bot account."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": r"/api/v1",
}
