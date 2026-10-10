"""Executable R0 reference model for the MIN0 virtual assembler."""

from __future__ import annotations

from dataclasses import dataclass
import re


CELL_MASK = 0xFFFF_FFFF
REGISTERS = frozenset({"V0", "V1", "V2", "V3"})
BINARY_OPS = frozenset({"ADD", "SUB", "MUL", "AND", "OR", "XOR"})
SHIFT_OPS = frozenset({"LSL", "LSR", "ASR", "ROL", "ROR"})


class VirtualAssemblerError(Exception):
    """Base class for deterministic assembler failures."""


class ParseError(VirtualAssemblerError):
    pass


class VerifyError(VirtualAssemblerError):
    pass


class StackUnderflow(VirtualAssemblerError):
    pass


@dataclass(frozen=True)
class Instruction:
    opcode: str
    operands: tuple[str, ...]
    line: int


@dataclass(frozen=True)
class CodeDefinition:
    name: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    instructions: tuple[Instruction, ...]

    def execute(self, stack: list[int]) -> list[int]:
        """Return a new stack; never mutate the caller's stack."""

        input_count = len(self.inputs)
        if len(stack) < input_count:
            raise StackUnderflow(
                f"{self.name} needs {input_count} inputs but stack has {len(stack)}"
            )
        prefix = list(stack[:-input_count]) if input_count else list(stack)
        values = list(stack[-input_count:]) if input_count else []
        entry = {
            name: value & CELL_MASK for name, value in zip(self.inputs, values)
        }
        registers: dict[str, int] = {}
        staged: dict[str, int] = {}

        for instruction in self.instructions:
            op = instruction.opcode
            args = instruction.operands
            if op == "IN":
                registers[args[0]] = entry[args[1]]
            elif op == "OUT":
                staged[args[0]] = registers[args[1]]
            elif op == "MOV":
                registers[args[0]] = registers[args[1]]
            elif op == "LIT":
                registers[args[0]] = _parse_number(args[1], instruction.line)
            elif op in BINARY_OPS:
                left = registers[args[0]]
                right = registers[args[1]]
                if op == "ADD":
                    result = left + right
                elif op == "SUB":
                    result = left - right
                elif op == "MUL":
                    result = left * right
                elif op == "AND":
                    result = left & right
                elif op == "OR":
                    result = left | right
                else:
                    result = left ^ right
                registers[args[0]] = result & CELL_MASK
            elif op == "NOT":
                registers[args[0]] = (~registers[args[0]]) & CELL_MASK
            elif op in SHIFT_OPS:
                register, raw_count = args
                value = registers[register]
                count = int(raw_count, 10)
                if op == "LSL":
                    result = value << count
                elif op == "LSR":
                    result = value >> count
                elif op == "ASR":
                    signed = value if value < 0x8000_0000 else value - 0x1_0000_0000
                    result = signed >> count
                elif op == "ROL":
                    result = value if count == 0 else (value << count) | (value >> (32 - count))
                else:
                    result = value if count == 0 else (value >> count) | (value << (32 - count))
                registers[register] = result & CELL_MASK
            else:  # Static verification makes this unreachable.
                raise AssertionError(op)

        return prefix + [staged[name] for name in self.outputs]


HEADER = re.compile(
    r"^\s*CODE:\s+([A-Za-z][A-Za-z0-9_-]*)\s*"
    r"\(\s*(.*?)\s*--\s*(.*?)\s*\)\s*$",
    re.IGNORECASE,
)


def compile_code(source: str) -> CodeDefinition:
    """Parse and statically verify one CODE: ... ;CODE definition."""

    lines = source.splitlines()
    meaningful = [(index, line) for index, line in enumerate(lines, 1) if line.strip()]
    if not meaningful:
        raise ParseError("empty source")
    header_line, header_text = meaningful[0]
    match = HEADER.match(header_text)
    if not match:
        raise ParseError(f"line {header_line}: invalid CODE header")
    name = match.group(1).upper()
    inputs = _names(match.group(2), "input", header_line)
    outputs = _names(match.group(3), "output", header_line)

    instructions: list[Instruction] = []
    ended = False
    for line_number, raw_line in meaningful[1:]:
        line = raw_line.split("\\", 1)[0].strip()
        if not line:
            continue
        if line.upper() == ";CODE":
            ended = True
            break
        instructions.append(_parse_instruction(line, line_number))
    if not ended:
        raise ParseError("missing ;CODE")

    definition = CodeDefinition(name, inputs, outputs, tuple(instructions))
    _verify(definition)
    return definition


def _names(text: str, role: str, line: int) -> tuple[str, ...]:
    names = tuple(part for part in text.split() if part)
    for name in names:
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", name):
            raise ParseError(f"line {line}: invalid {role} name {name!r}")
    if len(set(names)) != len(names):
        raise VerifyError(f"line {line}: duplicate {role} name")
    return names


def _parse_instruction(text: str, line: int) -> Instruction:
    parts = text.split(None, 1)
    opcode = parts[0].upper()
    operands = () if len(parts) == 1 else tuple(
        item.strip() for item in parts[1].split(",")
    )
    arity = {"NOT": 1, "IN": 2, "OUT": 2, "MOV": 2, "LIT": 2}
    if opcode in BINARY_OPS or opcode in SHIFT_OPS:
        expected = 2
    elif opcode in arity:
        expected = arity[opcode]
    else:
        raise ParseError(f"line {line}: unknown opcode {opcode}")
    if len(operands) != expected or any(not operand for operand in operands):
        raise ParseError(f"line {line}: {opcode} expects {expected} operand(s)")
    return Instruction(opcode, operands, line)


def _verify(definition: CodeDefinition) -> None:
    initialized: set[str] = set()
    assigned_outputs: set[str] = set()
    for instruction in definition.instructions:
        op, args, line = instruction.opcode, instruction.operands, instruction.line
        if op == "IN":
            _register(args[0], line)
            if args[1] not in definition.inputs:
                raise VerifyError(f"line {line}: unknown input {args[1]}")
            initialized.add(args[0])
        elif op == "OUT":
            if args[0] not in definition.outputs:
                raise VerifyError(f"line {line}: unknown output {args[0]}")
            _read_register(args[1], initialized, line)
            if args[0] in assigned_outputs:
                raise VerifyError(f"line {line}: output {args[0]} assigned twice")
            assigned_outputs.add(args[0])
        elif op == "MOV":
            _register(args[0], line)
            _read_register(args[1], initialized, line)
            initialized.add(args[0])
        elif op == "LIT":
            _register(args[0], line)
            _parse_number(args[1], line)
            initialized.add(args[0])
        elif op in BINARY_OPS:
            _read_register(args[0], initialized, line)
            _read_register(args[1], initialized, line)
        elif op == "NOT":
            _read_register(args[0], initialized, line)
        elif op in SHIFT_OPS:
            _read_register(args[0], initialized, line)
            try:
                count = int(args[1], 10)
            except ValueError as error:
                raise VerifyError(f"line {line}: invalid shift count {args[1]}") from error
            if not 0 <= count <= 31:
                raise VerifyError(f"line {line}: shift count must be 0..31")
    missing = [name for name in definition.outputs if name not in assigned_outputs]
    if missing:
        raise VerifyError(f"output(s) not assigned: {', '.join(missing)}")


def _register(name: str, line: int) -> None:
    if name.upper() not in REGISTERS or name != name.upper():
        raise VerifyError(f"line {line}: unknown register {name}")


def _read_register(name: str, initialized: set[str], line: int) -> None:
    _register(name, line)
    if name not in initialized:
        raise VerifyError(f"line {line}: register {name} is uninitialized")


def _parse_number(text: str, line: int) -> int:
    try:
        if re.fullmatch(r"-?0[xX][0-9A-Fa-f]+", text):
            sign = -1 if text.startswith("-") else 1
            digits = text[3:] if sign < 0 else text[2:]
            value = sign * int(digits, 16)
        elif re.fullmatch(r"-?[0-9]+", text):
            value = int(text, 10)
        else:
            raise ValueError(text)
    except ValueError as error:
        raise VerifyError(f"line {line}: invalid number {text}") from error
    if not -(1 << 31) <= value <= CELL_MASK:
        raise VerifyError(f"line {line}: literal outside 32-bit cell")
    return value & CELL_MASK
