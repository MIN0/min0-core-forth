"""Bind a real executable image, allocator metadata, and manifest by digest."""

from __future__ import annotations

import copy
import json

from code_relocation_demo import SOURCE
from constructor_image_fixture import make_system
from constructor_relocation_demo import collect_dictionary_relocations
from min0_core_forth_dictionary import RuntimeDictionary
from min0_core_forth_image import (
    ImageAuthenticationError,
    ImageError,
    build_image_envelope,
    link_image_envelope,
    validate_image_envelope,
)
from min0_core_forth_linker import build_manifest
from min0_core_forth_outer import DEFAULT_CODE_BASE, OuterInterpreter, install_core_primitives
from min0_core_forth_vm import Min0CoreForthVM, MemoryRegion, RegionMemory


SOURCE_BASES = {"code": 0x1000, "dictionary": 0x4000, "data": 0x8000}
SOURCE_LIMITS = {"code": 0x4000, "dictionary": 0x8000, "data": 0x10000}
TARGET_BASES = {"code": 0x2000, "dictionary": 0x5000, "data": 0x9000}
TARGET_LIMITS = {"code": 0x5000, "dictionary": 0x9000, "data": 0x11000}
SOURCE_GENERATION = 7


def build_source_image(generation: int = SOURCE_GENERATION) -> tuple[dict[str, bytes], dict]:
    vm, dictionary = make_system()
    install_core_primitives(dictionary)
    outer = OuterInterpreter(vm, dictionary)
    outer.interpret(SOURCE)
    components = {
        "code": vm.read_bytes(DEFAULT_CODE_BASE, outer.code_here - DEFAULT_CODE_BASE),
        "dictionary": dictionary.image(),
        "data": dictionary.body_image(),
    }
    allocator = {
        "code_here": outer.code_here,
        "header_here": dictionary.here,
        "data_here": dictionary.data_here,
        "latest": dictionary.latest,
    }
    records = outer.relocation_manifest() + collect_dictionary_relocations(vm, dictionary)
    manifest = build_manifest(records)
    envelope = build_image_envelope(
        components,
        SOURCE_BASES,
        SOURCE_LIMITS,
        allocator,
        manifest,
        generation=generation,
    )
    return components, envelope


def _expect_rejection(name: str, operation) -> str:
    try:
        operation()
    except (ImageError, ImageAuthenticationError):
        return name
    raise AssertionError(f"{name} was accepted")


def run_demo(implementation: str = "python") -> dict:
    components, envelope = build_source_image()
    validate_image_envelope(components, envelope)
    linked, linked_envelope = link_image_envelope(
        components, envelope, TARGET_BASES, TARGET_LIMITS
    )

    bus = RegionMemory(
        0x11000,
        [
            MemoryRegion("CODE", 0, 0x5000, "rwx", programmable=True),
            MemoryRegion("DICTIONARY", 0x5000, 0x4000, "rw"),
            MemoryRegion("DATA", 0x9000, 0x8000, "rw"),
        ],
    )
    moved_vm = Min0CoreForthVM(memory_size=0x11000, memory_bus=bus)
    moved_vm.load(linked["code"], TARGET_BASES["code"])
    moved_dictionary = RuntimeDictionary(
        moved_vm,
        base=TARGET_BASES["dictionary"],
        limit=TARGET_LIMITS["dictionary"],
        body_base=TARGET_BASES["data"],
        body_limit=TARGET_LIMITS["data"],
    )
    moved_allocator = linked_envelope["allocator"]
    moved_dictionary.load_images(
        linked["dictionary"],
        latest=moved_allocator["latest"],
        body_image=linked["data"],
    )
    moved_outer = OuterInterpreter(
        moved_vm, moved_dictionary, code_base=moved_allocator["code_here"]
    )
    stack = moved_outer.interpret(
        "0 CHOOSE 1 CHOOSE 0 SPIN SUM SKIP STEP READ-ANSWER SLOT-ADDR"
    )

    different_components = dict(components)
    changed_code = bytearray(different_components["code"])
    changed_code[-1] = 0  # Valid NOP; keep the alternate image structurally decodable.
    different_components["code"] = bytes(changed_code)
    different_envelope = build_image_envelope(
        different_components,
        SOURCE_BASES,
        SOURCE_LIMITS,
        envelope["allocator"],
        envelope["manifest"],
        generation=envelope["generation"],
    )
    allocator_tamper = copy.deepcopy(envelope)
    allocator_tamper["allocator"]["latest"] -= 4
    manifest_tamper = copy.deepcopy(envelope)
    manifest_tamper["manifest"]["records"][0]["kind"] += "-changed"
    rejected = [
        _expect_rejection(
            "different-image", lambda: validate_image_envelope(different_components, envelope)
        ),
        _expect_rejection(
            "different-envelope", lambda: validate_image_envelope(components, different_envelope)
        ),
        _expect_rejection(
            "allocator-metadata", lambda: validate_image_envelope(components, allocator_tamper)
        ),
        _expect_rejection(
            "manifest-digest", lambda: validate_image_envelope(components, manifest_tamper)
        ),
        _expect_rejection(
            "authentication-required",
            lambda: validate_image_envelope(
                components, envelope, require_authentication=True
            ),
        ),
    ]
    return {
        "implementation": implementation,
        "record_count": len(envelope["manifest"]["records"]),
        "source_identity": envelope["identity_sha256"],
        "linked_identity": linked_envelope["identity_sha256"],
        "different_identity": different_envelope["identity_sha256"],
        "identity_changed": envelope["identity_sha256"] != linked_envelope["identity_sha256"],
        "authentication": envelope["authentication"]["scheme"],
        "generation": envelope["generation"],
        "linked_generation": linked_envelope["generation"],
        "source_allocator": envelope["allocator"],
        "linked_allocator": linked_envelope["allocator"],
        "stack": stack,
        "rejected": rejected,
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), sort_keys=True, separators=(",", ":")))
