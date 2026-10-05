import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Final, Self

from vacancies.models import Skill

BOUNDARY_BEFORE: Final = r"(?<![\w.#+])"
BOUNDARY_AFTER: Final = r"(?![\w#+])"


def compile_phrases(phrases: Iterable[str], *, case_sensitive: bool) -> re.Pattern[str] | None:
    unique_phrases = sorted({phrase for phrase in phrases if phrase}, key=len, reverse=True)
    if not unique_phrases:
        return None
    alternatives = "|".join(map(re.escape, unique_phrases))
    flags = 0 if case_sensitive else re.IGNORECASE
    return re.compile(f"{BOUNDARY_BEFORE}(?:{alternatives}){BOUNDARY_AFTER}", flags)


def compile_skill_pattern(variants: Iterable[str], *, case_sensitive: bool) -> re.Pattern[str]:
    pattern = compile_phrases(variants, case_sensitive=case_sensitive)
    if pattern is None:
        raise ValueError("A skill pattern requires at least one non-empty variant")
    return pattern


@dataclass(frozen=True, slots=True)
class SkillRule:
    pattern: re.Pattern[str]
    stop_pattern: re.Pattern[str] | None = None

    def matches(self, text: str) -> bool:
        if self.stop_pattern is not None:
            text = self.stop_pattern.sub(" ", text)
        return self.pattern.search(text) is not None


class SkillMatcher:
    def __init__(self, rules: Mapping[int, SkillRule]) -> None:
        self._rules = dict(rules)

    @classmethod
    def from_skills(cls, skills: Iterable[Skill]) -> Self:
        return cls(
            {
                skill.pk: SkillRule(
                    pattern=compile_skill_pattern(
                        skill.variants, case_sensitive=skill.is_case_sensitive
                    ),
                    stop_pattern=compile_phrases(skill.stop_phrases, case_sensitive=False),
                )
                for skill in skills
            }
        )

    def match(self, text: str, *, ignore: Iterable[str] = ()) -> set[int]:
        ignored = compile_phrases(ignore, case_sensitive=False)
        if ignored is not None:
            text = ignored.sub(" ", text)
        return {skill_id for skill_id, rule in self._rules.items() if rule.matches(text)}
