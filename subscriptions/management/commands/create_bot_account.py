import os
import secrets
from argparse import ArgumentParser
from typing import Any, override

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.management.base import BaseCommand

BOT_ACCOUNT_ENV = "BOT_API_PASSWORD"


class Command(BaseCommand):
    help = "Create or update the API account the Telegram bot uses to manage subscriptions."

    @override
    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--username", default="telegram-bot")

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        password = os.environ.get(BOT_ACCOUNT_ENV) or secrets.token_urlsafe(24)
        user, created = get_user_model().objects.get_or_create(username=options["username"])
        user.set_password(password)
        user.save()
        user.user_permissions.add(
            Permission.objects.get(
                codename="access_bot_api", content_type__app_label="subscriptions"
            )
        )
        action = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{action} bot account {user.get_username()!r}"))
        if BOT_ACCOUNT_ENV not in os.environ:
            self.stdout.write(f"Generated password: {password}")
