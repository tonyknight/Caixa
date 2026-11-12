"""The collector contract: how one kind of export enters a box.

A collector declares what it is (`CollectorInfo`: id, name, platform, accepted inputs, "how to
export" instructions, an options JSON Schema the UI renders as a form) and can

- `preview(source, options, box=None)`: a dry run that writes nothing: counts, date range, participants,
  unresolved handles;
- `run(box, source, options, progress)`: the real import into a box, reporting `Progress` as it goes.

The user interface is built from these declarations, so a new source needs no UI code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Mapping, Optional, Protocol, runtime_checkable
from pathlib import Path

if TYPE_CHECKING:
    from caixa.box import Box

#: What a collector can be pointed at.
INPUT_KINDS = ("zip", "folder", "file", "database")


@dataclass(frozen=True)
class CollectorInfo:
    id: str
    name: str
    platform: str
    inputs: tuple[str, ...]
    how_to_export: str
    options_schema: dict[str, Any]

    def __post_init__(self) -> None:
        unknown = [kind for kind in self.inputs if kind not in INPUT_KINDS]
        if unknown or not self.inputs:
            raise ValueError(
                f"Collector '{self.id}' must accept at least one of {', '.join(INPUT_KINDS)}; "
                f"got {list(self.inputs)}."
            )


@dataclass
class Preview:
    """What a run would import, found without writing anything."""

    items: int = 0
    conversations: int = 0
    first: Optional[str] = None  # ISO date of the earliest item
    last: Optional[str] = None
    participants: list[str] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)  # handles no person is known for
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Progress:
    stage: str  # a short machine-readable step: "reading", "importing", "rendering", …
    current: int = 0
    total: Optional[int] = None
    message: str = ""


@dataclass
class RunResult:
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    pages: int = 0
    unresolved: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    #: Files that changed place in the box, as (from, to) relative to it (a person was named and
    #: their files followed). Caixa keeps this for undo; it is not shown.
    moved: list[tuple[str, str]] = field(default_factory=list)


@runtime_checkable
class Collector(Protocol):
    info: CollectorInfo

    # A collector's `preview` may also take `progress: Optional[Callable[[Progress], None]]`
    # (keyword). When it does, Caixa passes one, so a long preview can show how far it is and
    # can be cancelled (the callback raises). Collectors without it preview silently.
    def preview(
        self, source: Path, options: Mapping[str, Any], box: Optional["Box"] = None
    ) -> Preview: ...

    def run(
        self,
        box: "Box",
        source: Path,
        options: Mapping[str, Any],
        progress: Callable[[Progress], None],
    ) -> RunResult: ...


@runtime_checkable
class PeopleAware(Protocol):
    """Optional: a collector that can name who its data is still missing, and redo its pages.

    Collectors that share one working folder share a `work_key`, so the service asks only one of
    them. `refresh` re-matches people from the box's current aliases, redraws the pages that
    changed (removing the ones that no longer apply) and updates the master.
    """

    work_key: str

    def unresolved(self, box: "Box") -> list[dict[str, Any]]: ...

    def refresh(self, box: "Box", progress: Callable[[Progress], None]) -> RunResult: ...
