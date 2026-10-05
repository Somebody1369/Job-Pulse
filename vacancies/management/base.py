from argparse import ArgumentParser
from collections.abc import Callable
from typing import ClassVar, override

from django.core.management.base import BaseCommand, CommandError

from vacancies.models import ScrapeRun, Source
from vacancies.services import active_sources, supports_details


class SourceCommand(BaseCommand):
    requires_details: ClassVar[bool] = False

    @override
    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "-s",
            "--source",
            action="append",
            dest="sources",
            metavar="CODE",
            help="Source code to process. Repeatable. Defaults to all applicable active sources.",
        )

    def resolve_sources(self, codes: list[str] | None) -> list[Source]:
        if not codes:
            return active_sources(with_details=self.requires_details)
        sources = list(Source.objects.filter(code__in=codes))
        if missing := set(codes) - {source.code for source in sources}:
            raise CommandError(f"Unknown sources: {', '.join(sorted(missing))}")
        if rejected := [source.code for source in sources if not self._accepts(source)]:
            raise CommandError(f"Not supported for: {', '.join(sorted(rejected))}")
        return sources

    def run_for_sources(
        self, sources: list[Source], operation: Callable[[Source], ScrapeRun]
    ) -> None:
        failed: list[str] = []
        for source in sources:
            run = operation(source)
            self._report(run)
            if run.status == ScrapeRun.Status.FAILED:
                failed.append(source.code)
        if failed:
            raise CommandError(f"Processing failed for: {', '.join(failed)}")

    def _accepts(self, source: Source) -> bool:
        return not self.requires_details or supports_details(source)

    def _report(self, run: ScrapeRun) -> None:
        if run.status == ScrapeRun.Status.FAILED:
            self.stderr.write(self.style.ERROR(f"{run.source.code}: {run.error}"))
            return
        seconds = run.duration.total_seconds() if run.duration else 0.0
        failures = f", {run.failed_count} failed" if run.failed_count else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{run.source.code}: {run.fetched_count} vacancies, {run.created_count} new, "
                f"{run.updated_count} updated{failures} in {seconds:.1f}s"
            )
        )
