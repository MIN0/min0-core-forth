"""Compile and execute with separate CODE, DICTIONARY, and DATA regions."""

import hashlib
import json

from min0_core_forth_dictionary import RuntimeDictionary
from min0_core_forth_outer import OuterInterpreter, install_core_primitives
from min0_core_forth_vm import Min0CoreForthVM, MemoryRegion, RegionMemory


def main() -> None:
    bus = RegionMemory(
        0x10000,
        [
            MemoryRegion("CODE", 0x0000, 0x4000, "rwx", programmable=True),
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
    stack = outer.interpret(
        "CREATE TABLE 10 , 20 , "
        "VARIABLE FLAG "
        ": SUM-TABLE TABLE @ TABLE CELL+ @ + ; "
        "SUM-TABLE DUP FLAG ! FLAG @ TABLE"
    )
    table = dictionary.find("TABLE")
    flag = dictionary.find("FLAG")
    sum_table = dictionary.find("SUM-TABLE")
    assert table is not None and flag is not None and sum_table is not None
    dictionary_image = dictionary.image()

    result = {
        "stack": stack,
        "steps": vm.steps,
        "table": [table.header_address, table.payload],
        "flag": [flag.header_address, flag.payload],
        "sum_table": [sum_table.header_address, sum_table.payload],
        "header_here": dictionary.here,
        "data_here": dictionary.data_here,
        "code_here": outer.code_here,
        "body_hex": dictionary.body_image().hex(),
        "dictionary_sha256": hashlib.sha256(dictionary_image).hexdigest(),
    }
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
