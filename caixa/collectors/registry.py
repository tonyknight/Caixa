"""Finding collectors: the `caixa.collectors` entry-point group.

A package registers collectors in its `pyproject.toml`:

    [project.entry-points."caixa.collectors"]
    chattr = "caixa.collectors.chattr:collectors"

The entry point is a callable returning one collector or a list of them. One broken plugin never
hides the others: its problem is recorded on the registry (`problems`) for `caixa doctor` and
`caixa collectors` to tell.

Entry points are written into a package's metadata when it is installed, not read from
`pyproject.toml` as it runs: a checkout brought up to date with `git pull` but not installed
again keeps the list it was installed with. So Caixa's own collectors (`BUILT_IN`) are loaded
even when the installed metadata lacks them; such a fallback is noted (`fallbacks`), so the doctor
can say to install again.
"""

from __future__ import annotations

from importlib.metadata import EntryPoint, entry_points
from typing import Any, Callable, Iterable, Optional

from caixa.collectors.base import Collector

GROUP = "caixa.collectors"
#: Caixa's own collectors, as `pyproject.toml` registers them.
BUILT_IN = {
    "chattr": "caixa.collectors.chattr:collectors",
    "pdf": "caixa.collectors.pdfImport:collectors",
}


class Registry:
    def __init__(self) -> None:
        self._collectors: dict[str, Collector] = {}
        self._sources: dict[str, str] = {}
        self.problems: list[str] = []
        #: Caixa's own entry points the installed metadata lacked, loaded all the same.
        self.fallbacks: list[str] = []

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


def discover(plugins: Optional[Iterable[Any]] = None, built_in: Optional[bool] = None) -> Registry:
    """Load every registered collector, and Caixa's own whether or not the install recorded them
    (see the module text). `plugins` replaces the installed entry points, for tests; then the
    built-in collectors are added only with `built_in=True`."""
    registry = Registry()
    found = list(plugins) if plugins is not None else list(entry_points(group=GROUP))
    if built_in if built_in is not None else plugins is None:
        named = {getattr(plugin, "name", None) for plugin in found}
        for name, value in BUILT_IN.items():
            if name not in named:
                found.append(EntryPoint(name=name, value=value, group=GROUP))
                registry.fallbacks.append(name)
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
