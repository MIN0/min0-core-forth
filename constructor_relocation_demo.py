"""Relocate typed constructor metadata to a different three-region map."""

from __future__ import annotations

import hashlib
import json

from constructor_image_fixture import build_envelope, make_system
from min0_core_forth_dictionary import (
    KIND_COLON,
    KIND_CREATED,
    KIND_DEFER,
    KIND_DEFINER,
    KIND_DOES,
    KIND_VARIABLE,
    RuntimeDictionary,
)
from min0_core_forth_outer import OuterInterpreter
from min0_core_forth_vm import Min0CoreForthVM, MemoryRegion, RegionMemory


NEW_CODE_BASE = 0x2000
NEW_DICTIONARY_BASE = 0x5000
NEW_DATA_BASE = 0x9000


def collect_dictionary_relocations(vm, dictionary) -> list[dict[str, int | str]]:
    records: list[dict[str, int | str]] = []

    def add(cell_address: int, target: str, kind: str) -> None:
        records.append(
            {
                "section": "dictionary",
                "offset": cell_address - dictionary.base,
                "target": target,
                "width": 4,
                "kind": kind,
            }
        )

    for entry in dictionary.entries():
        if entry.link:
            add(entry.header_address, "dictionary", "dictionary-link")
        if entry.kind == KIND_COLON:
            add(entry.xt + 4, "code", "colon-code")
        elif entry.kind in (KIND_VARIABLE, KIND_CREATED):
            add(entry.xt + 4, "data", "data-body")
        elif entry.kind == KIND_DEFER:
            if entry.payload:
                add(entry.xt + 4, "dictionary", "defer-target-xt")
        elif entry.kind in (KIND_DOES, KIND_DEFINER):
            add(entry.xt + 4, "dictionary", "descriptor")

        if entry.kind == KIND_DOES:
            descriptor = entry.payload
            add(descriptor, "data", "does-body")
            add(descriptor + 4, "code", "does-behavior")
        elif entry.kind == KIND_DEFINER:
            descriptor = entry.payload
            plan, behavior = dictionary.read_definer_descriptor(entry)
            add(descriptor, "dictionary", "constructor-plan")
            if behavior:
                add(descriptor + 4, "code", "definer-behavior")
            count = vm.read_cell(plan + 8)
            for index in range(count):
                add(plan + 12 + index * 8, "code", "constructor-segment")

    return sorted(records, key=lambda record: int(record["offset"]))


def run_demo(implementation: str = "python") -> dict:
    envelope = build_envelope()
    vm, dictionary = make_system()
    vm.load(bytes.fromhex(envelope["code_hex"]), envelope["code_base"])
    dictionary.load_images(
        bytes.fromhex(envelope["dictionary_hex"]),
        latest=envelope["latest"],
        body_image=bytes.fromhex(envelope["body_hex"]),
    )
    records = collect_dictionary_relocations(vm, dictionary)
    deltas = {
        "code": NEW_CODE_BASE - envelope["code_base"],
        "dictionary": NEW_DICTIONARY_BASE - envelope["dictionary_base"],
        "data": NEW_DATA_BASE - envelope["body_base"],
    }
    headers = bytearray.fromhex(envelope["dictionary_hex"])
    for record in records:
        offset = int(record["offset"])
        old_value = int.from_bytes(headers[offset : offset + 4], "little")
        new_value = old_value + deltas[str(record["target"])]
        headers[offset : offset + 4] = new_value.to_bytes(4, "little")

    bus = RegionMemory(
        0x11000,
        [
            MemoryRegion("CODE", 0, 0x5000, "rwx", programmable=True),
            MemoryRegion("DICTIONARY", 0x5000, 0x4000, "rw"),
            MemoryRegion("DATA", 0x9000, 0x8000, "rw"),
        ],
    )
    moved_vm = Min0CoreForthVM(memory_size=0x11000, memory_bus=bus)
    code = bytes.fromhex(envelope["code_hex"])
    moved_vm.load(code, NEW_CODE_BASE)
    moved_dictionary = RuntimeDictionary(
        moved_vm,
        base=NEW_DICTIONARY_BASE,
        limit=NEW_DATA_BASE,
        body_base=NEW_DATA_BASE,
        body_limit=0x11000,
    )
    moved_latest = envelope["latest"] + deltas["dictionary"]
    moved_dictionary.load_images(headers, latest=moved_latest)
    moved_code_here = NEW_CODE_BASE + len(code)
    moved_outer = OuterInterpreter(
        moved_vm, moved_dictionary, code_base=moved_code_here
    )
    stack = moved_outer.interpret("2 0x1AB RECORD: ITEM ITEM")
    record = moved_dictionary.find("RECORD:")
    item = moved_dictionary.find("ITEM")
    assert record is not None and item is not None
    plan, _behavior = moved_dictionary.read_definer_descriptor(record)
    actions = [
        action for _code, action in moved_dictionary.read_constructor_plan(record)
    ]
    canonical_manifest = ";".join(
        f"{record['offset']}:{record['target']}" for record in records
    )
    target_counts = {
        target: sum(record["target"] == target for record in records)
        for target in ("code", "dictionary", "data")
    }
    return {
        "implementation": implementation,
        "source_bases": [
            envelope["code_base"],
            envelope["dictionary_base"],
            envelope["body_base"],
        ],
        "moved_bases": [NEW_CODE_BASE, NEW_DICTIONARY_BASE, NEW_DATA_BASE],
        "deltas": [deltas["code"], deltas["dictionary"], deltas["data"]],
        "relocation_count": len(records),
        "target_counts": target_counts,
        "manifest_sha256": hashlib.sha256(canonical_manifest.encode()).hexdigest(),
        "plan": plan,
        "actions": actions,
        "stack": stack,
        "item_body": item.payload,
        "body_hex": moved_vm.read_bytes(item.payload, 4).hex(),
        "data_here": moved_dictionary.data_here,
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), sort_keys=True))
