import logging
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Final

import requests
from django.conf import settings
from django.db import transaction

from core.http import HttpClient
from core.robots import RobotsPolicy, UrlPolicy
from market.services import UsdConverter
from vacancies.collectors.base import (
    DetailsCollector,
    DetailsParseError,
    VacancyData,
    VacancyDetails,
)
from vacancies.collectors.registry import UnknownSourceError, get_collector_class
from vacancies.dedup import company_key
from vacancies.models import Company, ScrapeRun, Skill, Source, Vacancy
from vacancies.salary import SalaryRange, format_salary_range
from vacancies.skills import SkillMatcher

GONE_STATUSES: Final = frozenset({404, 410})
REMATCH_CHUNK_SIZE: Final = 1000

logger = logging.getLogger(__name__)


class DetailsNotSupportedError(LookupError):
    pass


@dataclass(frozen=True, slots=True)
class IngestStats:
    fetched: int
    created: int
    updated: int
    failed: int = 0


def merge_duplicates(items: Iterable[VacancyData]) -> dict[str, VacancyData]:
    merged: dict[str, VacancyData] = {}
    for item in items:
        known = merged.get(item.external_id)
        merged[item.external_id] = (
            item if known is None else replace(item, categories=known.categories | item.categories)
        )
    return merged


def match_skills(
    matcher: SkillMatcher, *, title: str, description: str, company: Company | None
) -> set[int]:
    return matcher.match(f"{title}\n{description}", ignore=[company.name] if company else [])


def format_salary(salary: SalaryRange) -> str:
    if salary.minimum is None and salary.maximum is None:
        return ""
    return f"{format_salary_range(salary.minimum, salary.maximum)} {salary.currency}"


class CompanyResolver:
    def __init__(self) -> None:
        self._cache: dict[str, Company] = {}

    def resolve(self, name: str, website: str = "") -> Company | None:
        slug = company_key(name)
        if not slug:
            return None
        company = self._cache.get(slug)
        if company is None:
            company, _ = Company.objects.get_or_create(
                slug=slug, defaults={"name": name, "website": website}
            )
            self._cache[slug] = company
        if website and not company.website:
            company.website = website
            company.save(update_fields=("website",))
        return company


class VacancyWriter:
    def __init__(self, *, converter: UsdConverter) -> None:
        self._converter = converter
        self._companies = CompanyResolver()

    def apply_company(self, vacancy: Vacancy, name: str, website: str = "") -> None:
        if name:
            vacancy.company = self._companies.resolve(name, website)

    def apply_location(
        self, vacancy: Vacancy, locations: tuple[str, ...], is_remote: bool | None
    ) -> None:
        if locations:
            vacancy.locations = list(locations)
        if is_remote is not None:
            vacancy.is_remote = is_remote

    def apply_salary(self, vacancy: Vacancy, salary: SalaryRange | None, text: str = "") -> None:
        if salary is None:
            return
        vacancy.salary_text = text or format_salary(salary)
        vacancy.salary_min = salary.minimum
        vacancy.salary_max = salary.maximum
        vacancy.salary_currency = salary.currency
        vacancy.salary_min_usd = self._converter.convert(salary.minimum, salary.currency)
        vacancy.salary_max_usd = self._converter.convert(salary.maximum, salary.currency)


class VacancyIngestor:
    def __init__(
        self,
        source: Source,
        *,
        matcher: SkillMatcher,
        converter: UsdConverter,
        seen_at: datetime,
    ) -> None:
        self._source = source
        self._matcher = matcher
        self._writer = VacancyWriter(converter=converter)
        self._seen_at = seen_at

    @transaction.atomic
    def ingest(self, items: Iterable[VacancyData]) -> IngestStats:
        batch = merge_duplicates(items)
        existing = {
            vacancy.external_id: vacancy
            for vacancy in Vacancy.objects.select_for_update(of=("self",))
            .select_related("company")
            .filter(source=self._source, external_id__in=batch.keys())
        }
        for data in batch.values():
            vacancy = existing.get(data.external_id)
            if vacancy is None:
                vacancy = Vacancy(
                    source=self._source,
                    external_id=data.external_id,
                    first_seen_at=self._seen_at,
                )
            self._apply(vacancy, data)
            vacancy.refresh_fingerprint()
            vacancy.save()
            vacancy.skills.set(
                match_skills(
                    self._matcher,
                    title=vacancy.title,
                    description=vacancy.description,
                    company=vacancy.company,
                )
            )
        return IngestStats(
            fetched=len(batch),
            created=len(batch) - len(existing),
            updated=len(existing),
        )

    def _apply(self, vacancy: Vacancy, data: VacancyData) -> None:
        vacancy.url = data.url
        vacancy.title = data.title
        vacancy.categories = sorted({*vacancy.categories, *data.categories})
        vacancy.description = data.description
        vacancy.description_html = data.description_html
        vacancy.published_at = data.published_at
        vacancy.last_seen_at = self._seen_at
        self._writer.apply_company(vacancy, data.company)
        self._writer.apply_location(vacancy, data.locations, data.is_remote)
        self._writer.apply_salary(vacancy, data.salary, data.salary_text)


class VacancyEnricher:
    def __init__(
        self,
        collector: DetailsCollector,
        robots: UrlPolicy,
        *,
        matcher: SkillMatcher,
        converter: UsdConverter,
        fetched_at: datetime,
    ) -> None:
        self._collector = collector
        self._robots = robots
        self._matcher = matcher
        self._writer = VacancyWriter(converter=converter)
        self._fetched_at = fetched_at

    def enrich(self, vacancies: Iterable[Vacancy]) -> IngestStats:
        checked = enriched = 0
        for vacancy in vacancies:
            checked += 1
            if self._enrich_one(vacancy):
                enriched += 1
        return IngestStats(fetched=checked, created=0, updated=enriched, failed=checked - enriched)

    def _enrich_one(self, vacancy: Vacancy) -> bool:
        if not self._robots.is_allowed(vacancy.url):
            logger.info("robots.txt disallows %s", vacancy.url)
            self._mark_fetched(vacancy)
            return False
        try:
            details = self._collector.fetch_details(vacancy.url)
        except requests.HTTPError as exc:
            logger.warning("Failed to fetch %s: %s", vacancy.url, exc)
            if exc.response is not None and exc.response.status_code in GONE_STATUSES:
                self._mark_fetched(vacancy)
            return False
        except (requests.RequestException, DetailsParseError) as exc:
            logger.warning("Failed to fetch %s: %s", vacancy.url, exc)
            return False
        self._apply(vacancy, details)
        return True

    def _apply(self, vacancy: Vacancy, details: VacancyDetails) -> None:
        self._writer.apply_company(vacancy, details.company, details.company_website)
        self._writer.apply_location(vacancy, details.locations, details.is_remote)
        self._writer.apply_salary(vacancy, details.salary)
        if details.experience_months is not None:
            vacancy.experience_months = details.experience_months
        if details.english_level:
            vacancy.english_level = details.english_level
        vacancy.details_fetched_at = self._fetched_at
        vacancy.refresh_fingerprint()
        vacancy.save()
        vacancy.skills.set(
            match_skills(
                self._matcher,
                title=vacancy.title,
                description=vacancy.description,
                company=vacancy.company,
            )
        )

    def _mark_fetched(self, vacancy: Vacancy) -> None:
        vacancy.details_fetched_at = self._fetched_at
        vacancy.save(update_fields=("details_fetched_at",))


@transaction.atomic
def rematch_skills() -> int:
    matcher = SkillMatcher.from_skills(Skill.objects.all())
    link_model = Vacancy.skills.through
    vacancies = Vacancy.objects.select_related("company").only(
        "title", "description", "company__name"
    )
    links = [
        link_model(vacancy_id=vacancy.pk, skill_id=skill_id)
        for vacancy in vacancies.iterator(chunk_size=REMATCH_CHUNK_SIZE)
        for skill_id in match_skills(
            matcher, title=vacancy.title, description=vacancy.description, company=vacancy.company
        )
    ]
    link_model.objects.all().delete()
    link_model.objects.bulk_create(links, batch_size=REMATCH_CHUNK_SIZE)
    return len(links)


def active_sources(*, with_details: bool = False) -> list[Source]:
    return [
        source
        for source in Source.objects.filter(is_active=True)
        if not with_details or supports_details(source)
    ]


def supports_details(source: Source) -> bool:
    try:
        collector_class = get_collector_class(source.code)
    except UnknownSourceError:
        return False
    return issubclass(collector_class, DetailsCollector)


def collect_from_source(
    source: Source,
    categories: Sequence[str],
    *,
    http: HttpClient,
) -> ScrapeRun:
    run = ScrapeRun.objects.create(source=source, categories=list(categories))

    def collect() -> IngestStats:
        collector = get_collector_class(source.code)(http)
        items = collector.collect(categories)
        ingestor = VacancyIngestor(
            source,
            matcher=SkillMatcher.from_skills(Skill.objects.all()),
            converter=UsdConverter.from_latest_rates(),
            seen_at=run.started_at,
        )
        return ingestor.ingest(items)

    return _execute(run, collect)


def enrich_from_source(source: Source, *, http: HttpClient, limit: int) -> ScrapeRun:
    run = ScrapeRun.objects.create(source=source, kind=ScrapeRun.Kind.DETAILS)

    def enrich() -> IngestStats:
        collector = get_collector_class(source.code)(http)
        if not isinstance(collector, DetailsCollector):
            raise DetailsNotSupportedError(f"Source {source.code!r} has no details collector")
        pending = (
            source.vacancies.filter(details_fetched_at__isnull=True)
            .select_related("company")
            .order_by("-published_at")[:limit]
        )
        enricher = VacancyEnricher(
            collector,
            RobotsPolicy(http, settings.SCRAPER_USER_AGENT),
            matcher=SkillMatcher.from_skills(Skill.objects.all()),
            converter=UsdConverter.from_latest_rates(),
            fetched_at=run.started_at,
        )
        return enricher.enrich(pending)

    return _execute(run, enrich)


def _execute(run: ScrapeRun, operation: Callable[[], IngestStats]) -> ScrapeRun:
    try:
        stats = operation()
    except Exception as exc:
        logger.exception("%s run for %s failed", run.get_kind_display(), run.source.code)
        run.mark_failed(exc)
    else:
        run.mark_succeeded(stats)
        logger.info(
            "%s run for %s: %d vacancies, %d new, %d updated, %d failed",
            run.get_kind_display(),
            run.source.code,
            stats.fetched,
            stats.created,
            stats.updated,
            stats.failed,
        )
    return run
