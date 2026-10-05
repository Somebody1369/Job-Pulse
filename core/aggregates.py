from typing import Any

from django.db.models import Aggregate, FloatField


class Percentile(Aggregate):
    function = "PERCENTILE_CONT"
    name = "Percentile"
    output_field = FloatField()
    template = "%(function)s(%(fraction)s) WITHIN GROUP (ORDER BY %(expressions)s)"

    def __init__(self, expression: Any, fraction: float, **extra: Any) -> None:
        if not 0 <= fraction <= 1:
            raise ValueError("fraction must be between 0 and 1")
        super().__init__(expression, fraction=fraction, **extra)


class Median(Percentile):
    name = "Median"

    def __init__(self, expression: Any, **extra: Any) -> None:
        super().__init__(expression, fraction=0.5, **extra)
