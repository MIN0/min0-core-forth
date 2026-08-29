"""Typed relocation records emitted while MIN0 CORE FORTH images are built."""

from __future__ import annotations

from dataclasses import asdict, dataclass


SECTION_CODE = "code"
TARGET_CODE = "code"
TARGET_DICTIONARY = "dictionary"
TARGET_DATA = "data"
REFERENCE32_WIDTH = 4


@dataclass(frozen=True)
class RelocationRecord:
    """One typed address cell relative to the start of an image section."""

    section: str
    offset: int
    target: str
    width: int
    kind: str

    def to_dict(self) -> dict[str, str | int]:
        return asdict(self)
