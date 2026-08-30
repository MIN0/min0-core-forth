"""Demonstrate non-executable staging to sealed executable publication."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from image_envelope_demo import build_source_image
from min0_core_forth_image import ImageError
from min0_core_forth_publish import publish_runtime_image
from min0_core_forth_vm import MemoryFault


def _rejected(operation, errors) -> bool:
    try:
        operation()
    except errors:
        return True
    return False


def run_demo(implementation: str = "python") -> dict[str, object]:
    components, envelope = build_source_image()
    published = publish_runtime_image(components, envelope)
    bases = published.validation["bases"]
    code_base = bases["code"]
    code_region = next(
        region for region in published.vm.memory.regions if region.name == "CODE"
    )
    staging_code = next(
        region
        for region in published.staging_memory.regions
        if region.name == "STAGING-CODE"
    )

    staging_execution_rejected = _rejected(
        lambda: published.staging_memory.check_fetch(code_base, 1), (MemoryFault,)
    )
    runtime_before = published.vm.read_bytes(code_base, len(components["code"]))
    published.staging_memory.write(code_base, b"\xFF")
    staging_changed = published.staging_memory.read_u8(code_base) == 0xFF
    runtime_unchanged = (
        published.vm.read_bytes(code_base, len(components["code"])) == runtime_before
    )
    stack = published.outer.interpret("READ-ANSWER 2 3 +")

    runtime_write_rejected = _rejected(
        lambda: published.vm.write_u8(code_base, 0), (MemoryFault,)
    )
    runtime_reprogram_rejected = _rejected(
        lambda: published.vm.load(b"\x00", code_base), (MemoryFault,)
    )
    tampered = dict(components)
    changed_code = bytearray(components["code"])
    changed_code[0] ^= 0xFF
    tampered["code"] = bytes(changed_code)
    tampered_before_publish_rejected = _rejected(
        lambda: publish_runtime_image(tampered, envelope), (ImageError,)
    )
    return {
        "implementation": implementation,
        "staging_permissions": staging_code.permissions,
        "runtime_permissions": code_region.permissions,
        "runtime_programmable": code_region.programmable,
        "runtime_sealed": code_region.sealed,
        "stack": stack,
        "staging_changed_after_publish": staging_changed,
        "runtime_unchanged_after_staging_change": runtime_unchanged,
        "rejected": {
            "execute_staging": staging_execution_rejected,
            "write_runtime_code": runtime_write_rejected,
            "reprogram_runtime_code": runtime_reprogram_rejected,
            "tampered_before_publish": tampered_before_publish_rejected,
        },
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), sort_keys=True, separators=(",", ":")))
