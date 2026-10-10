"""Incremental linker for guarded RP2350 Thumb fragments."""

from __future__ import annotations

from dataclasses import dataclass, replace
import struct

from min0_rp2350_thumb_emitter import (
    MachineFragment,
    MachineRelocation,
    UDF_RELOCATION_SLOT,
    REGISTER_NUMBER,
    verify_machine_fragment,
)
from min0_virtual_assembler import VerifyError
from min0_virtual_assembler_rp2350 import (
    COMPARISON_REGISTERS,
    FUNCTION_FRAME_REGISTERS,
    HELPER_SIGNATURES,
)


NOP = 0xBF00
FUNCTION_PUSH_R4_R10_LR = struct.pack("<HH", 0xE92D, 0x47F0)
FUNCTION_POP_R4_R10_LR = struct.pack("<HH", 0xE8BD, 0x47F0)
THUNK_PUSH_R12_LR = struct.pack("<HH", 0xE92D, 0x5000)
THUNK_POP_R12_LR = struct.pack("<HH", 0xE8BD, 0x5000)
THUNK_POP_R12_PC = struct.pack("<HH", 0xE8BD, 0x9000)


@dataclass(frozen=True)
class ThunkInstruction:
    opcode: str
    operands: tuple[str | int, ...]


@dataclass(frozen=True)
class HelperThunkPlan:
    call_site_offset: int
    helper_symbol: str
    instructions: tuple[ThunkInstruction, ...]


def link_literal_constants(fragment: MachineFragment) -> MachineFragment:
    """Resolve MOV_IMM32 actions through a deduplicated trailing literal pool."""

    verify_machine_fragment(fragment)
    targets = [item for item in fragment.relocations if item.opcode == "MOV_IMM32"]
    if not targets:
        return fragment

    code = bytearray(fragment.code)
    while len(code) % 4:
        code.extend(b"\x00\xBF")
    pool_start = len(code)
    value_offsets: dict[int, int] = {}
    for relocation in targets:
        value = int(relocation.operands[1]) & 0xFFFF_FFFF
        if value not in value_offsets:
            value_offsets[value] = len(code)
            code.extend(struct.pack("<I", value))

    remaining: list[MachineRelocation] = []
    for relocation in fragment.relocations:
        if relocation.opcode != "MOV_IMM32":
            remaining.append(relocation)
            continue
        register_name = str(relocation.operands[0])
        register = REGISTER_NUMBER.get(register_name, 16)
        if register > 7:
            raise VerifyError("Thumb literal load requires a low destination register")
        value = int(relocation.operands[1]) & 0xFFFF_FFFF
        literal_offset = value_offsets[value]
        pc_base = (relocation.offset + 4) & ~3
        displacement = literal_offset - pc_base
        if displacement < 0 or displacement % 4 or displacement > 1020:
            raise VerifyError("literal pool is outside Thumb LDR literal range")
        halfword = 0x4800 | (register << 8) | (displacement // 4)
        code[relocation.offset:relocation.offset + 4] = struct.pack("<HH", halfword, NOP)

    linked = MachineFragment(
        fragment.architecture, bytes(code), tuple(remaining), dict(fragment.labels)
    )
    verify_machine_fragment(linked)
    if pool_start >= len(linked.code):
        raise VerifyError("literal linker did not append a pool")
    return linked


def bind_helper_symbols(fragment: MachineFragment) -> MachineFragment:
    """Bind helper backend actions to named out-of-line thunk relocations."""

    verify_machine_fragment(fragment)
    relocations: list[MachineRelocation] = []
    for relocation in fragment.relocations:
        signature = HELPER_SIGNATURES.get(relocation.opcode)
        if signature is None:
            relocations.append(relocation)
            continue
        relocations.append(replace(
            relocation,
            kind="RP2350_HELPER_THUNK_CALL",
            symbol=signature.name,
        ))
    bound = MachineFragment(
        fragment.architecture, fragment.code, tuple(relocations), dict(fragment.labels)
    )
    verify_machine_fragment(bound)
    return bound


def prepare_link(fragment: MachineFragment) -> MachineFragment:
    """Apply every linker pass that is safe without final addresses."""

    return bind_helper_symbols(link_literal_constants(fragment))


def link_function_frame(fragment: MachineFragment) -> MachineFragment:
    """Resolve the fixed prologue, context bind, epilogue, and return actions."""

    verify_machine_fragment(fragment)
    replacements = {
        "PROLOGUE_SAVE": FUNCTION_PUSH_R4_R10_LR,
        "CONTEXT_BIND": struct.pack("<HH", _encode_thumb_mov("r8", "r0"), NOP),
        "EPILOGUE_RESTORE": FUNCTION_POP_R4_R10_LR,
        "RETURN": struct.pack("<HH", 0x4770, NOP),  # BX lr; NOP
    }
    expected_operands = {
        "PROLOGUE_SAVE": FUNCTION_FRAME_REGISTERS,
        "CONTEXT_BIND": ("r8", "r0"),
        "EPILOGUE_RESTORE": FUNCTION_FRAME_REGISTERS,
        "RETURN": (),
    }
    code = bytearray(fragment.code)
    remaining: list[MachineRelocation] = []
    for relocation in fragment.relocations:
        replacement = replacements.get(relocation.opcode)
        if replacement is None:
            remaining.append(relocation)
            continue
        if relocation.kind != "RP2350_BACKEND_ACTION":
            raise VerifyError(f"unexpected relocation kind for {relocation.opcode}")
        if relocation.operands != expected_operands[relocation.opcode]:
            raise VerifyError(f"unexpected operands for {relocation.opcode}")
        code[relocation.offset:relocation.offset + 4] = replacement

    linked = MachineFragment(
        fragment.architecture, bytes(code), tuple(remaining), dict(fragment.labels)
    )
    verify_machine_fragment(linked)
    return linked


def link_internal_branches(fragment: MachineFragment) -> MachineFragment:
    """Resolve R0 branches while restoring the captured virtual comparison."""

    verify_machine_fragment(fragment)
    conditions = {
        "BEQ": 0x0,
        "BNE": 0x1,
        "BLTU": 0x3,
        "BGEU": 0x2,
        "BLT": 0xB,
        "BGE": 0xA,
    }
    code = bytearray(fragment.code)
    remaining: list[MachineRelocation] = []
    for relocation in fragment.relocations:
        if relocation.opcode not in conditions and relocation.opcode != "BRA":
            remaining.append(relocation)
            continue
        if relocation.kind != "RP2350_BACKEND_ACTION":
            raise VerifyError(f"unexpected relocation kind for {relocation.opcode}")
        if len(relocation.operands) != 1:
            raise VerifyError(f"unexpected operands for {relocation.opcode}")
        label = str(relocation.operands[0])
        try:
            target = fragment.labels[label]
        except KeyError as error:
            raise VerifyError(f"unknown machine label {label}") from error
        if relocation.opcode == "BRA":
            branch = _encode_thumb_b_n(relocation.offset, target)
            replacement = struct.pack("<HH", branch, NOP)
        else:
            compare = _encode_thumb_cmp_general(*COMPARISON_REGISTERS)
            branch = _encode_thumb_b_cond(
                relocation.offset + 2, target, conditions[relocation.opcode]
            )
            replacement = struct.pack("<HH", compare, branch)
        code[relocation.offset:relocation.offset + 4] = replacement

    linked = MachineFragment(
        fragment.architecture, bytes(code), tuple(remaining), dict(fragment.labels)
    )
    verify_machine_fragment(linked)
    return linked


def plan_helper_thunks(
    fragment: MachineFragment, capability_ids: dict[str, int],
) -> tuple[HelperThunkPlan, ...]:
    """Build auditable, 8-byte CPU-stack-balanced helper thunk plans."""

    verify_machine_fragment(fragment)
    plans: list[HelperThunkPlan] = []
    for relocation in fragment.relocations:
        if relocation.kind != "RP2350_HELPER_THUNK_CALL":
            continue
        if relocation.symbol is None:
            raise VerifyError("helper thunk relocation has no symbol")
        body = [ThunkInstruction("THUNK_ENTER_8", ("r12", "lr"))]
        body.append(ThunkInstruction("MOV", ("r0", "r8")))
        if relocation.opcode == "FRAME_LOAD":
            destination, input_index = relocation.operands
            body.extend((
                ThunkInstruction("MOV_IMM32", ("r1", int(input_index))),
                ThunkInstruction("BL", (relocation.symbol,)),
                ThunkInstruction(
                    "ABORT_IF_NONZERO", ("r0", "min0_abort_transaction", 8)
                ),
                ThunkInstruction("MOV", (destination, "r1")),
            ))
        elif relocation.opcode == "RESULT_STAGE":
            output_index, source = relocation.operands
            body.extend((
                ThunkInstruction("MOV_IMM32", ("r1", int(output_index))),
                ThunkInstruction("MOV", ("r2", source)),
                ThunkInstruction("BL", (relocation.symbol,)),
                ThunkInstruction(
                    "ABORT_IF_NONZERO", ("r0", "min0_abort_transaction", 8)
                ),
            ))
        elif relocation.opcode == "CHECKED_LD32":
            destination, capability, base, offset = relocation.operands
            capability_id = _capability_id(str(capability), capability_ids)
            body.extend((
                ThunkInstruction("MOV_IMM32", ("r1", capability_id)),
                ThunkInstruction("MOV", ("r2", base)),
                ThunkInstruction("MOV_IMM32", ("r3", int(offset))),
                ThunkInstruction("BL", (relocation.symbol,)),
                ThunkInstruction(
                    "ABORT_IF_NONZERO", ("r0", "min0_abort_transaction", 8)
                ),
                ThunkInstruction("MOV", (destination, "r1")),
            ))
        elif relocation.opcode == "STAGE_ST32":
            capability, base, offset, source = relocation.operands
            capability_id = _capability_id(str(capability), capability_ids)
            body.extend((
                ThunkInstruction("MOV_IMM32", ("r1", capability_id)),
                ThunkInstruction("MOV", ("r2", base)),
                ThunkInstruction("MOV_IMM32", ("r3", int(offset))),
                ThunkInstruction("MOV", ("r12", source)),
                ThunkInstruction("BL", (relocation.symbol,)),
                ThunkInstruction(
                    "ABORT_IF_NONZERO", ("r0", "min0_abort_transaction", 8)
                ),
            ))
        elif relocation.opcode == "FRAME_COMMIT":
            input_count, output_count = relocation.operands
            body.extend((
                ThunkInstruction("MOV_IMM32", ("r1", int(input_count))),
                ThunkInstruction("MOV_IMM32", ("r2", int(output_count))),
                ThunkInstruction("BL", (relocation.symbol,)),
                ThunkInstruction(
                    "ABORT_IF_NONZERO", ("r0", "min0_abort_transaction", 8)
                ),
            ))
        else:
            raise VerifyError(f"unsupported helper thunk {relocation.opcode}")
        body.append(ThunkInstruction("THUNK_RETURN_8", ("r12", "pc")))
        plan = HelperThunkPlan(relocation.offset, relocation.symbol, tuple(body))
        verify_helper_thunk(plan)
        plans.append(plan)
    return tuple(plans)


def emit_helper_thunks(
    fragment: MachineFragment, capability_ids: dict[str, int],
) -> MachineFragment:
    """Append guarded helper thunks and connect each original helper call site."""

    verify_machine_fragment(fragment)
    plans = plan_helper_thunks(fragment, capability_ids)
    if not plans:
        return fragment

    code = bytearray(fragment.code)
    labels = dict(fragment.labels)
    helper_sites = {plan.call_site_offset for plan in plans}
    relocations = [
        item for item in fragment.relocations if item.offset not in helper_sites
    ]
    for plan in plans:
        while len(code) % 4:
            code.extend(struct.pack("<H", NOP))
        thunk_offset = len(code)
        label = f"@helper-thunk-{plan.call_site_offset:08x}"
        if label in labels:
            raise VerifyError(f"duplicate helper thunk label {label}")
        labels[label] = thunk_offset
        code[plan.call_site_offset:plan.call_site_offset + 4] = encode_thumb_bl(
            plan.call_site_offset, thunk_offset
        )
        _emit_helper_thunk_body(code, relocations, plan)

    emitted = MachineFragment(
        fragment.architecture, bytes(code), tuple(sorted(relocations, key=lambda item: item.offset)),
        labels,
    )
    verify_machine_fragment(emitted)
    return link_literal_constants(emitted)


def resolve_external_branches(
    fragment: MachineFragment,
    image_base: int,
    symbol_addresses: dict[str, int],
) -> MachineFragment:
    """Resolve helper calls and abort branches once final image addresses exist."""

    verify_machine_fragment(fragment)
    if image_base < 0 or image_base > 0xFFFF_FFFF or image_base % 2:
        raise VerifyError("RP2350 image base must be an aligned 32-bit address")
    code = bytearray(fragment.code)
    remaining: list[MachineRelocation] = []
    branch_kinds = {
        "RP2350_THUNK_HELPER_CALL": encode_thumb_bl,
        "RP2350_THUNK_ABORT_BRANCH": encode_thumb_b_w,
    }
    for relocation in fragment.relocations:
        encoder = branch_kinds.get(relocation.kind)
        if encoder is None:
            remaining.append(relocation)
            continue
        if relocation.symbol is None:
            raise VerifyError("external branch relocation has no symbol")
        try:
            target = symbol_addresses[relocation.symbol]
        except KeyError as error:
            raise VerifyError(f"no address for RP2350 symbol {relocation.symbol}") from error
        if not 0 <= target <= 0xFFFF_FFFF:
            raise VerifyError(f"RP2350 symbol address outside 32-bit range: {relocation.symbol}")
        target &= ~1  # Function pointers may carry the Thumb-state bit.
        source = image_base + relocation.offset
        if source > 0xFFFF_FFFF:
            raise VerifyError("RP2350 branch source crosses the 32-bit address space")
        code[relocation.offset:relocation.offset + 4] = encoder(source, target)

    linked = MachineFragment(
        fragment.architecture, bytes(code), tuple(remaining), dict(fragment.labels)
    )
    verify_machine_fragment(linked)
    return linked


def encode_thumb_bl(source_address: int, target_address: int) -> bytes:
    return _encode_thumb_branch(source_address, target_address, link=True)


def encode_thumb_b_w(source_address: int, target_address: int) -> bytes:
    return _encode_thumb_branch(source_address, target_address, link=False)


def verify_helper_thunk(plan: HelperThunkPlan) -> None:
    if not plan.instructions:
        raise VerifyError("empty helper thunk")
    if plan.instructions[0] != ThunkInstruction("THUNK_ENTER_8", ("r12", "lr")):
        raise VerifyError("helper thunk must enter with an 8-byte CPU stack frame")
    if plan.instructions[-1] != ThunkInstruction("THUNK_RETURN_8", ("r12", "pc")):
        raise VerifyError("helper thunk must return and release its 8-byte CPU stack frame")
    forbidden = {"PUSH_DATA", "POP_DATA", "RAW_LDR", "RAW_STR"}
    if any(item.opcode in forbidden for item in plan.instructions):
        raise VerifyError("helper thunk touches forbidden state")
    calls = [item for item in plan.instructions if item.opcode == "BL"]
    if len(calls) != 1 or calls[0].operands != (plan.helper_symbol,):
        raise VerifyError("helper thunk must call exactly its bound helper")
    aborts = [item for item in plan.instructions if item.opcode == "ABORT_IF_NONZERO"]
    if len(aborts) != 1 or aborts[0].operands[2] != 8:
        raise VerifyError("helper failure path must unwind the 8-byte CPU stack frame")


def _emit_helper_thunk_body(
    code: bytearray,
    relocations: list[MachineRelocation],
    plan: HelperThunkPlan,
) -> None:
    for instruction in plan.instructions:
        if instruction.opcode == "THUNK_ENTER_8":
            code.extend(THUNK_PUSH_R12_LR)
        elif instruction.opcode == "THUNK_RETURN_8":
            code.extend(THUNK_POP_R12_PC)
        elif instruction.opcode == "MOV":
            code.extend(struct.pack("<H", _encode_thumb_mov(*instruction.operands)))
        elif instruction.opcode == "MOV_IMM32":
            offset = len(code)
            relocations.append(MachineRelocation(
                offset, "RP2350_BACKEND_ACTION", "MOV_IMM32", instruction.operands
            ))
            code.extend(UDF_RELOCATION_SLOT)
        elif instruction.opcode == "BL":
            offset = len(code)
            relocations.append(MachineRelocation(
                offset, "RP2350_THUNK_HELPER_CALL", "BL", instruction.operands,
                symbol=str(instruction.operands[0]),
            ))
            code.extend(UDF_RELOCATION_SLOT)
        elif instruction.opcode == "ABORT_IF_NONZERO":
            status, symbol, unwind = instruction.operands
            if status != "r0" or unwind != 8:
                raise VerifyError("unsupported helper abort sequence")
            code.extend(struct.pack("<HH", 0x2800, 0xD003))  # CMP r0,#0; BEQ success
            code.extend(THUNK_POP_R12_LR)
            offset = len(code)
            relocations.append(MachineRelocation(
                offset, "RP2350_THUNK_ABORT_BRANCH", "B.W", (symbol,),
                symbol=str(symbol),
            ))
            code.extend(UDF_RELOCATION_SLOT)
        else:
            raise VerifyError(f"cannot emit helper thunk opcode {instruction.opcode}")


def _encode_thumb_mov(destination: str | int, source: str | int) -> int:
    destination_number = _general_register(str(destination))
    source_number = _general_register(str(source))
    return (
        0x4600
        | ((destination_number & 8) << 4)
        | (source_number << 3)
        | (destination_number & 7)
    )


def _encode_thumb_cmp_general(left: str, right: str) -> int:
    left_number = _general_register(left)
    right_number = _general_register(right)
    return (
        0x4500
        | ((left_number & 8) << 4)
        | (right_number << 3)
        | (left_number & 7)
    )


def _encode_thumb_b_cond(source_offset: int, target_offset: int, condition: int) -> int:
    displacement = target_offset - (source_offset + 4)
    if not 0 <= condition <= 0xD:
        raise VerifyError("invalid Thumb conditional branch condition")
    if displacement % 2 or not -256 <= displacement <= 254:
        raise VerifyError("Thumb conditional branch target is outside R0 range")
    return 0xD000 | (condition << 8) | ((displacement >> 1) & 0xFF)


def _encode_thumb_b_n(source_offset: int, target_offset: int) -> int:
    displacement = target_offset - (source_offset + 4)
    if displacement % 2 or not -2048 <= displacement <= 2046:
        raise VerifyError("Thumb branch target is outside R0 range")
    return 0xE000 | ((displacement >> 1) & 0x7FF)


def _general_register(name: str) -> int:
    try:
        number = REGISTER_NUMBER[name]
    except KeyError as error:
        raise VerifyError(f"unknown machine register {name}") from error
    if number > 12:
        raise VerifyError(f"helper thunk MOV does not accept {name}")
    return number


def _encode_thumb_branch(
    source_address: int, target_address: int, *, link: bool,
) -> bytes:
    if source_address % 2 or target_address % 2:
        raise VerifyError("Thumb branch addresses must be halfword aligned")
    displacement = target_address - (source_address + 4)
    if displacement % 2 or not -(1 << 24) <= displacement < (1 << 24):
        raise VerifyError("Thumb wide branch target is outside signed 25-bit range")
    encoded = displacement & 0x01FF_FFFE
    sign = (encoded >> 24) & 1
    i1 = (encoded >> 23) & 1
    i2 = (encoded >> 22) & 1
    j1 = ((~i1) & 1) ^ sign
    j2 = ((~i2) & 1) ^ sign
    first = 0xF000 | (sign << 10) | ((encoded >> 12) & 0x03FF)
    second_base = 0xD000 if link else 0x9000
    second = second_base | (j1 << 13) | (j2 << 11) | ((encoded >> 1) & 0x07FF)
    return struct.pack("<HH", first, second)


def _capability_id(name: str, capability_ids: dict[str, int]) -> int:
    try:
        value = capability_ids[name]
    except KeyError as error:
        raise VerifyError(f"no numeric ID for memory capability {name}") from error
    if not 0 <= value <= 0xFFFF_FFFF:
        raise VerifyError(f"memory capability ID outside 32-bit range: {name}")
    return value
