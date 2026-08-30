"""Exercise successful and rejected transactional linker operations."""

from __future__ import annotations

import copy
import json

from min0_core_forth_linker import LinkError, build_manifest, link_components


def make_fixture() -> tuple[dict, dict, dict, dict]:
    components = {
        "code": (
            (0x1004).to_bytes(4, "little")
            + (0x3000).to_bytes(4, "little")
            + (0xDEADBEEF).to_bytes(4, "little")
        ),
        "dictionary": (0x1000).to_bytes(4, "little"),
        "data": (0x11223344).to_bytes(4, "little"),
    }
    source_bases = {"code": 0x1000, "dictionary": 0x2000, "data": 0x3000}
    target_bases = {"code": 0x4000, "dictionary": 0x5000, "data": 0x6000}
    manifest = build_manifest(
        [
            {"section": "code", "offset": 0, "target": "code", "width": 4, "kind": "call"},
            {"section": "code", "offset": 4, "target": "data", "width": 4, "kind": "data-literal"},
            {
                "section": "dictionary",
                "offset": 0,
                "target": "code",
                "width": 4,
                "kind": "colon-code",
            },
        ]
    )
    return components, source_bases, target_bases, manifest


def _rejected(name: str, mutate) -> str:
    components, source_bases, target_bases, manifest = make_fixture()
    mutate(components, source_bases, target_bases, manifest)
    before_components = copy.deepcopy(components)
    before_manifest = copy.deepcopy(manifest)
    try:
        link_components(components, source_bases, target_bases, manifest)
    except LinkError:
        if components != before_components or manifest != before_manifest:
            raise AssertionError(f"{name} mutated its inputs")
        return name
    raise AssertionError(f"{name} was accepted")


def run_demo(implementation: str = "python") -> dict:
    components, source_bases, target_bases, manifest = make_fixture()
    before = copy.deepcopy(components)
    linked = link_components(components, source_bases, target_bases, manifest)
    if components != before:
        raise AssertionError("successful link mutated source components")

    rejected = [
        _rejected("version", lambda _c, _s, _t, m: m.update(version=2)),
        _rejected(
            "section",
            lambda _c, _s, _t, m: m["records"][0].update(section="unknown"),
        ),
        _rejected(
            "width", lambda _c, _s, _t, m: m["records"][0].update(width=8)
        ),
        _rejected(
            "offset", lambda _c, _s, _t, m: m["records"][0].update(offset=99)
        ),
        _rejected(
            "overlap",
            lambda _c, _s, _t, m: m["records"].append(
                {"section": "code", "offset": 2, "target": "code", "width": 4, "kind": "overlap"}
            ),
        ),
        _rejected(
            "pointer",
            lambda c, _s, _t, _m: c.update(
                code=(0).to_bytes(4, "little") + c["code"][4:]
            ),
        ),
        _rejected(
            "target-overlap",
            lambda _c, _s, t, _m: t.update(dictionary=0x4008),
        ),
        _rejected(
            "overflow", lambda _c, _s, t, _m: t.update(code=0xFFFFFFFC)
        ),
        _rejected(
            "kind", lambda _c, _s, _t, m: m["records"][0].update(kind="")
        ),
    ]
    return {
        "implementation": implementation,
        "record_count": len(manifest["records"]),
        "source_unchanged": components == before,
        "code_hex": linked["code"].hex(),
        "dictionary_hex": linked["dictionary"].hex(),
        "data_hex": linked["data"].hex(),
        "rejected": rejected,
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), sort_keys=True, separators=(",", ":")))
