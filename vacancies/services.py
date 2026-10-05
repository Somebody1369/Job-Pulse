import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from datetime import datetime

from django.db import transaction
from django.utils.text import slugify

from core.http import HttpClient
from vacancies.collectors.base import VacancyData
from vacancies.collectors.registry import get_collector_class
from vacancies.models import Company, ScrapeRun, Skill, Source, Vacancy
from vacancies.skills import SkillMatcher

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class IngestStats:
    fetched: int
    created: int
    updated: int


def merge_duplicates(items: Iterable[VacancyData]) -> dict[str, VacancyData]:
    merged: dict[str, VacancyData] = {}
    for item in items:
        known = merged.get(item.external_id)
        merged[item.external_id] = (
            item if known is None else replace(item, categories=known.categories | item.categories)
        )
    return merged


class VacancyIngestor:
    def __init__(self, source: Source, *, matcher: SkillMatcher, seen_at: datetime) -> None:
        self._source = source
        self._matcher = matcher
        self._seen_at = seen_at
        self._companies: dict[str, Company] = {}

    @transaction.atomic
    def ingest(self, items: Iterable[VacancyData]) -> IngestStats:
        batch = merge_duplicates(items)
        existing = {
            vacancy.external_id: vacancy
            for vacancy in Vacancy.objects.select_for_update().filter(
                source=self._source, external_id__in=batch.keys()
            )
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
            vacancy.save()
            vacancy.skills.set(self._matcher.match(f"{data.title}\n{data.description}"))
        return IngestStats(
            fetched=len(batch),
            created=len(batch) - len(existing),
            updated=len(existing),
        )

    def _apply(self, vacancy: Vacancy, data: VacancyData) -> None:
        vacancy.url = data.url
        vacancy.title = data.title
        vacancy.company = self._resolve_company(data.company)
        vacancy.categories = sorted({*vacancy.categories, *data.categories})
        vacancy.locations = list(data.locations)
        vacancy.is_remote = data.is_remote
        vacancy.salary_text = data.salary_text
        vacancy.description = data.description
        vacancy.description_html = data.description_html
        vacancy.published_at = data.published_at
        vacancy.last_seen_at = self._seen_at

    def _resolve_company(self, name: str) -> Company | None:
        slug = slugify(name, allow_unicode=True)
        if not slug:
            return None
        if slug not in self._companies:
            self._companies[slug], _ = Company.objects.get_or_create(
                slug=slug, defaults={"name": name}
            )
        return self._companies[slug]


def collect_from_source(
    source: Source,
    categories: Sequence[str],
    *,
    http: HttpClient,
) -> ScrapeRun:
    run = ScrapeRun.objects.create(source=source, categories=list(categories))
    try:
        collector = get_collector_class(source.code)(http)
        items = [item for category in categories for item in collector.collect(category)]
        ingestor = VacancyIngestor(
            source,
            matcher=SkillMatcher.from_skills(Skill.objects.all()),
            seen_at=run.started_at,
        )
        stats = ingestor.ingest(items)
    except Exception as exc:
        logger.exception("Collection from %s failed", source.code)
        run.mark_failed(exc)
    else:
        run.mark_succeeded(stats)
        logger.info(
            "Collected %d vacancies from %s: %d new, %d updated",
            stats.fetched,
            source.code,
            stats.created,
            stats.updated,
        )
    return run
