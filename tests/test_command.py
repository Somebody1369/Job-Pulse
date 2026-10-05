from io import StringIO

import pytest
import responses
from django.core.management import CommandError, call_command
from responses import matchers

from tests.utils import DJINNI_FEED_URL, DOU_FEED_URL, read_fixture
from vacancies.models import ScrapeRun, Source, Vacancy

pytestmark = pytest.mark.django_db


def mock_dou(mock: responses.RequestsMock, category: str = "Python") -> None:
    mock.get(
        DOU_FEED_URL,
        body=read_fixture("dou_python.xml"),
        match=[matchers.query_param_matcher({"category": category})],
    )


def mock_djinni(mock: responses.RequestsMock, *, status: int = 200) -> None:
    mock.get(
        DJINNI_FEED_URL,
        body=read_fixture("djinni_python.xml"),
        status=status,
        match=[matchers.query_param_matcher({"primary_keyword": "Python"})],
    )


def test_collects_from_all_active_sources(mocked_responses: responses.RequestsMock) -> None:
    mock_dou(mocked_responses)
    mock_djinni(mocked_responses)
    output = StringIO()

    call_command("collect_vacancies", stdout=output)

    assert "dou: 5 vacancies, 5 new, 0 updated" in output.getvalue()
    assert "djinni: 3 vacancies, 3 new, 0 updated" in output.getvalue()
    assert Vacancy.objects.count() == 8
    assert ScrapeRun.objects.filter(status=ScrapeRun.Status.SUCCEEDED).count() == 4


def test_second_run_updates_instead_of_duplicating(
    mocked_responses: responses.RequestsMock,
) -> None:
    mock_dou(mocked_responses)
    output = StringIO()

    call_command("collect_vacancies", "--source", "dou", stdout=output)
    call_command("collect_vacancies", "--source", "dou", stdout=output)

    assert "dou: 5 vacancies, 0 new, 5 updated" in output.getvalue()
    assert Vacancy.objects.count() == 5


def test_collects_requested_categories(mocked_responses: responses.RequestsMock) -> None:
    mock_dou(mocked_responses, "Python")
    mock_dou(mocked_responses, "Java")

    call_command("collect_vacancies", "-s", "dou", "-c", "Python", "-c", "Java", stdout=StringIO())

    run = ScrapeRun.objects.get()
    assert run.categories == ["Python", "Java"]
    assert run.fetched_count == 5
    assert Vacancy.objects.filter(categories__contains=["Python", "Java"]).count() == 5


def test_skips_inactive_sources(mocked_responses: responses.RequestsMock) -> None:
    Source.objects.filter(code="djinni").update(is_active=False)
    mock_dou(mocked_responses)

    call_command("collect_vacancies", stdout=StringIO())

    collected = set(ScrapeRun.objects.values_list("source__code", flat=True))
    assert "dou" in collected
    assert "djinni" not in collected


def test_rejects_unknown_sources() -> None:
    with pytest.raises(CommandError, match="Unknown sources: nope"):
        call_command("collect_vacancies", "--source", "dou", "--source", "nope")


def test_reports_failed_sources_and_keeps_collecting(
    mocked_responses: responses.RequestsMock,
) -> None:
    mock_dou(mocked_responses)
    mock_djinni(mocked_responses, status=500)
    errors = StringIO()

    with pytest.raises(CommandError, match="Processing failed for: djinni"):
        call_command("collect_vacancies", stdout=StringIO(), stderr=errors)

    assert "djinni: HTTPError: 500" in errors.getvalue()
    assert Vacancy.objects.filter(source__code="dou").count() == 5
