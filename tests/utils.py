from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from vacancies.collectors.base import VacancyData

FIXTURES_DIR: Final = Path(__file__).parent / "fixtures"
DOU_FEED_URL: Final = "https://jobs.dou.ua/vacancies/feeds/"
DJINNI_FEED_URL: Final = "https://djinni.co/jobs/rss/"


def read_fixture(name: str) -> bytes:
    return (FIXTURES_DIR / name).read_bytes()


def make_vacancy_data(**overrides: Any) -> VacancyData:
    defaults: dict[str, Any] = {
        "external_id": "1",
        "url": "https://example.com/jobs/1/",
        "title": "Python Developer",
        "published_at": datetime(2026, 10, 1, 9, 0, tzinfo=UTC),
        "company": "Acme",
        "categories": frozenset({"Python"}),
        "description": "Django and PostgreSQL experience.",
    }
    return VacancyData(**(defaults | overrides))


def rss_document(*items: str) -> str:
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        f'<rss version="2.0"><channel><title>Feed</title>{"".join(items)}</channel></rss>'
    )
