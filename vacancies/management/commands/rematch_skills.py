from typing import Any, override

from django.core.management.base import BaseCommand

from vacancies.services import rematch_skills


class Command(BaseCommand):
    help = "Recalculate the skills of every vacancy after the skill dictionary changes."

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        links = rematch_skills()
        self.stdout.write(self.style.SUCCESS(f"Linked {links} vacancy skills"))
