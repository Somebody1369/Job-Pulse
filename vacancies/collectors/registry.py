from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from vacancies.collectors.base import Collector
from vacancies.collectors.djinni import DjinniCollector
from vacancies.collectors.dou import DouCollector


class UnknownSourceError(LookupError):
    pass


COLLECTORS: Final[Mapping[str, type[Collector]]] = MappingProxyType(
    {collector.source_code: collector for collector in (DouCollector, DjinniCollector)}
)


def get_collector_class(source_code: str) -> type[Collector]:
    try:
        return COLLECTORS[source_code]
    except KeyError as exc:
        raise UnknownSourceError(f"No collector registered for source {source_code!r}") from exc
