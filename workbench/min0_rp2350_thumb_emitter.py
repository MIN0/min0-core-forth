"""First non-executable Thumb machine fragment emitter for RP2350 plans."""

from __future__ import annotations

from dataclasses import dataclass
import struct

from min0_virtual_assembler import VerifyError
from min0_virtual_assembler_rp2350 import (
    BackendPlan,
    COMPARISON_REGISTERS,
    verify_backend_plan,
)


UDF_RELOCATION_SLOT = b"\x00\xDE\x01\xDE"
REGISTER_NUMBER = {f"r{number}": number for number in range(16)}


@dataclass(frozen=True)
class MachineRelocation:
    offset: int
    kind: str
    opcode: str
    operands: tuple[str | int, ...]
    symbol: str | None = None
    reserved_size: int = 4


@dataclass(frozen=True)
class MachineFragment:
    architecture: str
    code: bytes
    relocations: tuple[MachineRelocation, ...]
    labels: dict[str, int]

    @property
    def executable(self) -> bool:
        return not self.relocations


def emit_thumb_fragment(plan: BackendPlan) -> MachineFragment:
    """Emit safe Thumb-16 operations and UDF slots for every unresolved action."""

    verify_backend_plan(plan)
    code = bytearray()
    relocations: list[MachineRelocation] = []
    labels: dict[str, int] = {}
    encoders = {
        "MOV": _mov,
        "ADD": _add,
        "SUB": _sub,
        "AND": lambda operands: _data_processing(0x4000, operands),
        "XOR": lambda operands: _data_processing(0x4040, operands),
        "OR": lambda operands: _data_processing(0x4300, operands),
        "MUL": lambda operands: _data_processing(0x4340, operands),
        "MVN": _mvn,
        "LSL": lambda operands: _shift(0x0000, operands),
        "LSR": lambda operands: _shift(0x0800, operands),
        "ASR": lambda operands: _shift(0x1000, operands),
    }

    for instruction in plan.instructions:
        if instruction.opcode == "LABEL":
            labels[str(instruction.operands[0])] = len(code)
            continue
        if instruction.opcode == "CMP":
            left, right = instruction.operands
            code.extend(struct.pack(
                "<HH",
                _mov_general(COMPARISON_REGISTERS[0], str(left)),
                _mov_general(COMPARISON_REGISTERS[1], str(right)),
            ))
            continue
        encoder = encoders.get(instruction.opcode)
        if encoder is not None:
            code.extend(struct.pack("<H", encoder(instruction.operands)))
            continue
        relocation = MachineRelocation(
            len(code), "RP2350_BACKEND_ACTION", instruction.opcode,
            instruction.operands,
        )
        relocations.append(relocation)
        code.extend(UDF_RELOCATION_SLOT)

    fragment = MachineFragment(plan.architecture, bytes(code), tuple(relocations), labels)
    verify_machine_fragment(fragment)
    return fragment


def verify_machine_fragment(fragment: MachineFragment) -> None:
    previous_end = 0
    for relocation in fragment.relocations:
        start = relocation.offset
        end = start + relocation.reserved_size
        if start % 2 or relocation.reserved_size != len(UDF_RELOCATION_SLOT):
            raise VerifyError("machine relocation must use one aligned UDF slot")
        if start < previous_end:
            raise VerifyError("machine relocations overlap or are not ordered")
        if start < 0 or end > len(fragment.code):
            raise VerifyError("machine relocation is outside emitted code")
        if fragment.code[start:end] != UDF_RELOCATION_SLOT:
            raise VerifyError("unresolved relocation is not protected by UDF instructions")
        previous_end = end
    for name, offset in fragment.labels.items():
        if not name.startswith("@") or offset % 2 or not 0 <= offset <= len(fragment.code):
            raise VerifyError(f"invalid machine label {name}")
    if fragment.relocations and fragment.executable:
        raise VerifyError("fragment with relocations cannot be executable")


def _low_register(name: str) -> int:
    try:
        number = REGISTER_NUMBER[name]
    except KeyError as error:
        raise VerifyError(f"unknown machine register {name}") from error
    if number > 7:
        raise VerifyError(f"Thumb-16 operation requires low register, got {name}")
    return number


def _mov(operands: tuple[str | int, ...]) -> int:
    destination = _low_register(str(operands[0]))
    source = _low_register(str(operands[1]))
    return 0x4600 | (source << 3) | destination


def _mov_general(destination_name: str, source_name: str) -> int:
    try:
        destination = REGISTER_NUMBER[destination_name]
        source = REGISTER_NUMBER[source_name]
    except KeyError as error:
        raise VerifyError("unknown register in comparison snapshot") from error
    if destination > 12 or source > 12:
        raise VerifyError("comparison snapshot requires general registers r0..r12")
    return (
        0x4600
        | ((destination & 8) << 4)
        | (source << 3)
        | (destination & 7)
    )


def _add(operands: tuple[str | int, ...]) -> int:
    destination = _low_register(str(operands[0]))
    source = _low_register(str(operands[1]))
    return 0x1800 | (source << 6) | (destination << 3) | destination


def _sub(operands: tuple[str | int, ...]) -> int:
    destination = _low_register(str(operands[0]))
    source = _low_register(str(operands[1]))
    return 0x1A00 | (source << 6) | (destination << 3) | destination


def _data_processing(base: int, operands: tuple[str | int, ...]) -> int:
    destination = _low_register(str(operands[0]))
    source = destination if len(operands) == 1 else _low_register(str(operands[1]))
    return base | (source << 3) | destination


def _mvn(operands: tuple[str | int, ...]) -> int:
    return _data_processing(0x43C0, operands)


def _shift(base: int, operands: tuple[str | int, ...]) -> int:
    register = _low_register(str(operands[0]))
    count = int(operands[1])
    if not 0 <= count <= 31:
        raise VerifyError("Thumb immediate shift count must be 0..31")
    if count == 0:
        return _mov((f"r{register}", f"r{register}"))
    return base | (count << 6) | (register << 3) | register
