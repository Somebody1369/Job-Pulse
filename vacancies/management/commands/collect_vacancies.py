from argparse import ArgumentParser
from typing import Any, override

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.http import HttpClient
from vacancies.models import ScrapeRun, Source
from vacancies.services import collect_from_source


class Command(BaseCommand):
    help = "Collect vacancies from job boards and store them in the database."

    @override
    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "-s",
            "--source",
            action="append",
            dest="sources",
            metavar="CODE",
            help="Source code to collect from. Repeatable. Defaults to all active sources.",
        )
        parser.add_argument(
            "-c",
            "--category",
            action="append",
            dest="categories",
            metavar="NAME",
            help="Vacancy category, e.g. Python. Repeatable. Defaults to VACANCY_CATEGORIES.",
        )

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        sources = self._resolve_sources(options["sources"])
        categories: list[str] = options["categories"] or settings.VACANCY_CATEGORIES
        failed: list[str] = []
        with HttpClient.from_settings() as http:
            for source in sources:
                run = collect_from_source(source, categories, http=http)
                self._report(run)
                if run.status == ScrapeRun.Status.FAILED:
                    failed.append(source.code)
        if failed:
            raise CommandError(f"Collection failed for: {', '.join(failed)}")

    def _resolve_sources(self, codes: list[str] | None) -> list[Source]:
        if not codes:
            return list(Source.objects.filter(is_active=True))
        sources = list(Source.objects.filter(code__in=codes))
        if missing := set(codes) - {source.code for source in sources}:
            raise CommandError(f"Unknown sources: {', '.join(sorted(missing))}")
        return sources

    def _report(self, run: ScrapeRun) -> None:
        if run.status == ScrapeRun.Status.FAILED:
            self.stderr.write(self.style.ERROR(f"{run.source.code}: {run.error}"))
            return
        seconds = run.duration.total_seconds() if run.duration else 0.0
        self.stdout.write(
            self.style.SUCCESS(
                f"{run.source.code}: {run.fetched_count} vacancies, "
                f"{run.created_count} new, {run.updated_count} updated in {seconds:.1f}s"
            )
        )
