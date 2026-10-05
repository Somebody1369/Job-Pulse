import pytest

from vacancies.models import Skill
from vacancies.skills import SkillMatcher, compile_skill_pattern

GO = ("Go", "Golang", "golang")
DOTNET = (".NET", "dotnet", "ASP.NET")
NODE = ("Node.js", "NodeJS", "Node")


@pytest.mark.parametrize(
    ("variants", "case_sensitive", "text", "expected"),
    [
        (("Java",), False, "Senior JavaScript developer", False),
        (("Java",), False, "Java/Kotlin backend", True),
        (("C#",), False, "C#/.NET developer", True),
        (("C++",), False, "Modern C++ and Rust", True),
        (DOTNET, False, "ASP.NET Core services", True),
        ((".NET",), False, "ASP.NET Core services", False),
        (NODE, True, "Node.js and NestJS", True),
        (GO, True, "Backend in Go, Kafka and gRPC", True),
        (GO, True, "Ready to go to production", False),
        (GO, True, "Google Cloud", False),
        (("PostgreSQL", "Postgres"), False, "postgres replication", True),
        (("Python",), False, "Python-based tooling", True),
        (("SQL",), False, "PostgreSQL only", False),
        (("React", "React.js", "ReactJS"), True, "able to react quickly", False),
    ],
)
def test_compile_skill_pattern(
    variants: tuple[str, ...], case_sensitive: bool, text: str, expected: bool
) -> None:
    pattern = compile_skill_pattern(variants, case_sensitive=case_sensitive)

    assert (pattern.search(text) is not None) is expected


def test_compile_skill_pattern_requires_variants() -> None:
    with pytest.raises(ValueError, match="non-empty variant"):
        compile_skill_pattern(["", ""], case_sensitive=False)


def test_skill_matcher_returns_matching_skill_ids() -> None:
    matcher = SkillMatcher.from_skills(
        [
            Skill(pk=1, name="Django"),
            Skill(pk=2, name="PostgreSQL", aliases=["Postgres"]),
            Skill(pk=3, name="Go", aliases=["Golang"], is_case_sensitive=True),
        ]
    )

    assert matcher.match("Django + Postgres, go-to person for APIs") == {1, 2}
