"""Executable R0 reference model for the MIN0 virtual assembler."""

from __future__ import annotations

from dataclasses import dataclass
import re


CELL_MASK = 0xFFFF_FFFF
REGISTERS = frozenset({"V0", "V1", "V2", "V3"})
BINARY_OPS = frozenset({"ADD", "SUB", "MUL", "AND", "OR", "XOR"})
SHIFT_OPS = frozenset({"LSL", "LSR", "ASR", "ROL", "ROR"})
CONDITIONAL_BRANCHES = frozenset({"BEQ", "BNE", "BLT", "BGE", "BLTU", "BGEU"})


class VirtualAssemblerError(Exception):
    """Base class for deterministic assembler failures."""


class ParseError(VirtualAssemblerError):
    pass


class VerifyError(VirtualAssemblerError):
    pass


class StackUnderflow(VirtualAssemblerError):
    pass


class ExecutionError(VirtualAssemblerError):
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

    def execute(self, stack: list[int], *, max_steps: int = 10_000) -> list[int]:
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
        comparison: tuple[int, int] | None = None
        labels = {
            instruction.operands[0]: index
            for index, instruction in enumerate(self.instructions)
            if instruction.opcode == "LABEL"
        }

        pc = 0
        steps = 0
        while pc < len(self.instructions):
            steps += 1
            if steps > max_steps:
                raise ExecutionError(f"{self.name} exceeded {max_steps} virtual instructions")
            instruction = self.instructions[pc]
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
            elif op == "CMP":
                comparison = (registers[args[0]], registers[args[1]])
            elif op in CONDITIONAL_BRANCHES:
                assert comparison is not None
                left, right = comparison
                signed_left = _signed(left)
                signed_right = _signed(right)
                take = {
                    "BEQ": left == right,
                    "BNE": left != right,
                    "BLT": signed_left < signed_right,
                    "BGE": signed_left >= signed_right,
                    "BLTU": left < right,
                    "BGEU": left >= right,
                }[op]
                if take:
                    pc = labels[args[0]]
                    continue
            elif op == "BRA":
                pc = labels[args[0]]
                continue
            elif op == "LABEL":
                pass
            else:  # Static verification makes this unreachable.
                raise AssertionError(op)
            pc += 1

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
    label_match = re.fullmatch(r"@([A-Za-z][A-Za-z0-9_-]*):", text)
    if label_match:
        return Instruction("LABEL", (label_match.group(1),), line)
    parts = text.split(None, 1)
    opcode = parts[0].upper()
    operands = () if len(parts) == 1 else tuple(
        item.strip() for item in parts[1].split(",")
    )
    arity = {
        "NOT": 1, "IN": 2, "OUT": 2, "MOV": 2, "LIT": 2,
        "CMP": 2, "BRA": 1, "LABEL": 1,
        **{opcode: 1 for opcode in CONDITIONAL_BRANCHES},
    }
    if opcode in BINARY_OPS or opcode in SHIFT_OPS:
        expected = 2
    elif opcode in arity:
        expected = arity[opcode]
    else:
        raise ParseError(f"line {line}: unknown opcode {opcode}")
    if len(operands) != expected or any(not operand for operand in operands):
        raise ParseError(f"line {line}: {opcode} expects {expected} operand(s)")
    if opcode in CONDITIONAL_BRANCHES or opcode == "BRA":
        target = operands[0]
        if target.startswith("@"):
            target = target[1:]
        operands = (target,)
    return Instruction(opcode, operands, line)


def _verify(definition: CodeDefinition) -> None:
    labels: dict[str, int] = {}
    for instruction in definition.instructions:
        op, args, line = instruction.opcode, instruction.operands, instruction.line
        if op == "LABEL":
            _label(args[0], line)
            if args[0] in labels:
                raise VerifyError(f"line {line}: duplicate label {args[0]}")
            labels[args[0]] = len(labels)
        elif op in CONDITIONAL_BRANCHES or op == "BRA":
            _label(args[0], line)
        elif op == "IN":
            _register(args[0], line)
            if args[1] not in definition.inputs:
                raise VerifyError(f"line {line}: unknown input {args[1]}")
        elif op == "OUT":
            if args[0] not in definition.outputs:
                raise VerifyError(f"line {line}: unknown output {args[0]}")
            _register(args[1], line)
        elif op in {"MOV", "CMP"} or op in BINARY_OPS:
            _register(args[0], line)
            _register(args[1], line)
        elif op == "LIT":
            _register(args[0], line)
            _parse_number(args[1], line)
        elif op == "NOT":
            _register(args[0], line)
        elif op in SHIFT_OPS:
            _register(args[0], line)
            try:
                count = int(args[1], 10)
            except ValueError as error:
                raise VerifyError(f"line {line}: invalid shift count {args[1]}") from error
            if not 0 <= count <= 31:
                raise VerifyError(f"line {line}: shift count must be 0..31")
    for instruction in definition.instructions:
        if instruction.opcode in CONDITIONAL_BRANCHES or instruction.opcode == "BRA":
            if instruction.operands[0] not in labels:
                raise VerifyError(
                    f"line {instruction.line}: unknown label {instruction.operands[0]}"
                )
    _verify_paths(definition)


def _verify_paths(definition: CodeDefinition) -> None:
    labels = {
        instruction.operands[0]: index
        for index, instruction in enumerate(definition.instructions)
        if instruction.opcode == "LABEL"
    }
    pending = [(0, frozenset(), frozenset(), False)]
    seen: set[tuple[int, frozenset[str], frozenset[str], bool]] = set()
    terminal_seen = False
    while pending:
        pc, initialized, assigned, compared = pending.pop()
        state = (pc, initialized, assigned, compared)
        if state in seen:
            continue
        seen.add(state)
        if pc == len(definition.instructions):
            terminal_seen = True
            missing = [name for name in definition.outputs if name not in assigned]
            if missing:
                raise VerifyError(f"output(s) not assigned: {', '.join(missing)}")
            continue

        instruction = definition.instructions[pc]
        op, args, line = instruction.opcode, instruction.operands, instruction.line
        next_initialized = set(initialized)
        next_assigned = set(assigned)
        next_compared = compared
        if op == "IN":
            next_initialized.add(args[0])
        elif op == "OUT":
            _read_register(args[1], set(initialized), line)
            if args[0] in assigned:
                raise VerifyError(f"line {line}: output {args[0]} assigned twice on one path")
            next_assigned.add(args[0])
        elif op == "MOV":
            _read_register(args[1], set(initialized), line)
            next_initialized.add(args[0])
        elif op == "LIT":
            next_initialized.add(args[0])
        elif op in BINARY_OPS:
            _read_register(args[0], set(initialized), line)
            _read_register(args[1], set(initialized), line)
        elif op == "NOT" or op in SHIFT_OPS:
            _read_register(args[0], set(initialized), line)
        elif op == "CMP":
            _read_register(args[0], set(initialized), line)
            _read_register(args[1], set(initialized), line)
            next_compared = True
        elif op in CONDITIONAL_BRANCHES:
            if not compared:
                raise VerifyError(f"line {line}: {op} requires CMP on every path")
            branch_state = (
                labels[args[0]], frozenset(next_initialized),
                frozenset(next_assigned), next_compared,
            )
            pending.append(branch_state)
        elif op == "BRA":
            pending.append((
                labels[args[0]], frozenset(next_initialized),
                frozenset(next_assigned), next_compared,
            ))
            continue
        pending.append((
            pc + 1, frozenset(next_initialized), frozenset(next_assigned), next_compared,
        ))
    if not terminal_seen:
        raise VerifyError("CODE definition has no terminating path")


def _register(name: str, line: int) -> None:
    if name.upper() not in REGISTERS or name != name.upper():
        raise VerifyError(f"line {line}: unknown register {name}")


def _read_register(name: str, initialized: set[str], line: int) -> None:
    _register(name, line)
    if name not in initialized:
        raise VerifyError(f"line {line}: register {name} is uninitialized")


def _label(name: str, line: int) -> None:
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", name):
        raise VerifyError(f"line {line}: invalid label {name}")


def _signed(value: int) -> int:
    return value if value < 0x8000_0000 else value - 0x1_0000_0000


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
