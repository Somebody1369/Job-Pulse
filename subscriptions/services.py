from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final

from django.db.models import Q

from subscriptions.models import Delivery, Subscription
from vacancies.models import Vacancy, VacancyQuerySet

INITIAL_LOOKBACK: Final = timedelta(days=1)
NOTIFICATION_WINDOW: Final = timedelta(days=3)
MONTHS_PER_YEAR: Final = 12


@dataclass(frozen=True, slots=True)
class Notification:
    subscription: Subscription
    vacancy: Vacancy


def matching_vacancies(subscription: Subscription, *, since: datetime) -> VacancyQuerySet:
    vacancies = Vacancy.objects.filter(published_at__gte=since)
    for skill in subscription.skills.all():
        vacancies = vacancies.filter(skills=skill)
    if subscription.remote_only:
        vacancies = vacancies.filter(is_remote=True)
    if subscription.min_salary_usd is not None:
        vacancies = vacancies.filter(
            Q(salary_max_usd__gte=subscription.min_salary_usd)
            | Q(salary_max_usd__isnull=True, salary_min_usd__gte=subscription.min_salary_usd)
            | Q(salary_max_usd__isnull=True, salary_min_usd__isnull=True)
        )
    if subscription.max_experience_years is not None:
        vacancies = vacancies.filter(
            Q(experience_months__lte=subscription.max_experience_years * MONTHS_PER_YEAR)
            | Q(experience_months__isnull=True)
        )
    return vacancies


def pending_notifications(*, now: datetime, limit_per_subscription: int) -> list[Notification]:
    notifications: list[Notification] = []
    subscriptions = (
        Subscription.objects.filter(is_active=True)
        .select_related("subscriber")
        .prefetch_related("skills")
    )
    for subscription in subscriptions:
        since = max(subscription.created_at - INITIAL_LOOKBACK, now - NOTIFICATION_WINDOW)
        delivered = Delivery.objects.filter(subscription=subscription).values(
            "vacancy__fingerprint"
        )
        candidates = (
            matching_vacancies(subscription, since=since)
            .exclude(fingerprint__in=delivered)
            .select_related("company", "source")
            .prefetch_related("skills")
            .distinct_postings()
        )
        newest = sorted(candidates, key=lambda vacancy: vacancy.published_at, reverse=True)
        notifications.extend(
            Notification(subscription=subscription, vacancy=vacancy)
            for vacancy in newest[:limit_per_subscription]
        )
    return notifications


def acknowledge(deliveries: Iterable[tuple[int, int]]) -> None:
    Delivery.objects.bulk_create(
        [
            Delivery(subscription_id=subscription_id, vacancy_id=vacancy_id)
            for subscription_id, vacancy_id in deliveries
        ],
        ignore_conflicts=True,
    )
