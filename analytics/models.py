from django.db import models


class DashboardReport(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    image = models.BinaryField()

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"Dashboard report {self.created_at:%Y-%m-%d %H:%M}"
