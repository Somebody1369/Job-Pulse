from argparse import ArgumentParser
from datetime import date
from typing import Any, override

from django.core.management.base import BaseCommand

from core.http import HttpClient
from market.services import update_exchange_rates


class Command(BaseCommand):
    help = "Load official NBU exchange rates into the database."

    @override
    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--date",
            type=date.fromisoformat,
            metavar="YYYY-MM-DD",
            help="Load rates for this date instead of the latest published ones.",
        )

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        with HttpClient.from_settings() as http:
            count = update_exchange_rates(http, options["date"])
        self.stdout.write(self.style.SUCCESS(f"Stored {count} exchange rates"))
