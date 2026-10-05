from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Final, Self

from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector, SearchVectorField
from django.db import models
from django.db.models import F
from django.utils import timezone

from vacancies.dedup import vacancy_fingerprint

if TYPE_CHECKING:
    from vacancies.services import IngestStats

SEARCH_CONFIG: Final = "english"


class Source(models.Model):
    class Kind(models.TextChoices):
        RSS = "rss", "RSS feed"
        API = "api", "API"
        HTML = "html", "HTML pages"

    code = models.SlugField(max_length=32, unique=True)
    name = models.CharField(max_length=64)
    homepage = models.URLField()
    kind = models.CharField(max_length=8, choices=Kind)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class Company(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, allow_unicode=True)
    website = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("name",)
        verbose_name_plural = "companies"

    def __str__(self) -> str:
        return self.name


class Skill(models.Model):
    name = models.CharField(max_length=64, unique=True)
    slug = models.SlugField(max_length=64, unique=True)
    aliases = ArrayField(models.CharField(max_length=64), default=list, blank=True)
    is_case_sensitive = models.BooleanField(default=False)

    class Meta:
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name

    @property
    def variants(self) -> list[str]:
        return [self.name, *self.aliases]


def search_query(text: str) -> SearchQuery:
    return SearchQuery(text, search_type="websearch", config=SEARCH_CONFIG)


class VacancyQuerySet(models.QuerySet["Vacancy"]):
    def distinct_postings(self) -> Self:
        return self.order_by("fingerprint", "-published_at").distinct("fingerprint")

    def search(self, text: str) -> Self:
        query = search_query(text)
        return (
            self.filter(search_vector=query)
            .annotate(rank=SearchRank(F("search_vector"), query))
            .order_by("-rank", "-published_at")
        )


class Vacancy(models.Model):
    class EnglishLevel(models.TextChoices):
        A1 = "A1", "A1 Beginner"
        A2 = "A2", "A2 Elementary"
        B1 = "B1", "B1 Intermediate"
        B2 = "B2", "B2 Upper-intermediate"
        C1 = "C1", "C1 Advanced"
        C2 = "C2", "C2 Proficient"

    source = models.ForeignKey(Source, on_delete=models.PROTECT, related_name="vacancies")
    external_id = models.CharField(max_length=64)
    url = models.URLField(max_length=1000)
    title = models.CharField(max_length=500)
    company = models.ForeignKey(
        Company,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vacancies",
    )
    categories = ArrayField(models.CharField(max_length=64), default=list, blank=True)
    locations = ArrayField(models.CharField(max_length=128), default=list, blank=True)
    is_remote = models.BooleanField(null=True, blank=True)
    salary_text = models.CharField(max_length=64, blank=True)
    salary_min = models.PositiveIntegerField(null=True, blank=True)
    salary_max = models.PositiveIntegerField(null=True, blank=True)
    salary_currency = models.CharField(max_length=3, blank=True)
    salary_min_usd = models.PositiveIntegerField(null=True, blank=True)
    salary_max_usd = models.PositiveIntegerField(null=True, blank=True)
    experience_months = models.PositiveSmallIntegerField(null=True, blank=True)
    english_level = models.CharField(max_length=2, choices=EnglishLevel, blank=True)
    description = models.TextField(blank=True)
    description_html = models.TextField(blank=True)
    skills = models.ManyToManyField(Skill, related_name="vacancies", blank=True)
    published_at = models.DateTimeField()
    first_seen_at = models.DateTimeField(default=timezone.now)
    last_seen_at = models.DateTimeField(default=timezone.now)
    details_fetched_at = models.DateTimeField(null=True, blank=True)
    fingerprint = models.CharField(max_length=64, db_index=True, editable=False, default="")
    search_vector = models.GeneratedField(
        expression=SearchVector("title", weight="A", config=SEARCH_CONFIG)
        + SearchVector("description", weight="B", config=SEARCH_CONFIG),
        output_field=SearchVectorField(),
        db_persist=True,
    )

    objects = VacancyQuerySet.as_manager()

    class Meta:
        ordering = ("-published_at",)
        verbose_name_plural = "vacancies"
        constraints = (
            models.UniqueConstraint(
                fields=("source", "external_id"),
                name="vacancy_unique_per_source",
            ),
            models.CheckConstraint(
                condition=models.Q(salary_min__isnull=True)
                | models.Q(salary_max__isnull=True)
                | models.Q(salary_min__lte=models.F("salary_max")),
                name="vacancy_salary_range_valid",
            ),
        )
        indexes = (
            models.Index(fields=("-published_at",), name="vacancy_published_idx"),
            GinIndex(fields=("categories",), name="vacancy_categories_gin"),
            GinIndex(fields=("search_vector",), name="vacancy_search_gin"),
        )

    def __str__(self) -> str:
        return self.title

    def refresh_fingerprint(self) -> None:
        self.fingerprint = vacancy_fingerprint(
            company=self.company.slug if self.company else "",
            title=self.title,
            fallback=f"{self.source_id}:{self.external_id}",
        )


class ScrapeRun(models.Model):
    class Kind(models.TextChoices):
        FEED = "feed", "Feed"
        DETAILS = "details", "Details"

    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    source = models.ForeignKey(Source, on_delete=models.CASCADE, related_name="runs")
    kind = models.CharField(max_length=16, choices=Kind, default=Kind.FEED)
    categories = ArrayField(models.CharField(max_length=64), default=list, blank=True)
    status = models.CharField(max_length=16, choices=Status, default=Status.RUNNING)
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    fetched_count = models.PositiveIntegerField(default=0)
    created_count = models.PositiveIntegerField(default=0)
    updated_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    error = models.TextField(blank=True)

    class Meta:
        ordering = ("-started_at",)
        indexes = (
            models.Index(fields=("source", "-started_at"), name="scraperun_source_started_idx"),
        )

    def __str__(self) -> str:
        return f"{self.source} at {self.started_at:%Y-%m-%d %H:%M}"

    @property
    def duration(self) -> timedelta | None:
        if self.finished_at is None:
            return None
        return self.finished_at - self.started_at

    def mark_succeeded(self, stats: IngestStats) -> None:
        self.status = self.Status.SUCCEEDED
        self.fetched_count = stats.fetched
        self.created_count = stats.created
        self.updated_count = stats.updated
        self.failed_count = stats.failed
        self.finished_at = timezone.now()
        self.save(
            update_fields=(
                "status",
                "fetched_count",
                "created_count",
                "updated_count",
                "failed_count",
                "finished_at",
            )
        )

    def mark_failed(self, error: BaseException) -> None:
        self.status = self.Status.FAILED
        self.error = f"{type(error).__name__}: {error}"
        self.finished_at = timezone.now()
        self.save(update_fields=("status", "error", "finished_at"))
