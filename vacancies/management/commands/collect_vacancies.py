from argparse import ArgumentParser
from typing import Any, override

from django.conf import settings

from core.http import HttpClient
from vacancies.management.base import SourceCommand
from vacancies.services import collect_from_source


class Command(SourceCommand):
    help = "Collect vacancies from job board feeds and store them in the database."

    @override
    def add_arguments(self, parser: ArgumentParser) -> None:
        super().add_arguments(parser)
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
        sources = self.resolve_sources(options["sources"])
        categories: list[str] = options["categories"] or settings.VACANCY_CATEGORIES
        with HttpClient.from_settings() as http:
            self.run_for_sources(
                sources, lambda source: collect_from_source(source, categories, http=http)
            )
