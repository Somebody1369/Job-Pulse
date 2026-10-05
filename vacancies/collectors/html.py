import re
from typing import Final

from bs4 import BeautifulSoup
from bs4.element import NavigableString

BLOCK_TAGS: Final = (
    "article",
    "blockquote",
    "div",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "li",
    "ol",
    "p",
    "pre",
    "section",
    "table",
    "tr",
    "ul",
)
LIST_ITEM_PREFIX: Final = "• "

_WHITESPACE = re.compile(r"\s+")


def html_to_text(markup: str, *, exclude: str | None = None) -> str:
    soup = BeautifulSoup(markup, "lxml")
    if exclude:
        for node in soup.select(exclude):
            node.decompose()
    _collapse_whitespace(soup)
    for line_break in soup.find_all("br"):
        line_break.replace_with("\n")
    for item in soup.find_all("li"):
        item.insert(0, LIST_ITEM_PREFIX)
    for block in soup.find_all(BLOCK_TAGS):
        block.insert_after("\n")
    lines = (_WHITESPACE.sub(" ", line).strip() for line in soup.get_text().splitlines())
    return "\n".join(line for line in lines if line and line != LIST_ITEM_PREFIX.strip())


def _collapse_whitespace(soup: BeautifulSoup) -> None:
    for node in soup.find_all(string=True):
        if type(node) is NavigableString and node.find_parent("pre") is None:
            node.replace_with(_WHITESPACE.sub(" ", node))
