from argparse import ArgumentParser
from typing import Any, override

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.http import HttpClient
from market.services import capture_market_snapshots


class Command(BaseCommand):
    help = "Capture today's Djinni market statistics for the tracked categories."

    @override
    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "-c",
            "--category",
            action="append",
            dest="categories",
            metavar="CODE",
            help="Djinni category code, e.g. python. Repeatable. Defaults to MARKET_CATEGORIES.",
        )

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        categories: list[str] = options["categories"] or settings.MARKET_CATEGORIES
        with HttpClient.from_settings() as http:
            result = capture_market_snapshots(http, categories)
        for snapshot in result.captured:
            self.stdout.write(
                f"{snapshot.category_label}: {snapshot.active_candidates} candidates, "
                f"{snapshot.vacancies_online} vacancies"
            )
        if result.failed:
            raise CommandError(f"Failed categories: {', '.join(map(repr, result.failed))}")
        self.stdout.write(self.style.SUCCESS(f"Captured {len(result.captured)} snapshots"))
