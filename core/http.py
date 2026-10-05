import time
from collections.abc import Mapping
from types import TracebackType
from typing import Final, Self
from urllib.parse import urlsplit

import requests
from django.conf import settings
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

RETRY_STATUSES: Final = frozenset({429, 500, 502, 503, 504})
RETRY_METHODS: Final = frozenset({"GET", "HEAD"})


class HttpClient:
    def __init__(
        self,
        *,
        user_agent: str,
        timeout: tuple[float, float],
        max_retries: int,
        backoff_factor: float,
        min_interval: float,
    ) -> None:
        self._timeout = timeout
        self._min_interval = min_interval
        self._last_request_at: dict[str, float] = {}
        self._session = requests.Session()
        self._session.headers["User-Agent"] = user_agent
        adapter = HTTPAdapter(
            max_retries=Retry(
                total=max_retries,
                backoff_factor=backoff_factor,
                status_forcelist=RETRY_STATUSES,
                allowed_methods=RETRY_METHODS,
                respect_retry_after_header=True,
                raise_on_status=False,
            )
        )
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)

    @classmethod
    def from_settings(cls) -> Self:
        return cls(
            user_agent=settings.SCRAPER_USER_AGENT,
            timeout=(settings.SCRAPER_CONNECT_TIMEOUT, settings.SCRAPER_READ_TIMEOUT),
            max_retries=settings.SCRAPER_MAX_RETRIES,
            backoff_factor=settings.SCRAPER_BACKOFF_FACTOR,
            min_interval=settings.SCRAPER_MIN_INTERVAL,
        )

    def get(self, url: str, *, params: Mapping[str, str] | None = None) -> requests.Response:
        self._wait_for_slot(urlsplit(url).netloc)
        response = self._session.get(url, params=params, timeout=self._timeout)
        response.raise_for_status()
        return response

    def close(self) -> None:
        self._session.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def _wait_for_slot(self, host: str) -> None:
        last_request_at = self._last_request_at.get(host)
        if last_request_at is not None:
            delay = self._min_interval - (time.monotonic() - last_request_at)
            if delay > 0:
                time.sleep(delay)
        self._last_request_at[host] = time.monotonic()
