import re
from collections.abc import Iterable, Mapping
from typing import Final, Self

from vacancies.models import Skill

BOUNDARY_BEFORE: Final = r"(?<![\w.#+])"
BOUNDARY_AFTER: Final = r"(?![\w#+])"


def compile_skill_pattern(variants: Iterable[str], *, case_sensitive: bool) -> re.Pattern[str]:
    unique_variants = sorted({variant for variant in variants if variant}, key=len, reverse=True)
    if not unique_variants:
        raise ValueError("A skill pattern requires at least one non-empty variant")
    alternatives = "|".join(map(re.escape, unique_variants))
    flags = 0 if case_sensitive else re.IGNORECASE
    return re.compile(f"{BOUNDARY_BEFORE}(?:{alternatives}){BOUNDARY_AFTER}", flags)


class SkillMatcher:
    def __init__(self, patterns: Mapping[int, re.Pattern[str]]) -> None:
        self._patterns = dict(patterns)

    @classmethod
    def from_skills(cls, skills: Iterable[Skill]) -> Self:
        return cls(
            {
                skill.pk: compile_skill_pattern(
                    skill.variants, case_sensitive=skill.is_case_sensitive
                )
                for skill in skills
            }
        )

    def match(self, text: str) -> set[int]:
        return {skill_id for skill_id, pattern in self._patterns.items() if pattern.search(text)}
