"""Exercise the protected split-memory backend and print stable JSON."""

import json

from min0_core_forth_vm import Assembler, Min0CoreForthVM, MemoryFault, MemoryRegion, Op, RegionMemory


def faulted(operation) -> bool:
    try:
        operation()
    except MemoryFault:
        return True
    return False


def main() -> None:
    bus = RegionMemory(
        80,
        [
            MemoryRegion("CODE", 0, 32, "rx", programmable=True),
            MemoryRegion("DATA", 32, 32, "rw"),
        ],
    )
    vm = Min0CoreForthVM(memory_size=80, memory_bus=bus)
    assembler = Assembler()
    assembler.emit(Op.LIT, 0x12345678)
    assembler.emit(Op.LIT, 32)
    assembler.emit(Op.STORE)
    assembler.emit(Op.LIT, 32)
    assembler.emit(Op.FETCH)
    assembler.emit(Op.HALT)
    program = assembler.build()
    vm.load(program)
    stack = vm.run()

    result = {
        "stack": stack,
        "steps": vm.steps,
        "code_hex": bus.region_bytes("CODE")[: len(program)].hex(),
        "data_hex": bus.region_bytes("DATA")[:4].hex(),
        "code_write_fault": faulted(lambda: bus.write_u8(0, 0)),
        "data_fetch_fault": faulted(lambda: bus.fetch_u8(32)),
        "boundary_fault": faulted(lambda: bus.read(30, 4)),
        "unmapped_fault": faulted(lambda: bus.read_u8(64)),
    }
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
