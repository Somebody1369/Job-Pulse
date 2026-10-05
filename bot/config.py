import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Self

DEFAULT_API_URL: Final = "http://localhost:8000/api/v1/"
DEFAULT_API_USERNAME: Final = "telegram-bot"


class ConfigError(ValueError):
    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class BotConfig:
    telegram_token: str
    api_url: str = DEFAULT_API_URL
    api_username: str = DEFAULT_API_USERNAME
    api_password: str
    redis_url: str = ""
    notify_interval: float = 300.0
    notifications_per_subscription: int = 5
    weekly_report_weekday: int = 0
    weekly_report_hour: int = 10
    timezone: str = "Europe/Kyiv"

    @classmethod
    def from_env(cls, environ: Mapping[str, str] = os.environ) -> Self:
        missing = [
            name for name in ("TELEGRAM_BOT_TOKEN", "BOT_API_PASSWORD") if not environ.get(name)
        ]
        if missing:
            raise ConfigError(f"Missing environment variables: {', '.join(missing)}")
        return cls(
            telegram_token=environ["TELEGRAM_BOT_TOKEN"],
            api_url=environ.get("JOBPULSE_API_URL", DEFAULT_API_URL),
            api_username=environ.get("BOT_API_USERNAME", DEFAULT_API_USERNAME),
            api_password=environ["BOT_API_PASSWORD"],
            redis_url=environ.get("BOT_REDIS_URL", ""),
            notify_interval=float(environ.get("BOT_NOTIFY_INTERVAL", "300")),
        )
