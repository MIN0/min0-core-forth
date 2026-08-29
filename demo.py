"""Execute two colon-definition-like routines on MIN0 CORE FORTH VM v0.1."""

from min0_core_forth_vm import Assembler, Min0CoreForthVM, Op


def make_demo_program() -> bytes:
    asm = Assembler()

    # Equivalent to: 5 SQUARE 7 DOUBLE
    asm.label("main")
    asm.emit(Op.LIT, 5)
    asm.emit(Op.CALL, "square")
    asm.emit(Op.LIT, 7)
    asm.emit(Op.CALL, "double")
    asm.emit(Op.HALT)

    # : SQUARE DUP * ;
    asm.label("square")
    asm.emit(Op.DUP)
    asm.emit(Op.MUL)
    asm.emit(Op.EXIT)

    # : DOUBLE DUP + ;
    asm.label("double")
    asm.emit(Op.DUP)
    asm.emit(Op.ADD)
    asm.emit(Op.EXIT)

    return asm.build()


if __name__ == "__main__":
    vm = Min0CoreForthVM()
    vm.load(make_demo_program())
    result = vm.run()
    print("MIN0 CORE FORTH VM v0.1")
    print(f"steps: {vm.steps}")
    print(f"data stack: {result}")
    print("PASS" if result == [25, 14] else "FAIL")
