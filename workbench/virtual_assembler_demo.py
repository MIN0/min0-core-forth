import json

from min0_virtual_assembler import compile_code
from test_virtual_assembler import SUM_XOR


def main() -> None:
    definition = compile_code(SUM_XOR)
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
    }, sort_keys=True))


if __name__ == "__main__":
    main()
