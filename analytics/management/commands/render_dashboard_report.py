from typing import Any, override

from django.core.management.base import BaseCommand

from analytics.reports import render_dashboard_report


class Command(BaseCommand):
    help = "Take a screenshot of the analytics dashboard for the weekly Telegram report."

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        report = render_dashboard_report()
        size = len(bytes(report.image)) // 1024
        self.stdout.write(self.style.SUCCESS(f"Saved {report} ({size} KB)"))
