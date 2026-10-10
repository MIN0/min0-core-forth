"""Auditable RP2350 lowering plan for MIN0 virtual assembler R0.

This module intentionally does not emit or execute machine code yet.  It
translates verified virtual instructions into a small backend plan where all
stack and memory effects remain explicit and inspectable.
"""

from __future__ import annotations

from dataclasses import dataclass

from min0_virtual_assembler import (
    BINARY_OPS,
    CONDITIONAL_BRANCHES,
    SHIFT_OPS,
    CodeDefinition,
    VerifyError,
    _address_operand,
    _parse_number,
)


ARCHITECTURE = "rp2350-arm-s/cortex-m33"
REGISTER_MAP = {"V0": "r4", "V1": "r5", "V2": "r6", "V3": "r7"}
SAFE_MEMORY_OPS = frozenset({"CHECKED_LD32", "STAGE_ST32"})
HELPER_ABI_VERSION = "min0-rp2350-helper-abi/0.1"
CONTEXT_REGISTER = "r8"
HELPER_CLOBBERS = frozenset({"r0", "r1", "r2", "r3", "r12", "APSR"})
HELPER_PRESERVES = frozenset({"r4", "r5", "r6", "r7", "r8", "r9", "r10", "r11"})


@dataclass(frozen=True)
class HelperSignature:
    name: str
    arguments: tuple[str, ...]
    results: tuple[str, ...]


HELPER_SIGNATURES = {
    "CHECKED_LD32": HelperSignature(
        "min0_checked_ld32",
        ("r0=context", "r1=capability", "r2=base", "r3=offset"),
        ("r0=status", "r1=value"),
    ),
    "STAGE_ST32": HelperSignature(
        "min0_stage_st32",
        ("r0=context", "r1=capability", "r2=base", "r3=offset", "r12=value"),
        ("r0=status",),
    ),
    "FRAME_COMMIT": HelperSignature(
        "min0_frame_commit",
        ("r0=context", "r1=input-count", "r2=output-count"),
        ("r0=status",),
    ),
}


@dataclass(frozen=True)
class BackendInstruction:
    opcode: str
    operands: tuple[str | int, ...]
    source_line: int | None = None


@dataclass(frozen=True)
class BackendPlan:
    word: str
    architecture: str
    input_count: int
    output_count: int
    instructions: tuple[BackendInstruction, ...]

    def listing(self) -> str:
        lines = [
            f"; MIN0 backend plan for {self.word}",
            f"; target {self.architecture}",
            f"; helper ABI {HELPER_ABI_VERSION}",
        ]
        for instruction in self.instructions:
            operands = ", ".join(str(item) for item in instruction.operands)
            lines.append(
                f"{instruction.opcode}{' ' if operands else ''}{operands}"
            )
        return "\n".join(lines) + "\n"


def lower_rp2350(definition: CodeDefinition) -> BackendPlan:
    """Lower a verified CODE definition to an auditable RP2350 plan."""

    lowered: list[BackendInstruction] = [
        BackendInstruction("PROLOGUE_SAVE", ("r4", "r5", "r6", "r7", "r8", "lr")),
        BackendInstruction("CONTEXT_BIND", (CONTEXT_REGISTER, "r0")),
    ]
    input_indexes = {name: index for index, name in enumerate(definition.inputs)}
    output_indexes = {name: index for index, name in enumerate(definition.outputs)}

    for instruction in definition.instructions:
        op, args, line = instruction.opcode, instruction.operands, instruction.line
        if op == "IN":
            lowered.append(BackendInstruction(
                "FRAME_LOAD", (REGISTER_MAP[args[0]], input_indexes[args[1]]), line
            ))
        elif op == "OUT":
            lowered.append(BackendInstruction(
                "RESULT_STAGE", (output_indexes[args[0]], REGISTER_MAP[args[1]]), line
            ))
        elif op == "MOV":
            lowered.append(BackendInstruction(
                "MOV", (REGISTER_MAP[args[0]], REGISTER_MAP[args[1]]), line
            ))
        elif op == "LIT":
            lowered.append(BackendInstruction(
                "MOV_IMM32", (REGISTER_MAP[args[0]], _parse_number(args[1], line)), line
            ))
        elif op in BINARY_OPS or op in SHIFT_OPS:
            second: str | int = REGISTER_MAP[args[1]] if op in BINARY_OPS else int(args[1])
            lowered.append(BackendInstruction(op, (REGISTER_MAP[args[0]], second), line))
        elif op == "NOT":
            lowered.append(BackendInstruction("MVN", (REGISTER_MAP[args[0]],), line))
        elif op == "CMP":
            lowered.append(BackendInstruction(
                "CMP", (REGISTER_MAP[args[0]], REGISTER_MAP[args[1]]), line
            ))
        elif op in CONDITIONAL_BRANCHES or op == "BRA":
            lowered.append(BackendInstruction(op, (f"@{args[0]}",), line))
        elif op == "LABEL":
            lowered.append(BackendInstruction("LABEL", (f"@{args[0]}",), line))
        elif op == "LD32":
            capability, base, offset = _address_operand(args[1], line)
            lowered.append(BackendInstruction(
                "CHECKED_LD32",
                (REGISTER_MAP[args[0]], capability or "DEFAULT", REGISTER_MAP[base], offset),
                line,
            ))
        elif op == "ST32":
            capability, base, offset = _address_operand(args[0], line)
            lowered.append(BackendInstruction(
                "STAGE_ST32",
                (capability or "DEFAULT", REGISTER_MAP[base], offset, REGISTER_MAP[args[1]]),
                line,
            ))
        else:
            raise VerifyError(f"line {line}: RP2350 lowering does not support {op}")

    lowered.extend((
        BackendInstruction(
            "FRAME_COMMIT", (len(definition.inputs), len(definition.outputs))
        ),
        BackendInstruction(
            "EPILOGUE_RESTORE", ("r4", "r5", "r6", "r7", "r8", "lr")
        ),
        BackendInstruction("RETURN", ()),
    ))
    plan = BackendPlan(
        definition.name, ARCHITECTURE, len(definition.inputs),
        len(definition.outputs), tuple(lowered),
    )
    verify_backend_plan(plan)
    return plan


def verify_backend_plan(plan: BackendPlan) -> None:
    """Reject plans that could bypass the runtime stack or memory gates."""

    if not plan.instructions or plan.instructions[0] != BackendInstruction(
        "PROLOGUE_SAVE", ("r4", "r5", "r6", "r7", "r8", "lr")
    ):
        raise VerifyError("backend plan must begin with PROLOGUE_SAVE")
    if len(plan.instructions) < 2 or plan.instructions[1] != BackendInstruction(
        "CONTEXT_BIND", (CONTEXT_REGISTER, "r0")
    ):
        raise VerifyError("backend plan must bind execution context to r8")
    tail = [instruction.opcode for instruction in plan.instructions[-3:]]
    if tail != ["FRAME_COMMIT", "EPILOGUE_RESTORE", "RETURN"]:
        raise VerifyError("backend plan must end with commit, restore, return")
    if plan.instructions[-3].operands != (plan.input_count, plan.output_count):
        raise VerifyError("FRAME_COMMIT counts do not match backend plan contract")
    if plan.instructions[-2].operands != ("r4", "r5", "r6", "r7", "r8", "lr"):
        raise VerifyError("backend epilogue restore set does not match helper ABI")
    if plan.instructions[-1].operands:
        raise VerifyError("RETURN must not have operands")
    forbidden = {"PUSH_DATA", "POP_DATA", "RAW_LDR", "RAW_STR"}
    allowed = {
        "PROLOGUE_SAVE", "CONTEXT_BIND", "FRAME_LOAD", "RESULT_STAGE", "MOV", "MOV_IMM32",
        "MVN", "CMP", "BRA", "LABEL", "CHECKED_LD32", "STAGE_ST32",
        "FRAME_COMMIT", "EPILOGUE_RESTORE", "RETURN",
    } | set(BINARY_OPS) | set(SHIFT_OPS) | set(CONDITIONAL_BRANCHES)
    for instruction in plan.instructions:
        if instruction.opcode in forbidden:
            raise VerifyError(f"unsafe backend opcode {instruction.opcode}")
        if instruction.opcode not in allowed:
            raise VerifyError(f"unknown backend opcode {instruction.opcode}")
    if set(REGISTER_MAP.values()) & HELPER_CLOBBERS:
        raise VerifyError("virtual register mapping overlaps helper clobbers")
    if CONTEXT_REGISTER in HELPER_CLOBBERS:
        raise VerifyError("context register is clobbered by helper ABI")
    labels = {
        instruction.operands[0]
        for instruction in plan.instructions
        if instruction.opcode == "LABEL"
    }
    for instruction in plan.instructions:
        if instruction.opcode in CONDITIONAL_BRANCHES or instruction.opcode == "BRA":
            if instruction.operands[0] not in labels:
                raise VerifyError(f"unknown backend label {instruction.operands[0]}")
