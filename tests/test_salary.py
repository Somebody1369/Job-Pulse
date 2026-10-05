import pytest

from vacancies.salary import SalaryRange, format_salary_range, parse_salary


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("$1200–2800", SalaryRange(1200, 2800, "USD")),
        ("від\u00a0$1500", SalaryRange(1500, None, "USD")),
        ("до $1500", SalaryRange(None, 1500, "USD")),
        ("від 40 000 грн", SalaryRange(40000, None, "UAH")),
        ("30 000–45 000 ₴", SalaryRange(30000, 45000, "UAH")),
        ("€3000-4000", SalaryRange(3000, 4000, "EUR")),
        ("$3–4k", SalaryRange(3000, 4000, "USD")),
        ("5000 USD", SalaryRange(5000, 5000, "USD")),
        ("up to 2500 EUR", SalaryRange(None, 2500, "EUR")),
        ("$4000–3000", SalaryRange(3000, 4000, "USD")),
    ],
)
def test_parse_salary(text: str, expected: SalaryRange) -> None:
    assert parse_salary(text) == expected


@pytest.mark.parametrize("text", ["", "за домовленістю", "$", "3000–4000"])
def test_parse_salary_requires_amount_and_currency(text: str) -> None:
    assert parse_salary(text) is None


@pytest.mark.parametrize(
    ("minimum", "maximum", "expected"),
    [
        (None, None, "—"),
        (1500, None, "from 1500"),
        (None, 2500, "up to 2500"),
        (2000, 2000, "2000"),
        (1200, 2800, "1200–2800"),
    ],
)
def test_format_salary_range(minimum: int | None, maximum: int | None, expected: str) -> None:
    assert format_salary_range(minimum, maximum) == expected
