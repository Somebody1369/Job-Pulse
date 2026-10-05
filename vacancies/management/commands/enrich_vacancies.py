from argparse import ArgumentParser, ArgumentTypeError
from typing import Any, ClassVar, override

from django.conf import settings

from core.http import HttpClient
from vacancies.management.base import SourceCommand
from vacancies.services import enrich_from_source


def positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise ArgumentTypeError("must be a positive integer")
    return number


class Command(SourceCommand):
    help = "Fetch vacancy pages to fill in company, location, salary and requirements."
    requires_details: ClassVar[bool] = True

    @override
    def add_arguments(self, parser: ArgumentParser) -> None:
        super().add_arguments(parser)
        parser.add_argument(
            "--limit",
            type=positive_int,
            default=settings.VACANCY_DETAILS_BATCH_SIZE,
            help="Maximum number of vacancy pages to fetch per source.",
        )

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        sources = self.resolve_sources(options["sources"])
        limit: int = options["limit"]
        with HttpClient.from_settings() as http:
            self.run_for_sources(
                sources, lambda source: enrich_from_source(source, http=http, limit=limit)
            )
