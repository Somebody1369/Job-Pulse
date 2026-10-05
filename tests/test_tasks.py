from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

import psycopg
import pytest
import responses
from django.conf import settings
from django.db import connection
from responses import matchers

from config.celery import app as celery_app
from core.locks import advisory_lock, lock_id
from market.nbu import NBU_EXCHANGE_URL
from market.tasks import update_exchange_rates
from tests.utils import (
    DJINNI_FEED_URL,
    DOU_FEED_URL,
    make_ingestor,
    make_vacancy_data,
    read_fixture,
)
from vacancies.models import ScrapeRun, Source
from vacancies.tasks import collect_vacancies, enrich_vacancies

pytestmark = pytest.mark.django_db

JOB_URL = "https://djinni.co/jobs/1-python-developer/"


@contextmanager
def lock_held_elsewhere(name: str) -> Iterator[None]:
    with psycopg.connect(**connection.get_connection_params()) as other:
        other.execute("SELECT pg_advisory_lock(%s)", [lock_id(name)])
        yield


def test_collect_vacancies_task(mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.get(DOU_FEED_URL, body=read_fixture("dou_python.xml"))
    mocked_responses.get(DJINNI_FEED_URL, body=read_fixture("djinni_python.xml"))

    assert collect_vacancies() == {
        "dou": "succeeded",
        "djinni": "succeeded",
        "greenhouse": "succeeded",
        "lever": "succeeded",
    }
    assert ScrapeRun.objects.filter(kind=ScrapeRun.Kind.FEED).count() == 4


def test_enrich_vacancies_task(mocked_responses: responses.RequestsMock) -> None:
    make_ingestor(Source.objects.get(code="djinni")).ingest(
        [make_vacancy_data(url=JOB_URL, published_at=datetime(2026, 10, 1, tzinfo=UTC))]
    )
    mocked_responses.get("https://djinni.co/robots.txt", body="User-agent: *\nDisallow:\n")
    mocked_responses.get(JOB_URL, body=read_fixture("djinni_job_remote.html"))

    assert enrich_vacancies() == {"djinni": "succeeded"}


def test_update_exchange_rates_task(mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.get(
        NBU_EXCHANGE_URL,
        json=[{"cc": "USD", "rate": 41.5, "exchangedate": "05.10.2026"}],
        match=[matchers.query_param_matcher({"json": ""})],
    )

    assert update_exchange_rates() == 1


@pytest.mark.parametrize(
    ("lock_name", "task"),
    [("vacancies.collect", collect_vacancies), ("vacancies.enrich", enrich_vacancies)],
)
def test_tasks_skip_when_another_run_holds_the_lock(
    lock_name: str, task: Callable[[], dict[str, str]]
) -> None:
    with lock_held_elsewhere(lock_name):
        assert task() == {}

    assert not ScrapeRun.objects.exists()


def test_advisory_lock_is_released_after_use() -> None:
    with advisory_lock("tests.lock") as first:
        assert first
    with advisory_lock("tests.lock") as second:
        assert second


def test_beat_schedule_points_to_registered_tasks() -> None:
    celery_app.loader.import_default_modules()
    scheduled = {entry["task"] for entry in settings.CELERY_BEAT_SCHEDULE.values()}

    assert scheduled <= set(celery_app.tasks)
