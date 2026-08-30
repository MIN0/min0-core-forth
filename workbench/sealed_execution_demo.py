"""Demonstrate one-way W^X CODE sealing plus runtime boundary enforcement."""

from __future__ import annotations

import json

from constructor_relocation_demo import collect_dictionary_relocations
from min0_core_forth_dictionary import RuntimeDictionary
from min0_core_forth_image import build_image_envelope, validate_image_envelope
from min0_core_forth_linker import build_manifest
from min0_core_forth_outer import DEFAULT_CODE_BASE, OuterInterpreter, install_core_primitives
from min0_core_forth_vm import (
    ExecutionPolicyError,
    InvalidExecutionTarget,
    MemoryFault,
    MemoryRegion,
    Min0CoreForthVM,
    RegionMemory,
)


BASES = {"code": 0x1000, "dictionary": 0x4000, "data": 0x8000}
LIMITS = {"code": 0x4000, "dictionary": 0x8000, "data": 0x10000}


def _rejected(operation, errors) -> bool:
    try:
        operation()
    except errors:
        return True
    return False


def run_demo(implementation: str = "python") -> dict[str, object]:
    code_region = MemoryRegion("CODE", 0, 0x4000, "rwx", programmable=True)
    bus = RegionMemory(
        0x10000,
        [
            code_region,
            MemoryRegion("DICTIONARY", 0x4000, 0x4000, "rw"),
            MemoryRegion("DATA", 0x8000, 0x8000, "rw"),
        ],
    )
    vm = Min0CoreForthVM(memory_bus=bus)
    dictionary = RuntimeDictionary(
        vm, base=0x4000, limit=0x8000, body_base=0x8000, body_limit=0x10000
    )
    install_core_primitives(dictionary)
    outer = OuterInterpreter(vm, dictionary)
    outer.interpret(
        ": SAFE 0x25 ; : TARGET 7 ; "
        "DEFER ACTION ' TARGET IS ACTION : USE ACTION ; "
        "VARIABLE CELL : DATA-ROUNDTRIP 123 CELL ! CELL @ ; "
        ": CODE-WRITE 0x25 0x1000 ! ;"
    )
    safe = dictionary.find("SAFE")
    target = dictionary.find("TARGET")
    use = dictionary.find("USE")
    data_roundtrip = dictionary.find("DATA-ROUNDTRIP")
    code_write = dictionary.find("CODE-WRITE")
    assert all(item is not None for item in (safe, target, use, data_roundtrip, code_write))
    assert safe is not None and target is not None and use is not None
    assert data_roundtrip is not None and code_write is not None
    operand_address = safe.payload + 1
    outer.interpret(
        f": CORRUPT-TARGET 0x{operand_address:X} 0x{target.xt + 4:X} ! ;"
    )
    corrupt_target = dictionary.find("CORRUPT-TARGET")
    assert corrupt_target is not None

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
    envelope = build_image_envelope(
        components,
        BASES,
        LIMITS,
        allocator,
        build_manifest(records),
        generation=1,
    )
    validated = validate_image_envelope(components, envelope)
    verification = validated["code_verification"]
    before_permissions = code_region.permissions
    vm.seal_verified_execution(
        verification,
        extra_entries=outer.execution_extra_entries(),
    )

    safe_value = outer.execute(safe)[-1]
    vm.pop()
    data_value = outer.execute(data_roundtrip)[-1]
    vm.pop()
    defer_value = outer.execute(use)[-1]
    vm.pop()
    primitive_value = outer.interpret("2 3 +")[-1]
    vm.pop()

    code_before = vm.read_bytes(DEFAULT_CODE_BASE, 4)
    code_store_rejected = _rejected(
        lambda: outer.execute(code_write), (MemoryFault,)
    )
    direct_code_write_rejected = _rejected(
        lambda: vm.write_cell(DEFAULT_CODE_BASE, 0x25), (MemoryFault,)
    )
    loader_rewrite_rejected = _rejected(
        lambda: vm.load(b"\x00", DEFAULT_CODE_BASE), (MemoryFault,)
    )
    operand_entry_rejected = _rejected(
        lambda: vm.resume(
            operand_address,
            return_to=outer.return_trampoline,
        ),
        (InvalidExecutionTarget,),
    )

    outer.execute(corrupt_target)
    corrupted_payload = vm.read_cell(target.xt + 4)
    corrupted_indirect_rejected = _rejected(
        lambda: outer.execute(use), (InvalidExecutionTarget,)
    )
    data_execution_rejected = _rejected(
        lambda: vm.resume(dictionary.body_base),
        (InvalidExecutionTarget, MemoryFault),
    )
    reseal_rejected = _rejected(
        lambda: vm.seal_verified_execution(
            verification, extra_entries=outer.execution_extra_entries()
        ),
        (ExecutionPolicyError,),
    )
    clear_rejected = _rejected(lambda: bus.clear(), (MemoryFault,))
    flat_memory_seal_rejected = _rejected(
        lambda: Min0CoreForthVM().seal_verified_execution(verification),
        (ExecutionPolicyError,),
    )
    return {
        "implementation": implementation,
        "before_permissions": before_permissions,
        "after_permissions": code_region.permissions,
        "code_programmable_after_seal": code_region.programmable,
        "code_sealed": code_region.sealed,
        "verified_boundary_count": len(vm.verified_boundaries or ()),
        "values": {
            "literal_0x25": safe_value,
            "data_roundtrip": data_value,
            "defer_before_corruption": defer_value,
            "primitive_after_seal": primitive_value,
        },
        "corrupted_target_payload": corrupted_payload,
        "operand_address": operand_address,
        "code_unchanged": vm.read_bytes(DEFAULT_CODE_BASE, 4) == code_before,
        "rejected": {
            "forth_store_to_code": code_store_rejected,
            "direct_code_write": direct_code_write_rejected,
            "loader_rewrite_after_seal": loader_rewrite_rejected,
            "resume_into_operand": operand_entry_rejected,
            "corrupted_indirect_target": corrupted_indirect_rejected,
            "execute_data": data_execution_rejected,
            "second_seal": reseal_rejected,
            "clear_sealed_code": clear_rejected,
            "flat_memory_cannot_seal": flat_memory_seal_rejected,
        },
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), sort_keys=True, separators=(",", ":")))
