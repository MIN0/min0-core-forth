"""Safe-runtime W^X image publication for MIN0 CORE FORTH (R0)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from min0_core_forth_dictionary import RuntimeDictionary
from min0_core_forth_image import (
    EXECUTION_PROFILE_SAFE_RUNTIME,
    ImageError,
    validate_image_envelope,
)
from min0_core_forth_outer import OuterInterpreter
from min0_core_forth_vm import MemoryRegion, Min0CoreForthVM, RegionMemory


class PublishError(ImageError):
    pass


@dataclass(frozen=True)
class PublishedRuntime:
    vm: Min0CoreForthVM
    dictionary: RuntimeDictionary
    outer: OuterInterpreter
    staging_memory: RegionMemory
    validation: dict


def _r0_layout(bases: Mapping[str, int], limits: Mapping[str, int]) -> int:
    if not (
        0 < bases["code"] < limits["code"] == bases["dictionary"]
        < limits["dictionary"] == bases["data"] < limits["data"]
    ):
        raise PublishError(
            "R0 publication requires contiguous CODE, DICTIONARY, and DATA limits"
        )
    return limits["data"]


def publish_runtime_image(
    components: Mapping[str, object],
    envelope: object,
    *,
    require_authentication: bool = False,
    minimum_generation: int = 0,
    trusted_public_keys: Mapping[str, object] | None = None,
    required_image_role: str | None = None,
) -> PublishedRuntime:
    """Validate in non-executable staging, copy to runtime, then seal CODE rx."""

    validation_options = {
        "require_authentication": require_authentication,
        "minimum_generation": minimum_generation,
        "trusted_public_keys": trusted_public_keys,
        "required_image_role": required_image_role,
        "runtime_profile": EXECUTION_PROFILE_SAFE_RUNTIME,
    }
    first = validate_image_envelope(components, envelope, **validation_options)
    bases = first["bases"]
    limits = first["limits"]
    memory_size = _r0_layout(bases, limits)

    staging = RegionMemory(
        memory_size,
        [
            MemoryRegion(
                "STAGING-CODE", bases["code"],
                limits["code"] - bases["code"], "rw",
            ),
            MemoryRegion(
                "STAGING-DICTIONARY", bases["dictionary"],
                limits["dictionary"] - bases["dictionary"], "rw",
            ),
            MemoryRegion(
                "STAGING-DATA", bases["data"],
                limits["data"] - bases["data"], "rw",
            ),
        ],
    )
    for section in ("code", "dictionary", "data"):
        staging.write(bases[section], first["components"][section])
    staged_components = {
        section: staging.read(bases[section], len(first["components"][section]))
        for section in ("code", "dictionary", "data")
    }
    validated = validate_image_envelope(
        staged_components, envelope, **validation_options
    )

    code_region = MemoryRegion(
        "CODE", 0, limits["code"], "rx", programmable=True
    )
    runtime_memory = RegionMemory(
        memory_size,
        [
            code_region,
            MemoryRegion(
                "DICTIONARY", bases["dictionary"],
                limits["dictionary"] - bases["dictionary"], "rw",
            ),
            MemoryRegion(
                "DATA", bases["data"],
                limits["data"] - bases["data"], "rw",
            ),
        ],
    )
    vm = Min0CoreForthVM(memory_size=memory_size, memory_bus=runtime_memory)
    vm.load(staged_components["code"], bases["code"])
    dictionary = RuntimeDictionary(
        vm,
        base=bases["dictionary"],
        limit=limits["dictionary"],
        body_base=bases["data"],
        body_limit=limits["data"],
    )
    allocator = validated["allocator"]
    dictionary.load_images(
        staged_components["dictionary"],
        latest=allocator["latest"],
        body_image=staged_components["data"],
    )
    outer = OuterInterpreter(vm, dictionary, code_base=allocator["code_here"])
    dictionary.seal_runtime_structure()
    vm.seal_verified_execution(
        validated["code_verification"],
        extra_entries=outer.execution_extra_entries(),
    )
    return PublishedRuntime(vm, dictionary, outer, staging, validated)
