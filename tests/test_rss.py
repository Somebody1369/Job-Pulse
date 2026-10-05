from datetime import UTC, datetime, timedelta, timezone

import pytest

from tests.utils import read_fixture, rss_document
from vacancies.collectors.rss import FeedFormatError, parse_feed

KYIV_SUMMER = timezone(timedelta(hours=3))


def test_parse_feed_reads_items_from_real_feed() -> None:
    items = parse_feed(read_fixture("djinni_python.xml"))

    assert len(items) == 3
    first = items[0]
    assert first.title == "Senior Backend Engineer (Go), generative image and video, AI product"
    assert first.link == (
        "https://djinni.co/jobs/851542-senior-backend-engineer-go-generative-image-a/"
    )
    assert first.published_at == datetime(2026, 10, 5, 13, 21, 39, tzinfo=KYIV_SUMMER)
    assert first.categories == ("Python",)
    assert first.description_html.startswith("<p>We are New Wave Devs")


def test_parse_feed_requires_channel() -> None:
    with pytest.raises(FeedFormatError, match="channel"):
        parse_feed("<html><body>Maintenance</body></html>")


@pytest.mark.parametrize("missing", ["title", "link", "pubDate"])
def test_parse_feed_requires_mandatory_item_fields(missing: str) -> None:
    fields = {
        "title": "Python Developer",
        "link": "https://example.com/jobs/1/",
        "pubDate": "Mon, 05 Oct 2026 10:00:00 +0300",
    }
    item = "".join(f"<{tag}>{value}</{tag}>" for tag, value in fields.items() if tag != missing)

    with pytest.raises(FeedFormatError, match=missing):
        parse_feed(rss_document(f"<item>{item}</item>"))


def test_parse_feed_rejects_invalid_date() -> None:
    item = (
        "<item><title>Dev</title><link>https://example.com/1</link><pubDate>soon</pubDate></item>"
    )

    with pytest.raises(FeedFormatError, match="pubDate"):
        parse_feed(rss_document(item))


def test_parse_feed_treats_unknown_timezone_as_utc() -> None:
    item = (
        "<item><title>Dev</title><link>https://example.com/1</link>"
        "<pubDate>Mon, 05 Oct 2026 10:00:00 -0000</pubDate></item>"
    )

    (parsed,) = parse_feed(rss_document(item))

    assert parsed.published_at == datetime(2026, 10, 5, 10, 0, tzinfo=UTC)
    assert parsed.description_html == ""
    assert parsed.categories == ()
