"""Build the canonical dictionary fixture used for cross-language checks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from min0_core_forth_dictionary import RuntimeDictionary
from min0_core_forth_vm import Min0CoreForthVM, Op


def build_fixture() -> tuple[RuntimeDictionary, list[dict[str, int | str | bool]]]:
    vm = Min0CoreForthVM()
    dictionary = RuntimeDictionary(vm)
    dictionary.add_primitive("DUP", Op.DUP)
    dictionary.add_primitive("*", Op.MUL)
    dictionary.add_colon("SQUARE", 0x120)
    dictionary.add_primitive("IMM", Op.NOP, immediate=True)
    entries = [
        {
            "name": entry.name,
            "header": entry.header_address,
            "link": entry.link,
            "flags": entry.flags,
            "xt": entry.xt,
            "kind": entry.kind,
            "payload": entry.payload,
            "immediate": entry.immediate,
            "hidden": entry.hidden,
        }
        for entry in dictionary.entries()
    ]
    return dictionary, entries


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    args = parser.parse_args()
    dictionary, entries = build_fixture()
    args.image.write_bytes(dictionary.image())
    print(
        json.dumps(
            {
                "base": dictionary.base,
                "here": dictionary.here,
                "latest": dictionary.latest,
                "bytes": len(dictionary.image()),
                "entries": entries,
            },
            separators=(",", ":"),
        )
    )


if __name__ == "__main__":
    main()
