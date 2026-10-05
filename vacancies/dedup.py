import hashlib
import re
from typing import Final

from django.utils.text import slugify

LEGAL_FORMS: Final = frozenset(
    {"llc", "inc", "ltd", "limited", "gmbh", "corp", "corporation", "plc", "llp", "тов"}
)

_PARENTHESES = re.compile(r"\([^)]*\)")
_TOKEN_SEPARATORS = re.compile(r"[\s,.]+")
_NON_WORD = re.compile(r"[\W_]+")


def company_key(name: str) -> str:
    tokens = _TOKEN_SEPARATORS.split(_PARENTHESES.sub(" ", name))
    meaningful = " ".join(token for token in tokens if token.casefold() not in LEGAL_FORMS)
    return slugify(meaningful, allow_unicode=True) or slugify(name, allow_unicode=True)


def title_key(title: str) -> str:
    return " ".join(_NON_WORD.sub(" ", title.casefold()).split())


def vacancy_fingerprint(*, company: str, title: str, fallback: str) -> str:
    if not company:
        return fallback
    return hashlib.sha1(f"{company}|{title_key(title)}".encode(), usedforsecurity=False).hexdigest()
