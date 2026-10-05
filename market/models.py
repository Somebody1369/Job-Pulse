from django.db import models


class ExchangeRate(models.Model):
    currency = models.CharField(max_length=3)
    rate_date = models.DateField()
    uah_per_unit = models.DecimalField(max_digits=16, decimal_places=6)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-rate_date", "currency")
        constraints = (
            models.UniqueConstraint(
                fields=("currency", "rate_date"), name="exchange_rate_unique_per_day"
            ),
            models.CheckConstraint(
                condition=models.Q(uah_per_unit__gt=0), name="exchange_rate_positive"
            ),
        )

    def __str__(self) -> str:
        return f"{self.currency} {self.uah_per_unit} UAH on {self.rate_date:%Y-%m-%d}"


class MarketSnapshot(models.Model):
    category = models.CharField(max_length=64, blank=True)
    category_label = models.CharField(max_length=128)
    calculated_on = models.DateField()
    active_candidates = models.PositiveIntegerField()
    expected_min = models.PositiveIntegerField()
    expected_max = models.PositiveIntegerField()
    offers_per_candidate = models.DecimalField(max_digits=8, decimal_places=2)
    vacancies_online = models.PositiveIntegerField()
    vacancies_change = models.IntegerField(null=True, blank=True)
    offered_min = models.PositiveIntegerField()
    offered_max = models.PositiveIntegerField()
    applications_per_vacancy = models.DecimalField(max_digits=8, decimal_places=1)
    djinni_index = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)
    offers_30d = models.PositiveIntegerField(null=True, blank=True)
    applications_30d = models.PositiveIntegerField(null=True, blank=True)
    fetched_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-calculated_on", "category")
        constraints = (
            models.UniqueConstraint(
                fields=("category", "calculated_on"), name="market_snapshot_unique_per_day"
            ),
        )

    def __str__(self) -> str:
        return f"{self.category_label} on {self.calculated_on:%Y-%m-%d}"

    @property
    def candidates_per_vacancy(self) -> float | None:
        if not self.vacancies_online:
            return None
        return round(self.active_candidates / self.vacancies_online, 1)
