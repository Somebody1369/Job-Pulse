import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, tzinfo
from typing import NoReturn

logger = logging.getLogger(__name__)

type Job = Callable[[], Awaitable[object]]


def next_weekly_run(now: datetime, *, weekday: int, hour: int) -> datetime:
    start_of_hour = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    candidate = start_of_hour + timedelta(days=(weekday - now.weekday()) % 7)
    return candidate if candidate > now else candidate + timedelta(weeks=1)


async def run_job(name: str, job: Job) -> None:
    try:
        await job()
    except Exception:
        logger.exception("Scheduled job %s failed", name)


async def run_every(name: str, interval: float, job: Job) -> NoReturn:
    while True:
        await run_job(name, job)
        await asyncio.sleep(interval)


async def run_weekly(name: str, *, weekday: int, hour: int, zone: tzinfo, job: Job) -> NoReturn:
    while True:
        now = datetime.now(zone)
        await asyncio.sleep(
            (next_weekly_run(now, weekday=weekday, hour=hour) - now).total_seconds()
        )
        await run_job(name, job)
