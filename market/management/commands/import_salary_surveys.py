from argparse import ArgumentParser
from typing import Any, override

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.http import HttpClient
from market.services import import_salary_survey
from market.surveys import SurveyFormatError


class Command(BaseCommand):
    help = "Import raw DOU salary survey results published on GitHub."

    @override
    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "-s",
            "--survey",
            action="append",
            dest="surveys",
            metavar="NAME",
            help="Survey name such as 2026_june. Repeatable. Defaults to DOU_SALARY_SURVEYS.",
        )

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        names: list[str] = options["surveys"] or settings.DOU_SALARY_SURVEYS
        failed: list[str] = []
        with HttpClient.from_settings() as http:
            for name in names:
                try:
                    survey = import_salary_survey(http, name)
                except (requests.RequestException, SurveyFormatError) as exc:
                    self.stderr.write(self.style.ERROR(f"{name}: {exc}"))
                    failed.append(name)
                    continue
                self.stdout.write(f"{name}: {survey.response_count} responses")
        if failed:
            raise CommandError(f"Failed surveys: {', '.join(failed)}")
