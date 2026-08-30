"""Trusted anti-rollback generation state for the MIN0 CORE FORTH host prototype."""

from __future__ import annotations

from min0_core_forth_image import MAX_GENERATION


class GenerationError(ValueError):
    pass


def validate_generation(value: object, label: str = "generation") -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise GenerationError(f"{label} must be an integer")
    if not 0 <= value <= MAX_GENERATION:
        raise GenerationError(f"{label} must be an unsigned 64-bit integer")
    return value


class TrustedGeneration:
    """In-memory model of state kept outside the installable image."""

    def __init__(self, minimum_accepted: int = 0) -> None:
        self._minimum_accepted = validate_generation(
            minimum_accepted, "minimum accepted generation"
        )

    @property
    def minimum_accepted(self) -> int:
        return self._minimum_accepted

    def authorize(self, generation: int) -> int:
        candidate = validate_generation(generation)
        if candidate < self._minimum_accepted:
            raise GenerationError(
                f"generation {candidate} is below trusted minimum "
                f"{self._minimum_accepted}"
            )
        return candidate

    def commit(self, generation: int) -> int:
        candidate = self.authorize(generation)
        if candidate > self._minimum_accepted:
            self._minimum_accepted = candidate
        return self._minimum_accepted
