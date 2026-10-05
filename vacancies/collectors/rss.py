from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

from bs4 import BeautifulSoup, Tag


class FeedFormatError(ValueError):
    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class FeedItem:
    title: str
    link: str
    description_html: str
    published_at: datetime
    categories: tuple[str, ...]


def parse_feed(document: bytes | str) -> list[FeedItem]:
    soup = BeautifulSoup(document, "xml")
    channel = soup.find("channel")
    if not isinstance(channel, Tag):
        raise FeedFormatError("RSS document has no <channel> element")
    return [_parse_item(node) for node in channel.find_all("item", recursive=False)]


def _parse_item(node: Tag) -> FeedItem:
    return FeedItem(
        title=_required_text(node, "title"),
        link=_required_text(node, "link"),
        description_html=_optional_text(node, "description"),
        published_at=_parse_date(_required_text(node, "pubDate")),
        categories=tuple(
            text
            for category in node.find_all("category", recursive=False)
            if (text := category.get_text(strip=True))
        ),
    )


def _optional_text(node: Tag, name: str) -> str:
    child = node.find(name, recursive=False)
    return child.get_text().strip() if isinstance(child, Tag) else ""


def _required_text(node: Tag, name: str) -> str:
    text = _optional_text(node, name)
    if not text:
        raise FeedFormatError(f"RSS item has no <{name}> element")
    return text


def _parse_date(value: str) -> datetime:
    try:
        published_at = parsedate_to_datetime(value)
    except (TypeError, ValueError) as exc:
        raise FeedFormatError(f"RSS item has invalid <pubDate>: {value!r}") from exc
    if published_at.tzinfo is None:
        return published_at.replace(tzinfo=UTC)
    return published_at
