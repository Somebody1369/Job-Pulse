from django.db import models

from vacancies.models import Skill, Vacancy


class Subscriber(models.Model):
    chat_id = models.BigIntegerField(unique=True)
    username = models.CharField(max_length=64, blank=True)
    weekly_report = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        permissions = (("access_bot_api", "Can manage subscribers through the bot API"),)

    def __str__(self) -> str:
        return f"@{self.username}" if self.username else str(self.chat_id)


class Subscription(models.Model):
    subscriber = models.ForeignKey(
        Subscriber, on_delete=models.CASCADE, related_name="subscriptions"
    )
    skills = models.ManyToManyField(Skill, related_name="subscriptions", blank=True)
    remote_only = models.BooleanField(default=False)
    min_salary_usd = models.PositiveIntegerField(null=True, blank=True)
    max_experience_years = models.PositiveSmallIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at",)

    def __str__(self) -> str:
        return f"Subscription #{self.pk} of {self.subscriber}"


class Delivery(models.Model):
    subscription = models.ForeignKey(
        Subscription, on_delete=models.CASCADE, related_name="deliveries"
    )
    vacancy = models.ForeignKey(Vacancy, on_delete=models.CASCADE, related_name="deliveries")
    delivered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "deliveries"
        constraints = (
            models.UniqueConstraint(
                fields=("subscription", "vacancy"), name="delivery_unique_per_subscription"
            ),
        )

    def __str__(self) -> str:
        return f"{self.vacancy} to {self.subscription.subscriber}"
