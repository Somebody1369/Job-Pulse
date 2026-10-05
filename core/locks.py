import zlib
from collections.abc import Iterator
from contextlib import contextmanager

from django.db import connection


def lock_id(name: str) -> int:
    return zlib.crc32(name.encode())


@contextmanager
def advisory_lock(name: str) -> Iterator[bool]:
    key = lock_id(name)
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_lock(%s)", [key])
        acquired = bool(cursor.fetchone()[0])
    try:
        yield acquired
    finally:
        if acquired:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_unlock(%s)", [key])
