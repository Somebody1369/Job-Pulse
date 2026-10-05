from typing import cast, override

from django.contrib import admin
from django.db.models import Count, Model, QuerySet
from django.http import HttpRequest
from django.utils.html import format_html
from django.utils.safestring import SafeString

from vacancies.models import Company, ScrapeRun, Skill, Source, Vacancy
from vacancies.salary import format_salary_range


class VacancyCountAdmin[ModelT: Model](admin.ModelAdmin[ModelT]):
    @override
    def get_queryset(self, request: HttpRequest) -> QuerySet[ModelT]:
        queryset = super().get_queryset(request).annotate(vacancy_total=Count("vacancies"))
        return cast("QuerySet[ModelT]", queryset)

    @admin.display(description="Vacancies", ordering="vacancy_total")
    def vacancy_count(self, obj: ModelT) -> int:
        return int(getattr(obj, "vacancy_total", 0))


@admin.register(Source)
class SourceAdmin(VacancyCountAdmin[Source]):
    list_display = ("name", "code", "kind", "is_active", "vacancy_count")
    list_filter = ("kind", "is_active")


@admin.register(Company)
class CompanyAdmin(VacancyCountAdmin[Company]):
    list_display = ("name", "website", "vacancy_count", "created_at")
    search_fields = ("name",)
    readonly_fields = ("slug", "created_at")


@admin.register(Skill)
class SkillAdmin(VacancyCountAdmin[Skill]):
    list_display = ("name", "aliases", "is_case_sensitive", "vacancy_count")
    list_filter = ("is_case_sensitive",)
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Vacancy)
class VacancyAdmin(admin.ModelAdmin[Vacancy]):
    list_display = (
        "title",
        "company",
        "source",
        "salary_usd",
        "is_remote",
        "published_at",
        "original",
    )
    list_filter = (
        "source",
        "is_remote",
        "english_level",
        "salary_currency",
        "published_at",
        "skills",
    )
    list_select_related = ("source", "company")
    search_fields = ("title", "company__name", "description")
    date_hierarchy = "published_at"
    autocomplete_fields = ("company",)
    filter_horizontal = ("skills",)
    readonly_fields = ("original", "first_seen_at", "last_seen_at", "details_fetched_at")
    fieldsets = (
        (None, {"fields": ("title", "company", "source", "external_id", "url", "original")}),
        (
            "Details",
            {
                "fields": (
                    "categories",
                    "skills",
                    "locations",
                    "is_remote",
                    "experience_months",
                    "english_level",
                )
            },
        ),
        (
            "Salary",
            {
                "fields": (
                    "salary_text",
                    ("salary_min", "salary_max", "salary_currency"),
                    ("salary_min_usd", "salary_max_usd"),
                )
            },
        ),
        ("Description", {"fields": ("description", "description_html")}),
        (
            "Timeline",
            {"fields": ("published_at", "first_seen_at", "last_seen_at", "details_fetched_at")},
        ),
    )

    @admin.display(description="Salary, USD", ordering="salary_min_usd")
    def salary_usd(self, obj: Vacancy) -> str:
        return format_salary_range(obj.salary_min_usd, obj.salary_max_usd)

    @admin.display(description="Original")
    def original(self, obj: Vacancy) -> SafeString:
        return format_html('<a href="{}" target="_blank" rel="noopener">Open</a>', obj.url)


@admin.register(ScrapeRun)
class ScrapeRunAdmin(admin.ModelAdmin[ScrapeRun]):
    list_display = (
        "source",
        "kind",
        "status",
        "started_at",
        "duration",
        "fetched_count",
        "created_count",
        "updated_count",
        "failed_count",
    )
    list_filter = ("kind", "status", "source")
    list_select_related = ("source",)
    date_hierarchy = "started_at"

    @override
    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    @override
    def has_change_permission(self, request: HttpRequest, obj: ScrapeRun | None = None) -> bool:
        return False
