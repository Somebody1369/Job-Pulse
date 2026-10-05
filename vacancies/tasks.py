import logging

from celery import shared_task
from django.conf import settings

from core.http import HttpClient
from core.locks import advisory_lock
from vacancies.services import active_sources, collect_from_source, enrich_from_source

logger = logging.getLogger(__name__)


@shared_task
def collect_vacancies() -> dict[str, str]:
    with advisory_lock("vacancies.collect") as acquired:
        if not acquired:
            logger.info("Vacancy collection is already running")
            return {}
        with HttpClient.from_settings() as http:
            runs = [
                collect_from_source(source, settings.VACANCY_CATEGORIES, http=http)
                for source in active_sources()
            ]
    return {run.source.code: run.status for run in runs}


@shared_task
def enrich_vacancies() -> dict[str, str]:
    with advisory_lock("vacancies.enrich") as acquired:
        if not acquired:
            logger.info("Vacancy enrichment is already running")
            return {}
        with HttpClient.from_settings() as http:
            runs = [
                enrich_from_source(source, http=http, limit=settings.VACANCY_DETAILS_BATCH_SIZE)
                for source in active_sources(with_details=True)
            ]
    return {run.source.code: run.status for run in runs}
