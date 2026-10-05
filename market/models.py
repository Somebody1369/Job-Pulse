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
