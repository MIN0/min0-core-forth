"""Validated copy-on-success relocation linker for MIN0 CORE FORTH R0 images."""

from __future__ import annotations

from collections.abc import Mapping


MANIFEST_FORMAT = "min0-core-forth-relocation-manifest"
MANIFEST_VERSION = 1
MANIFEST_PROFILE = "reference32-le"
SECTIONS = ("code", "dictionary", "data")
REFERENCE32_LIMIT = 1 << 32


class LinkError(ValueError):
    pass


def build_manifest(records: list[dict[str, str | int]]) -> dict:
    """Build the current in-memory manifest envelope without freezing a file format."""

    return {
        "format": MANIFEST_FORMAT,
        "version": MANIFEST_VERSION,
        "profile": MANIFEST_PROFILE,
        "records": [dict(record) for record in records],
    }


def _integer(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise LinkError(f"{label} must be an integer")
    return value


def _normalize_components(components: Mapping[str, object]) -> dict[str, bytes]:
    if not isinstance(components, Mapping):
        raise LinkError("components must be a mapping")
    result: dict[str, bytes] = {}
    for section in SECTIONS:
        value = components.get(section)
        if not isinstance(value, (bytes, bytearray, memoryview)):
            raise LinkError(f"component {section} must be bytes")
        result[section] = bytes(value)
    return result


def _normalize_bases(bases: Mapping[str, object], label: str) -> dict[str, int]:
    if not isinstance(bases, Mapping):
        raise LinkError(f"{label} bases must be a mapping")
    result: dict[str, int] = {}
    for section in SECTIONS:
        base = _integer(bases.get(section), f"{label} base {section}")
        if base < 0 or base >= REFERENCE32_LIMIT:
            raise LinkError(f"{label} base {section} is outside Reference32")
        result[section] = base
    return result


def _validate_ranges(
    components: dict[str, bytes], bases: dict[str, int], label: str
) -> None:
    ranges: list[tuple[int, int, str]] = []
    for section in SECTIONS:
        start = bases[section]
        end = start + len(components[section])
        if end > REFERENCE32_LIMIT:
            raise LinkError(f"{label} component {section} exceeds Reference32")
        if end > start:
            ranges.append((start, end, section))
    ranges.sort()
    for previous, current in zip(ranges, ranges[1:]):
        if current[0] < previous[1]:
            raise LinkError(
                f"{label} components {previous[2]} and {current[2]} overlap"
            )


def link_components(
    components: Mapping[str, object],
    source_bases: Mapping[str, object],
    target_bases: Mapping[str, object],
    manifest: object,
) -> dict[str, bytes]:
    """Validate every record, then patch private copies and return them."""

    images = _normalize_components(components)
    old_bases = _normalize_bases(source_bases, "source")
    new_bases = _normalize_bases(target_bases, "target")
    _validate_ranges(images, old_bases, "source")
    _validate_ranges(images, new_bases, "target")
    if not isinstance(manifest, Mapping):
        raise LinkError("manifest must be a mapping")
    if set(manifest) != {"format", "version", "profile", "records"}:
        raise LinkError("relocation manifest fields are malformed")
    if manifest.get("format") != MANIFEST_FORMAT:
        raise LinkError("unsupported relocation manifest format")
    if _integer(manifest.get("version"), "manifest version") != MANIFEST_VERSION:
        raise LinkError("unsupported relocation manifest version")
    if manifest.get("profile") != MANIFEST_PROFILE:
        raise LinkError("unsupported relocation manifest profile")
    records = manifest.get("records")
    if not isinstance(records, list):
        raise LinkError("manifest records must be a list")

    occupied: dict[str, list[tuple[int, int]]] = {section: [] for section in SECTIONS}
    patches: list[tuple[str, int, int]] = []
    for index, record in enumerate(records):
        prefix = f"relocation record {index}"
        if not isinstance(record, Mapping):
            raise LinkError(f"{prefix} must be a mapping")
        if set(record) != {"section", "offset", "target", "width", "kind"}:
            raise LinkError(f"{prefix} fields are malformed")
        section = record.get("section")
        target = record.get("target")
        if section not in SECTIONS:
            raise LinkError(f"{prefix} has unknown patch section")
        if target not in SECTIONS:
            raise LinkError(f"{prefix} has unknown target section")
        offset = _integer(record.get("offset"), f"{prefix} offset")
        width = _integer(record.get("width"), f"{prefix} width")
        kind = record.get("kind")
        if not isinstance(kind, str) or not kind:
            raise LinkError(f"{prefix} kind must be a nonempty string")
        if width != 4:
            raise LinkError(f"{prefix} width is unsupported for Reference32")
        if offset < 0 or offset + width > len(images[section]):
            raise LinkError(f"{prefix} patch is outside its component")
        if section == "dictionary" and (old_bases[section] + offset) % 4:
            raise LinkError(f"{prefix} dictionary patch is not cell-aligned")
        interval = (offset, offset + width)
        if any(interval[0] < end and start < interval[1] for start, end in occupied[section]):
            raise LinkError(f"{prefix} overlaps another patch")
        occupied[section].append(interval)

        old_value = int.from_bytes(
            images[section][offset : offset + width], "little", signed=False
        )
        target_start = old_bases[target]
        target_end = target_start + len(images[target])
        in_source = (
            target_start <= old_value <= target_end
            if target == "data"
            else target_start <= old_value < target_end
        )
        if not in_source:
            raise LinkError(f"{prefix} value is outside its source target component")
        new_value = old_value + new_bases[target] - old_bases[target]
        if new_value < 0 or new_value >= REFERENCE32_LIMIT:
            raise LinkError(f"{prefix} result is outside Reference32")
        moved_end = new_bases[target] + len(images[target])
        in_target = (
            new_bases[target] <= new_value <= moved_end
            if target == "data"
            else new_bases[target] <= new_value < moved_end
        )
        if not in_target:
            raise LinkError(f"{prefix} result is outside its target component")
        patches.append((section, offset, new_value))

    result = {section: bytearray(image) for section, image in images.items()}
    for section, offset, value in patches:
        result[section][offset : offset + 4] = value.to_bytes(4, "little")
    return {section: bytes(image) for section, image in result.items()}
