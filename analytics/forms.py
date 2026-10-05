from typing import Any, cast

from django import forms

from analytics.dashboard import DEFAULT_CATEGORY, DEFAULT_LANGUAGE, PERIOD_CHOICES, Filters


class FilterForm(forms.Form):
    language = forms.ChoiceField(required=False)
    category = forms.ChoiceField(required=False)
    days = forms.TypedChoiceField(
        label="Skills period",
        choices=[(days, f"{days} days") for days in PERIOD_CHOICES],
        coerce=int,
        required=False,
    )

    def __init__(
        self,
        data: Any = None,
        *,
        languages: list[str],
        categories: list[tuple[str, str]],
    ) -> None:
        self.defaults = Filters(
            language=DEFAULT_LANGUAGE
            if DEFAULT_LANGUAGE in languages
            else next(iter(languages), ""),
            category=DEFAULT_CATEGORY
            if DEFAULT_CATEGORY in dict(categories)
            else next(iter(dict(categories)), ""),
        )
        super().__init__(
            data,
            initial={
                "language": self.defaults.language,
                "category": self.defaults.category,
                "days": self.defaults.days,
            },
        )
        self._choice_field("language").choices = [(language, language) for language in languages]
        self._choice_field("category").choices = categories

    def filters(self) -> Filters:
        if not self.is_bound or not self.is_valid():
            return self.defaults
        data = self.cleaned_data
        return Filters(
            language=data["language"] or self.defaults.language,
            category=data["category"] if "category" in self.data else self.defaults.category,
            days=data["days"] or self.defaults.days,
        )

    def _choice_field(self, name: str) -> forms.ChoiceField:
        return cast(forms.ChoiceField, self.fields[name])
