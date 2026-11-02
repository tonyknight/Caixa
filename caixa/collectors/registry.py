"""Finding collectors: the `caixa.collectors` entry-point group.

A package registers collectors in its `pyproject.toml`:

    [project.entry-points."caixa.collectors"]
    chattr = "caixa.collectors.chattr:collectors"

The entry point is a callable returning one collector or a list of them. One broken plugin never
hides the others: its problem is recorded on the registry (`problems`) for the UI to show.
"""

from __future__ import annotations

from importlib.metadata import entry_points
from typing import Any, Callable, Iterable, Optional

from caixa.collectors.base import Collector

GROUP = "caixa.collectors"


class Registry:
    def __init__(self) -> None:
        self._collectors: dict[str, Collector] = {}
        self._sources: dict[str, str] = {}
        self.problems: list[str] = []

    def register(self, collector: Collector, source: str = "") -> None:
        if not isinstance(collector, Collector):
            raise TypeError(f"{collector!r} is not a collector (it needs info, preview and run).")
        collector_id = collector.info.id
        if collector_id in self._collectors:
            raise ValueError(f"A collector with id '{collector_id}' is already registered.")
        self._collectors[collector_id] = collector
        self._sources[collector_id] = source or collector_id

    def get(self, collector_id: str) -> Collector:
        try:
            return self._collectors[collector_id]
        except KeyError:
            raise KeyError(f"No collector '{collector_id}'.") from None

    def all(self) -> list[Collector]:
        """Every collector, by display name."""
        return sorted(self._collectors.values(), key=lambda c: c.info.name.casefold())

    def describe(self) -> list[dict[str, Any]]:
        """What the UI renders: plain JSON for each collector."""
        return [
            {
                "id": c.info.id,
                "name": c.info.name,
                "platform": c.info.platform,
                "inputs": list(c.info.inputs),
                "how_to_export": c.info.how_to_export,
                "options_schema": c.info.options_schema,
                "source": self._sources[c.info.id],
            }
            for c in self.all()
        ]


def discover(plugins: Optional[Iterable[Any]] = None) -> Registry:
    """Load every registered collector (`plugins` replaces the installed entry points, for tests)."""
    registry = Registry()
    found = list(plugins) if plugins is not None else list(entry_points(group=GROUP))
    for plugin in found:
        name = getattr(plugin, "name", "?")
        try:
            loaded: Callable[[], Any] | Any = plugin.load()
            produced = (
                loaded() if callable(loaded) and not isinstance(loaded, Collector) else loaded
            )
            for collector in produced if isinstance(produced, (list, tuple)) else [produced]:
                registry.register(collector, source=name)
        except Exception as error:  # a broken plugin must not take the others down
            registry.problems.append(f"{name}: {type(error).__name__}: {error}")
    return registry
