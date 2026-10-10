import json

from min0_virtual_assembler import MemoryWindow, compile_code
from test_virtual_assembler import SUM_XOR


def main() -> None:
    definition = compile_code(SUM_XOR)
    maximum = compile_code("""CODE: MAX ( a b -- max )
    IN V0, a
    IN V1, b
    CMP V0, V1
    BGE @a-wins
    OUT max, V1
    BRA @done
@a-wins:
    OUT max, V0
@done:
    ;CODE""")
    memory = MemoryWindow(0x1000, 4)
    round_trip = compile_code("""CODE: ROUND-TRIP ( value address -- observed )
    IN V0, value
    IN V1, address
    ST32 [V1], V0
    LD32 V2, [V1]
    OUT observed, V2
    ;CODE""")
    memory_result = round_trip.execute([55, 0x1000], memory=memory)
    before = [10, 20, 30]
    print(json.dumps({
        "format": "min0-virtual-assembler/0.1",
        "implementation": "python",
        "word": definition.name,
        "inputs": list(definition.inputs),
        "outputs": list(definition.outputs),
        "before": before,
        "after": definition.execute(before),
        "instruction_count": len(definition.instructions),
        "branch_results": [maximum.execute([10, 20]), maximum.execute([30, 20])],
        "memory_result": memory_result,
        "committed_memory": memory.read32(0x1000),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
