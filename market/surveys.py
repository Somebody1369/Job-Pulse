import csv
import io
import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Final

SURVEY_URL_TEMPLATE: Final = (
    "https://raw.githubusercontent.com/devua/csv/master/salaries/{name}_raw.csv"
)
ENCODINGS: Final = ("utf-8-sig", "cp1251")
MONTHS: Final = {"june": 6, "dec": 12}
MAX_MONTHLY_SALARY: Final = 100_000

SALARY_COLUMN: Final = ("зарплата",)
EXPERIENCE_COLUMN: Final = ("загальний стаж",)
LANGUAGE_COLUMN: Final = ("основна мова програмування",)
ENGLISH_COLUMN: Final = ("знання англійської",)
POSITION_COLUMN: Final = ("основну посаду", "position", "посади")
SENIORITY_COLUMN: Final = ("title_clean", "тайтл")

EXPERIENCE_PHRASES: Final = {
    "менше як 3 місяці": Decimal("0.1"),
    "3 місяці": Decimal("0.25"),
    "пів року": Decimal("0.5"),
    "півтора роки": Decimal("1.5"),
    "понад 20 років": Decimal("20"),
}
LANGUAGE_ALIASES: Final = {
    "c#  net": "C# / .NET",
    "bash  shell": "Bash / Shell",
    "не можу обрати одну основну мову": "",
}

_LEADING_NUMBER = re.compile(r"^\d+(?:[.,]\d+)?")
_ENUMERATION_PREFIX = re.compile(r"^\d+\.\s*")


class SurveyFormatError(ValueError):
    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class SurveyResponse:
    salary_usd: int
    experience_years: Decimal | None
    programming_language: str
    position: str
    seniority: str
    english_level: str


def survey_period(name: str) -> date:
    year, _, month = name.partition("_")
    try:
        return date(int(year), MONTHS[month], 1)
    except (KeyError, ValueError) as exc:
        raise SurveyFormatError(f"Unexpected survey name {name!r}") from exc


def decode_survey(content: bytes) -> str:
    for encoding in ENCODINGS:
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise SurveyFormatError("Survey file uses an unsupported encoding")


def parse_survey(text: str) -> Iterator[SurveyResponse]:
    reader = csv.reader(io.StringIO(text))
    header = next(reader, None)
    if header is None:
        raise SurveyFormatError("Survey file is empty")
    salary = _column(header, SALARY_COLUMN)
    experience = _column(header, EXPERIENCE_COLUMN)
    language = _column(header, LANGUAGE_COLUMN)
    english = _column(header, ENGLISH_COLUMN)
    position = _optional_column(header, POSITION_COLUMN)
    seniority = _optional_column(header, SENIORITY_COLUMN)
    for row in reader:
        salary_usd = parse_salary(_cell(row, salary))
        if salary_usd is None:
            continue
        yield SurveyResponse(
            salary_usd=salary_usd,
            experience_years=parse_experience(_cell(row, experience)),
            programming_language=normalize_language(_cell(row, language)),
            position=_text(row, position, 128),
            seniority=_text(row, seniority, 64),
            english_level=normalize_english(_cell(row, english)),
        )


def parse_salary(value: str) -> int | None:
    try:
        amount = Decimal(value.replace(",", ".").replace(" ", ""))
    except InvalidOperation:
        return None
    if not 0 < amount <= MAX_MONTHLY_SALARY:
        return None
    return int(amount)


def parse_experience(value: str) -> Decimal | None:
    text = " ".join(value.casefold().split())
    if text in EXPERIENCE_PHRASES:
        return EXPERIENCE_PHRASES[text]
    match = _LEADING_NUMBER.match(text)
    if match is None:
        return None
    return Decimal(match.group().replace(",", "."))


def normalize_language(value: str) -> str:
    language = value.strip()
    return LANGUAGE_ALIASES.get(language.casefold(), " ".join(language.split()))[:64]


def normalize_english(value: str) -> str:
    return _ENUMERATION_PREFIX.sub("", value.strip())[:32]


def _column(header: Sequence[str], keywords: Sequence[str]) -> int:
    index = _optional_column(header, keywords)
    if index is None:
        raise SurveyFormatError(f"Survey has no column matching {keywords!r}")
    return index


def _optional_column(header: Sequence[str], keywords: Sequence[str]) -> int | None:
    names = [column.casefold() for column in header]
    for keyword in keywords:
        for index, name in enumerate(names):
            if keyword in name:
                return index
    return None


def _cell(row: Sequence[str], index: int) -> str:
    return row[index].strip() if index < len(row) else ""


def _text(row: Sequence[str], index: int | None, limit: int) -> str:
    if index is None:
        return ""
    return " ".join(_cell(row, index).split())[:limit]
