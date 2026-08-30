"""Demonstrate sealed dictionary structure with a narrow Monitor DEFER gate."""

from __future__ import annotations

import json

from constructor_image_fixture import make_system
from constructor_relocation_demo import collect_dictionary_relocations
from min0_core_forth_control import (
    PROFILE_MONITOR,
    PROFILE_OBSERVER,
    ControlAuthorizationError,
    MonitorControlAuthority,
)
from min0_core_forth_dictionary import DictionaryError, RuntimeDictionary
from min0_core_forth_image import build_image_envelope
from min0_core_forth_linker import build_manifest
from min0_core_forth_outer import DEFAULT_CODE_BASE, OuterInterpreter, install_core_primitives
from min0_core_forth_publish import publish_runtime_image
from min0_core_forth_vm import MemoryFault, Min0CoreForthVM


BASES = {"code": 0x1000, "dictionary": 0x4000, "data": 0x8000}
LIMITS = {"code": 0x4000, "dictionary": 0x8000, "data": 0x10000}
SOURCE = (
    ": TARGET-A 7 ; : TARGET-B 9 ; "
    "DEFER ACTION ' TARGET-A IS ACTION : USE ACTION ; VARIABLE CELL"
)


def _rejected(operation, errors) -> bool:
    try:
        operation()
    except errors:
        return True
    return False


def _build_image() -> tuple[dict[str, bytes], dict]:
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
    envelope = build_image_envelope(
        components, BASES, LIMITS, allocator, build_manifest(records), generation=1
    )
    return components, envelope


def run_demo(implementation: str = "python") -> dict[str, object]:
    components, envelope = _build_image()
    published = publish_runtime_image(components, envelope)
    vm = published.vm
    dictionary = published.dictionary
    outer = published.outer
    dictionary_region = next(
        region for region in vm.memory.regions if region.name == "DICTIONARY"
    )
    action = dictionary.find("ACTION")
    target_b = dictionary.find("TARGET-B")
    cell_word = dictionary.find("CELL")
    use = dictionary.find("USE")
    assert action is not None and target_b is not None and cell_word is not None and use is not None

    data_value = outer.interpret("123 CELL ! CELL @")[-1]
    vm.data_stack.clear()
    dictionary_before_attacks = dictionary.image()
    raw_header_store_rejected = _rejected(
        lambda: outer.interpret(f"0 0x{dictionary.latest:X} !"), (MemoryFault,)
    )
    vm.data_stack.clear()
    raw_defer_store_rejected = _rejected(
        lambda: outer.interpret(f"0 0x{action.xt + 4:X} !"), (MemoryFault,)
    )
    vm.data_stack.clear()
    definition_rejected = _rejected(
        lambda: outer.interpret(": INTRUDER 1 ;"), (DictionaryError,)
    )
    allocator_rejected = _rejected(
        lambda: outer.interpret("1 ,"), (DictionaryError,)
    )
    vm.data_stack.clear()
    ordinary_is_rejected = _rejected(
        lambda: outer.interpret("' TARGET-B IS ACTION"), (DictionaryError,)
    )
    vm.data_stack.clear()
    loader_program_rejected = _rejected(
        lambda: vm.load(b"\x00", dictionary.latest), (MemoryFault,)
    )
    second_structure_seal_rejected = _rejected(
        dictionary.seal_runtime_structure, (DictionaryError,)
    )
    flat_dictionary = RuntimeDictionary(Min0CoreForthVM())
    flat_memory_seal_rejected = _rejected(
        flat_dictionary.seal_runtime_structure, (DictionaryError,)
    )
    forged_scope_rejected = _rejected(
        lambda: vm.memory.authorized_writes("DICTIONARY", object()).__enter__(),
        (MemoryFault,),
    )
    attacks_left_dictionary_unchanged = dictionary.image() == dictionary_before_attacks

    vm.reset(clear_memory=False)
    authority = MonitorControlAuthority(vm, dictionary)
    observer = authority.issue(PROFILE_OBSERVER)
    monitor = authority.issue(PROFILE_MONITOR)
    observer_switch_rejected = _rejected(
        lambda: observer.switch_defer("ACTION", "TARGET-B"),
        (ControlAuthorizationError,),
    )
    audit = monitor.switch_defer("ACTION", "TARGET-B")
    defer_value = outer.execute(use)[-1]
    vm.pop()

    dictionary_after_monitor = dictionary.image()
    changed_offsets = [
        index
        for index, (before, after) in enumerate(
            zip(dictionary_before_attacks, dictionary_after_monitor)
        )
        if before != after
    ]
    defer_offset = action.xt + 4 - dictionary.base
    monitor_changed_only_defer_slot = bool(changed_offsets) and all(
        defer_offset <= offset < defer_offset + 4 for offset in changed_offsets
    )
    return {
        "implementation": implementation,
        "dictionary_permissions": dictionary_region.permissions,
        "dictionary_write_protected": dictionary_region.write_protected,
        "runtime_structure_sealed": dictionary.runtime_structure_sealed,
        "data_value": data_value,
        "defer_value_after_monitor": defer_value,
        "monitor_audit_operation": audit["operation"],
        "attacks_left_dictionary_unchanged": attacks_left_dictionary_unchanged,
        "monitor_changed_only_defer_slot": monitor_changed_only_defer_slot,
        "rejected": {
            "raw_header_store": raw_header_store_rejected,
            "raw_defer_store": raw_defer_store_rejected,
            "new_definition": definition_rejected,
            "allocator_comma": allocator_rejected,
            "ordinary_is": ordinary_is_rejected,
            "loader_program": loader_program_rejected,
            "second_structure_seal": second_structure_seal_rejected,
            "flat_memory_seal": flat_memory_seal_rejected,
            "forged_write_scope": forged_scope_rejected,
            "observer_switch": observer_switch_rejected,
        },
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), sort_keys=True, separators=(",", ":")))
