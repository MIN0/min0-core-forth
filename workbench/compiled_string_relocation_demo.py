"""Relocate a compiled S-quote literal and execute it from read-only DATA."""

from __future__ import annotations

import json

from constructor_image_fixture import make_system
from constructor_relocation_demo import (
    NEW_CODE_BASE,
    NEW_DATA_BASE,
    NEW_DICTIONARY_BASE,
    collect_dictionary_relocations,
)
from min0_core_forth_dictionary import RuntimeDictionary
from min0_core_forth_linker import build_manifest, link_components
from min0_core_forth_outer import DEFAULT_CODE_BASE, OuterInterpreter, install_core_primitives
from min0_core_forth_vm import MemoryFault, MemoryRegion, Min0CoreForthVM, RegionMemory


def run_demo(implementation: str = "python") -> dict[str, object]:
    vm, dictionary = make_system()
    install_core_primitives(dictionary)
    outer = OuterInterpreter(vm, dictionary)
    outer.interpret(': MESSAGE S" Relocated" ;')

    string_record = next(
        record
        for record in outer.relocation_manifest()
        if record["kind"] == "string-address"
    )
    records = outer.relocation_manifest() + collect_dictionary_relocations(vm, dictionary)
    components = {
        "code": vm.read_bytes(DEFAULT_CODE_BASE, outer.code_here - DEFAULT_CODE_BASE),
        "dictionary": dictionary.image(),
        "data": dictionary.body_image(),
    }
    source_bases = {
        "code": DEFAULT_CODE_BASE,
        "dictionary": dictionary.base,
        "data": dictionary.body_base,
    }
    target_bases = {
        "code": NEW_CODE_BASE,
        "dictionary": NEW_DICTIONARY_BASE,
        "data": NEW_DATA_BASE,
    }
    linked = link_components(
        components, source_bases, target_bases, build_manifest(records)
    )

    data_region = MemoryRegion("DATA", NEW_DATA_BASE, 0x8000, "rw")
    bus = RegionMemory(
        0x11000,
        [
            MemoryRegion("CODE", 0, 0x5000, "rwx", programmable=True),
            MemoryRegion("DICTIONARY", NEW_DICTIONARY_BASE, 0x4000, "rw"),
            data_region,
        ],
    )
    moved_vm = Min0CoreForthVM(memory_size=0x11000, memory_bus=bus)
    moved_vm.load(linked["code"], NEW_CODE_BASE)
    moved_dictionary = RuntimeDictionary(
        moved_vm,
        base=NEW_DICTIONARY_BASE,
        limit=NEW_DATA_BASE,
        body_base=NEW_DATA_BASE,
        body_limit=0x11000,
    )
    moved_dictionary.load_images(
        linked["dictionary"],
        latest=dictionary.latest + NEW_DICTIONARY_BASE - dictionary.base,
        body_image=linked["data"],
    )
    bus.seal_read_only_region("DATA")
    moved_outer = OuterInterpreter(
        moved_vm,
        moved_dictionary,
        code_base=NEW_CODE_BASE + len(linked["code"]),
    )
    stack = moved_outer.interpret("MESSAGE")
    address, length = stack
    raw = moved_vm.read_bytes(address, length)
    moved_outer.interpret("TYPE")

    rejected: dict[str, bool] = {}
    for name, operation in {
        "write": lambda: moved_vm.write_u8(address, 0),
        "program": lambda: bus.program(address, b"X"),
        "clear": bus.clear,
    }.items():
        try:
            operation()
        except MemoryFault:
            rejected[name] = True
        else:
            rejected[name] = False

    return {
        "implementation": implementation,
        "relocation": string_record,
        "source_data_base": dictionary.body_base,
        "moved_data_base": NEW_DATA_BASE,
        "address": address,
        "length": length,
        "text_hex": raw.hex(),
        "terminal_text": moved_outer.terminal_text,
        "data_permissions": data_region.permissions,
        "read_only_sealed": data_region.read_only_sealed,
        "rejected": rejected,
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), sort_keys=True, separators=(",", ":")))
