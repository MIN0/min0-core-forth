import json

from min0_virtual_assembler import compile_code
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
    }, sort_keys=True))


if __name__ == "__main__":
    main()
