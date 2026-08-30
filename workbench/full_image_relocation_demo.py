"""Relocate and execute a mixed CODE/DICTIONARY/DATA image."""

from __future__ import annotations

import json

from code_relocation_demo import SOURCE
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
from min0_core_forth_vm import Min0CoreForthVM, MemoryRegion, RegionMemory


def run_demo(implementation: str = "python") -> dict:
    vm, dictionary = make_system()
    install_core_primitives(dictionary)
    outer = OuterInterpreter(vm, dictionary)
    outer.interpret(SOURCE)

    code_records = outer.relocation_manifest()
    dictionary_records = collect_dictionary_relocations(vm, dictionary)
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
    components = {
        "code": vm.read_bytes(
            DEFAULT_CODE_BASE, outer.code_here - DEFAULT_CODE_BASE
        ),
        "dictionary": dictionary.image(),
        "data": dictionary.body_image(),
    }
    manifest = build_manifest(code_records + dictionary_records)
    linked = link_components(components, source_bases, target_bases, manifest)

    bus = RegionMemory(
        0x11000,
        [
            MemoryRegion("CODE", 0, 0x5000, "rwx", programmable=True),
            MemoryRegion("DICTIONARY", 0x5000, 0x4000, "rw"),
            MemoryRegion("DATA", 0x9000, 0x8000, "rw"),
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
    moved_outer = OuterInterpreter(
        moved_vm, moved_dictionary, code_base=NEW_CODE_BASE + len(linked["code"])
    )
    stack = moved_outer.interpret(
        "0 CHOOSE 1 CHOOSE 0 SPIN SUM SKIP STEP READ-ANSWER SLOT-ADDR"
    )
    answer = moved_dictionary.find("ANSWER")
    slot = moved_dictionary.find("SLOT")
    assert answer is not None and slot is not None
    answer_body, answer_behavior = moved_dictionary.read_does_descriptor(answer)
    return {
        "implementation": implementation,
        "source_bases": [DEFAULT_CODE_BASE, dictionary.base, dictionary.body_base],
        "moved_bases": [NEW_CODE_BASE, NEW_DICTIONARY_BASE, NEW_DATA_BASE],
        "manifest_records": len(manifest["records"]),
        "code_relocations": len(code_records),
        "dictionary_relocations": len(dictionary_records),
        "code_targets": {
            target: sum(record["target"] == target for record in code_records)
            for target in ("code", "dictionary", "data")
        },
        "dictionary_targets": {
            target: sum(record["target"] == target for record in dictionary_records)
            for target in ("code", "dictionary", "data")
        },
        "stack": stack,
        "slot": slot.payload,
        "answer_body": answer_body,
        "answer_behavior": answer_behavior,
        "answer_value": moved_vm.read_cell(answer_body),
        "code_here": NEW_CODE_BASE + len(linked["code"]),
        "header_here": moved_dictionary.here,
        "data_here": moved_dictionary.data_here,
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), sort_keys=True, separators=(",", ":")))
