import django_filters
from django.db.models import Q, QuerySet

from vacancies.models import Vacancy, search_query


class VacancyFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(method="filter_search", label="Full-text search")
    skills = django_filters.CharFilter(
        method="filter_skills", label="Comma-separated skill slugs, all required"
    )
    source = django_filters.CharFilter(field_name="source__code")
    company = django_filters.CharFilter(field_name="company__slug")
    category = django_filters.CharFilter(method="filter_category")
    remote = django_filters.BooleanFilter(field_name="is_remote")
    english_level = django_filters.ChoiceFilter(choices=Vacancy.EnglishLevel.choices)
    min_salary_usd = django_filters.NumberFilter(
        method="filter_min_salary", label="Published salary reaching this amount"
    )
    published_after = django_filters.IsoDateTimeFilter(field_name="published_at", lookup_expr="gte")

    class Meta:
        model = Vacancy
        fields = ("q", "skills", "source", "company", "category", "remote", "english_level")

    def filter_search(
        self, queryset: QuerySet[Vacancy], _name: str, value: str
    ) -> QuerySet[Vacancy]:
        return queryset.filter(search_vector=search_query(value)) if value.strip() else queryset

    def filter_skills(
        self, queryset: QuerySet[Vacancy], _name: str, value: str
    ) -> QuerySet[Vacancy]:
        for slug in filter(None, (part.strip() for part in value.split(","))):
            queryset = queryset.filter(skills__slug=slug)
        return queryset

    def filter_category(
        self, queryset: QuerySet[Vacancy], _name: str, value: str
    ) -> QuerySet[Vacancy]:
        return queryset.filter(categories__contains=[value])

    def filter_min_salary(
        self, queryset: QuerySet[Vacancy], _name: str, value: float
    ) -> QuerySet[Vacancy]:
        return queryset.filter(
            Q(salary_max_usd__gte=value) | Q(salary_max_usd__isnull=True, salary_min_usd__gte=value)
        )
