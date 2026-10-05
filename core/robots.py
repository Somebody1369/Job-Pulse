from typing import Final, Protocol
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import requests

from core.http import HttpClient

DISALLOW_ALL: Final = ("User-agent: *", "Disallow: /")
CLIENT_ERRORS: Final = range(400, 500)


class UrlPolicy(Protocol):
    def is_allowed(self, url: str) -> bool: ...


class RobotsPolicy:
    def __init__(self, http: HttpClient, user_agent: str) -> None:
        self._http = http
        self._user_agent = user_agent
        self._parsers: dict[str, RobotFileParser] = {}

    def is_allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._parsers:
            self._parsers[origin] = self._load(origin)
        return self._parsers[origin].can_fetch(self._user_agent, url)

    def _load(self, origin: str) -> RobotFileParser:
        parser = RobotFileParser(f"{origin}/robots.txt")
        try:
            response = self._http.get(f"{origin}/robots.txt")
        except requests.HTTPError as exc:
            client_error = exc.response is not None and exc.response.status_code in CLIENT_ERRORS
            parser.parse(() if client_error else DISALLOW_ALL)
        except requests.RequestException:
            parser.parse(DISALLOW_ALL)
        else:
            parser.parse(response.text.splitlines())
        return parser
