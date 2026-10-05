from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Board:
    token: str
    company: str = ""


def parse_boards(values: Iterable[str]) -> list[Board]:
    boards: list[Board] = []
    for value in values:
        token, _, company = value.partition("=")
        if token.strip():
            boards.append(Board(token=token.strip(), company=company.strip()))
    return boards


def mentions_location(locations: Iterable[str], keywords: Iterable[str]) -> bool:
    text = " ".join(locations).casefold()
    return any(keyword.casefold() in text for keyword in keywords)
