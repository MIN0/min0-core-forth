"""Minimal MIN0 CORE FORTH bytecode virtual machine (draft v0.1).

The VM deliberately models only the CPU-independent execution core.  Console
I/O, dictionaries, parsing, and target-specific services are outside this
first executable experiment.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Callable, Iterable, Protocol, runtime_checkable


CELL_BITS = 32
CELL_BYTES = CELL_BITS // 8
CELL_MASK = (1 << CELL_BITS) - 1
SIGN_BIT = 1 << (CELL_BITS - 1)
DEFAULT_MEMORY_SIZE = 64 * 1024
DEFAULT_DATA_STACK_DEPTH = 256
DEFAULT_RETURN_STACK_DEPTH = 256
DEFAULT_LOOP_STACK_DEPTH = 32
MINIMUM_CONFORMING_LOOP_DEPTH = 8


class VMError(RuntimeError):
    """Base class for deterministic VM failures."""


class StackUnderflow(VMError):
    pass


class StackOverflow(VMError):
    pass


class DataStackOverflow(StackOverflow):
    pass


class ReturnStackOverflow(StackOverflow):
    pass


class LoopStackOverflow(StackOverflow):
    pass


class LoopStackUnderflow(StackUnderflow):
    pass


class MemoryFault(VMError):
    pass


class InvalidOpcode(VMError):
    pass


class StepLimitExceeded(VMError):
    pass


class UnassignedDefer(VMError):
    pass


class InvalidIndirectCall(VMError):
    pass


class DeferStoreDenied(VMError):
    pass


class InvalidExecutionTarget(VMError):
    pass


class ExecutionPolicyError(VMError):
    pass


class UnknownService(VMError):
    pass


class ServiceRegistrationError(VMError):
    pass


class ServiceRegistrySealed(ServiceRegistrationError):
    pass


@runtime_checkable
class MemoryBus(Protocol):
    """Byte-addressed memory interface used by the execution engine."""

    @property
    def size(self) -> int: ...

    def check_read(self, address: int, size: int) -> None: ...
    def check_write(self, address: int, size: int) -> None: ...
    def check_fetch(self, address: int, size: int) -> None: ...
    def read(self, address: int, size: int) -> bytes: ...
    def write(self, address: int, data: bytes) -> None: ...
    def program(self, address: int, data: bytes) -> None: ...
    def fetch(self, address: int, size: int) -> bytes: ...
    def read_u8(self, address: int) -> int: ...
    def write_u8(self, address: int, value: int) -> None: ...
    def fetch_u8(self, address: int) -> int: ...
    def clear(self) -> None: ...


class FlatMemory:
    """Backward-compatible, readable/writable/executable flat memory."""

    def __init__(self, size: int) -> None:
        if size <= 0:
            raise ValueError("memory size must be positive")
        self._data = bytearray(size)

    @property
    def size(self) -> int:
        return len(self._data)

    def check_read(self, address: int, size: int) -> None:
        self._check_range(address, size)

    def check_write(self, address: int, size: int) -> None:
        self._check_range(address, size)

    def check_fetch(self, address: int, size: int) -> None:
        self._check_range(address, size)

    def read(self, address: int, size: int) -> bytes:
        self.check_read(address, size)
        return bytes(self._data[address : address + size])

    def write(self, address: int, data: bytes) -> None:
        raw = bytes(data)
        self.check_write(address, len(raw))
        self._data[address : address + len(raw)] = raw

    def program(self, address: int, data: bytes) -> None:
        self.write(address, data)

    def fetch(self, address: int, size: int) -> bytes:
        self.check_fetch(address, size)
        return bytes(self._data[address : address + size])

    def read_u8(self, address: int) -> int:
        self.check_read(address, 1)
        return self._data[address]

    def write_u8(self, address: int, value: int) -> None:
        self.check_write(address, 1)
        self._data[address] = value & 0xFF

    def fetch_u8(self, address: int) -> int:
        self.check_fetch(address, 1)
        return self._data[address]

    def clear(self) -> None:
        self._data[:] = b"\x00" * self.size

    def _check_range(self, address: int, size: int) -> None:
        if address < 0 or size < 0 or address + size > self.size:
            raise MemoryFault(
                f"memory range 0x{address:08X}..0x{address + size:08X} is invalid"
            )

    # Temporary sequence compatibility for dictionary/compiler migration.
    def __len__(self) -> int:
        return self.size

    def __getitem__(self, key: int | slice) -> int | bytearray:
        return self._data[key]

    def __setitem__(self, key: int | slice, value: int | bytes) -> None:
        self._data[key] = value

    def __bytes__(self) -> bytes:
        return bytes(self._data)


@dataclass
class MemoryRegion:
    """One non-overlapping logical region in a RegionMemory map."""

    name: str
    start: int
    size: int
    permissions: str
    programmable: bool = False
    sealed: bool = field(default=False, init=False)
    read_only_sealed: bool = field(default=False, init=False)
    write_protected: bool = field(default=False, init=False)
    _write_authorities: list[object] = field(default_factory=list, init=False, repr=False)
    data: bytearray = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("memory region name must not be empty")
        if self.start < 0 or self.size <= 0:
            raise ValueError("memory region start/size is invalid")
        if not self.permissions or set(self.permissions) - set("rwx"):
            raise ValueError("memory region permissions must use r, w, and/or x")
        if len(set(self.permissions)) != len(self.permissions):
            raise ValueError("memory region permissions contain duplicates")
        self.data = bytearray(self.size)

    @property
    def end(self) -> int:
        return self.start + self.size


class RegionMemory:
    """Logical memory composed of protected, non-overlapping regions."""

    def __init__(self, size: int, regions: Iterable[MemoryRegion]) -> None:
        if size <= 0:
            raise ValueError("memory size must be positive")
        self._size = size
        self.regions = sorted(list(regions), key=lambda region: region.start)
        self._active_write_authorities: list[tuple[MemoryRegion, object]] = []
        if not self.regions:
            raise ValueError("at least one memory region is required")
        if len({region.name for region in self.regions}) != len(self.regions):
            raise ValueError("memory region names must be unique")
        previous_end = 0
        for index, region in enumerate(self.regions):
            if region.end > size:
                raise ValueError(f"memory region {region.name!r} is outside the map")
            if index and region.start < previous_end:
                raise ValueError("memory regions must not overlap")
            previous_end = region.end

    @property
    def size(self) -> int:
        return self._size

    def check_read(self, address: int, size: int) -> None:
        self._resolve(address, size, "r")

    def check_write(self, address: int, size: int) -> None:
        region = self._resolve(address, size, "w")
        self._check_write_authority(address, size, region)

    def check_fetch(self, address: int, size: int) -> None:
        self._resolve(address, size, "x")

    def read(self, address: int, size: int) -> bytes:
        region = self._resolve(address, size, "r")
        if region is None:
            return b""
        offset = address - region.start
        return bytes(region.data[offset : offset + size])

    def write(self, address: int, data: bytes) -> None:
        raw = bytes(data)
        region = self._resolve(address, len(raw), "w")
        if region is None:
            return
        self._check_write_authority(address, len(raw), region)
        offset = address - region.start
        region.data[offset : offset + len(raw)] = raw

    def program(self, address: int, data: bytes) -> None:
        """Host-side image loading, including explicitly programmable ROM."""

        raw = bytes(data)
        region = self._resolve_containing(address, len(raw))
        if region is None:
            return
        if "w" not in region.permissions and not region.programmable:
            self._permission_fault(address, len(raw), region, "program")
        self._check_write_authority(address, len(raw), region)
        offset = address - region.start
        region.data[offset : offset + len(raw)] = raw

    def protect_region_writes(
        self, name: str, authorities: Iterable[object]
    ) -> None:
        """Require one opaque authority for all later write/program operations."""

        region = next((item for item in self.regions if item.name == name), None)
        if region is None:
            raise MemoryFault(f"memory region {name!r} does not exist")
        if region.write_protected:
            raise MemoryFault(f"memory region {name!r} writes are already protected")
        if "w" not in region.permissions:
            raise MemoryFault(f"memory region {name!r} is not writable")
        tokens: list[object] = []
        for authority in authorities:
            if authority is None:
                raise ValueError("write authority must not be null")
            if not any(authority is token for token in tokens):
                tokens.append(authority)
        if not tokens:
            raise ValueError("at least one write authority is required")
        region._write_authorities = tokens
        region.write_protected = True

    @contextmanager
    def authorized_writes(self, name: str, authority: object):
        region = next((item for item in self.regions if item.name == name), None)
        if region is None:
            raise MemoryFault(f"memory region {name!r} does not exist")
        if not region.write_protected or not any(
            authority is token for token in region._write_authorities
        ):
            raise MemoryFault(f"memory region {name!r} rejects write authority")
        marker = (region, authority)
        self._active_write_authorities.append(marker)
        try:
            yield
        finally:
            if (
                not self._active_write_authorities
                or self._active_write_authorities[-1] is not marker
            ):
                raise RuntimeError("authorized write scope is unbalanced")
            self._active_write_authorities.pop()

    def seal_executable_region(self, name: str) -> None:
        """One-way transition from build storage to non-writable execution."""

        region = next((item for item in self.regions if item.name == name), None)
        if region is None:
            raise MemoryFault(f"memory region {name!r} does not exist")
        if region.sealed:
            return
        permissions = "r" if "r" in region.permissions else ""
        region.permissions = permissions + "x"
        region.programmable = False
        region.sealed = True

    def seal_read_only_region(self, name: str) -> None:
        """One-way transition from loaded storage to readable immutable data."""

        region = next((item for item in self.regions if item.name == name), None)
        if region is None:
            raise MemoryFault(f"memory region {name!r} does not exist")
        if region.read_only_sealed:
            return
        if "r" not in region.permissions:
            raise MemoryFault(f"memory region {name!r} is not readable")
        region.permissions = "r"
        region.programmable = False
        region.read_only_sealed = True

    def fetch(self, address: int, size: int) -> bytes:
        region = self._resolve(address, size, "x")
        if region is None:
            return b""
        offset = address - region.start
        return bytes(region.data[offset : offset + size])

    def read_u8(self, address: int) -> int:
        return self.read(address, 1)[0]

    def write_u8(self, address: int, value: int) -> None:
        self.write(address, bytes([value & 0xFF]))

    def fetch_u8(self, address: int) -> int:
        return self.fetch(address, 1)[0]

    def clear(self) -> None:
        sealed = next((region for region in self.regions if region.sealed), None)
        if sealed is not None:
            raise MemoryFault(f"sealed region {sealed.name!r} cannot be cleared")
        read_only = next(
            (region for region in self.regions if region.read_only_sealed), None
        )
        if read_only is not None:
            raise MemoryFault(
                f"read-only region {read_only.name!r} cannot be cleared"
            )
        protected = next((region for region in self.regions if region.write_protected), None)
        if protected is not None:
            raise MemoryFault(f"protected region {protected.name!r} cannot be cleared")
        for region in self.regions:
            region.data[:] = b"\x00" * region.size

    def region_bytes(self, name: str) -> bytes:
        for region in self.regions:
            if region.name == name:
                return bytes(region.data)
        raise KeyError(name)

    def _resolve(
        self, address: int, size: int, permission: str
    ) -> MemoryRegion | None:
        region = self._resolve_containing(address, size)
        if region is not None and permission not in region.permissions:
            operation = {"r": "read", "w": "write", "x": "fetch"}[permission]
            self._permission_fault(address, size, region, operation)
        return region

    def _resolve_containing(self, address: int, size: int) -> MemoryRegion | None:
        self._check_logical_range(address, size)
        if size == 0:
            return None
        end = address + size
        for region in self.regions:
            if address >= region.start and end <= region.end:
                return region
        raise MemoryFault(
            f"memory range 0x{address:08X}..0x{end:08X} is unmapped or crosses a region"
        )

    def _check_logical_range(self, address: int, size: int) -> None:
        if address < 0 or size < 0 or address + size > self.size:
            raise MemoryFault(
                f"memory range 0x{address:08X}..0x{address + size:08X} is invalid"
            )

    def _check_write_authority(
        self, address: int, size: int, region: MemoryRegion | None
    ) -> None:
        if region is None or not region.write_protected:
            return
        authorized = any(
            active_region is region
            and any(active_authority is token for token in region._write_authorities)
            for active_region, active_authority in self._active_write_authorities
        )
        if not authorized:
            self._permission_fault(address, size, region, "protected write")

    @staticmethod
    def _permission_fault(
        address: int, size: int, region: MemoryRegion, operation: str
    ) -> None:
        raise MemoryFault(
            f"memory region {region.name!r} denies {operation} at "
            f"0x{address:08X}..0x{address + size:08X}"
        )

    # Temporary sequence compatibility for dictionary/compiler migration.
    def __len__(self) -> int:
        return self.size

    def __getitem__(self, key: int | slice) -> int | bytes:
        if isinstance(key, int):
            return self.read_u8(key)
        if key.step not in (None, 1):
            raise ValueError("memory slices do not support a step")
        start = 0 if key.start is None else key.start
        stop = self.size if key.stop is None else key.stop
        return self.read(start, stop - start)

    def __setitem__(self, key: int | slice, value: int | bytes) -> None:
        if isinstance(key, int):
            if not isinstance(value, int):
                raise TypeError("single-byte memory assignment requires an integer")
            self.write_u8(key, value)
            return
        if key.step not in (None, 1):
            raise ValueError("memory slices do not support a step")
        start = 0 if key.start is None else key.start
        stop = self.size if key.stop is None else key.stop
        raw = bytes(value)
        if len(raw) != stop - start:
            raise ValueError("memory slice assignment cannot resize a region")
        self.write(start, raw)


class Op(IntEnum):
    NOP = 0x00
    LIT = 0x01
    CALL = 0x02
    EXIT = 0x03
    BRANCH = 0x04
    ZBRANCH = 0x05
    FETCH = 0x06
    STORE = 0x07
    DROP = 0x08
    DUP = 0x09
    SWAP = 0x0A
    OVER = 0x0B
    ADD = 0x0C
    SUB = 0x0D
    MUL = 0x0E
    AND = 0x0F
    OR = 0x10
    XOR = 0x11
    LESS = 0x12
    EQUAL = 0x13
    HALT = 0x14
    DO = 0x15
    LOOP = 0x16
    I = 0x17
    UNLOOP = 0x18
    PLOOP = 0x19
    J = 0x1A
    QDO = 0x1B
    LEAVE = 0x1C
    CELL_PLUS = 0x1D
    CELLS = 0x1E
    ALIGNED = 0x1F
    C_FETCH = 0x20
    C_STORE = 0x21
    CHAR_PLUS = 0x22
    CHARS = 0x23
    ICALL = 0x24
    DSET = 0x25
    SERVICE = 0x26


def cell(value: int) -> int:
    """Convert a Python integer to one unsigned 32-bit VM cell."""

    return value & CELL_MASK


def signed(value: int) -> int:
    """Interpret a VM cell as a signed two's-complement integer."""

    value = cell(value)
    return value - (1 << CELL_BITS) if value & SIGN_BIT else value


@dataclass
class LoopFrame:
    limit: int
    index: int


@dataclass
class Min0CoreForthVM:
    memory_size: int = DEFAULT_MEMORY_SIZE
    max_data_depth: int = DEFAULT_DATA_STACK_DEPTH
    max_return_depth: int = DEFAULT_RETURN_STACK_DEPTH
    max_loop_depth: int = DEFAULT_LOOP_STACK_DEPTH
    allow_defer_store: bool = False
    memory_bus: MemoryBus | None = field(default=None, repr=False)
    memory: MemoryBus = field(init=False)
    ip: int = 0
    data_stack: list[int] = field(default_factory=list)
    return_stack: list[int] = field(default_factory=list)
    loop_stack: list[LoopFrame] = field(default_factory=list)
    halted: bool = False
    steps: int = 0
    verified_boundaries: frozenset[int] | None = field(
        default=None, init=False, repr=False
    )
    verified_code_start: int | None = field(default=None, init=False)
    verified_code_end: int | None = field(default=None, init=False)
    service_registry_sealed: bool = field(default=False, init=False)
    allowed_service_ids: frozenset[int] | None = field(
        default=None, init=False, repr=False
    )
    _service_handlers: dict[int, Callable[[], None]] = field(
        default_factory=dict, init=False, repr=False
    )

    def __post_init__(self) -> None:
        if self.memory_size <= 0:
            raise ValueError("memory size must be positive")
        if min(self.max_data_depth, self.max_return_depth, self.max_loop_depth) <= 0:
            raise ValueError("stack depths must be positive")
        if self.memory_bus is None:
            self.memory_bus = FlatMemory(self.memory_size)
        elif self.memory_bus.size != self.memory_size:
            raise ValueError("memory bus size does not match memory_size")
        self.memory = self.memory_bus

    def reset(self, *, clear_memory: bool = False) -> None:
        self.ip = 0
        self.data_stack.clear()
        self.return_stack.clear()
        self.loop_stack.clear()
        self.halted = False
        self.steps = 0
        if clear_memory:
            self.memory.clear()

    def load(self, program: bytes, address: int = 0) -> None:
        self.memory.program(address, program)
        self.ip = address

    def lock_defer_store(self) -> None:
        self.allow_defer_store = False

    def register_service(self, service_id: int, handler: Callable[[], None]) -> None:
        """Register one trusted target service before execution policy is sealed."""

        if self.service_registry_sealed or self.verified_boundaries is not None:
            raise ServiceRegistrySealed("service registry is sealed")
        if (
            not isinstance(service_id, int)
            or isinstance(service_id, bool)
            or not 1 <= service_id <= CELL_MASK
        ):
            raise ServiceRegistrationError(
                "service id must be a nonzero Reference32 integer"
            )
        if not callable(handler):
            raise ServiceRegistrationError("service handler must be callable")
        if service_id in self._service_handlers:
            raise ServiceRegistrationError(
                f"service id {service_id} is already registered"
            )
        self._service_handlers[service_id] = handler

    def registered_service_ids(self) -> tuple[int, ...]:
        return tuple(sorted(self._service_handlers))

    def seal_verified_execution(
        self,
        verification: object,
        *,
        code_region: str = "CODE",
        extra_entries: Iterable[int] = (),
    ) -> None:
        """Install a one-way instruction-boundary policy and seal CODE W^X."""

        if self.verified_boundaries is not None:
            raise ExecutionPolicyError("verified execution policy is already sealed")
        if not isinstance(verification, dict):
            raise ExecutionPolicyError("verification summary must be a mapping")
        boundaries_raw = verification.get("boundaries")
        code_start = verification.get("code_start")
        code_end = verification.get("code_end")
        boundary_count = verification.get("boundary_count")
        service_ids_raw = verification.get("service_ids", [])
        if (
            not isinstance(boundaries_raw, list)
            or not isinstance(code_start, int)
            or isinstance(code_start, bool)
            or not isinstance(code_end, int)
            or isinstance(code_end, bool)
            or code_end < code_start
            or boundary_count != len(boundaries_raw)
        ):
            raise ExecutionPolicyError("verification summary is malformed")
        if not isinstance(service_ids_raw, list):
            raise ExecutionPolicyError("verified service IDs are malformed")
        service_ids: set[int] = set()
        for service_id in service_ids_raw:
            if (
                not isinstance(service_id, int)
                or isinstance(service_id, bool)
                or not 1 <= service_id <= CELL_MASK
            ):
                raise ExecutionPolicyError("verified service ID is invalid")
            service_ids.add(service_id)
        if len(service_ids) != len(service_ids_raw):
            raise ExecutionPolicyError("verified service IDs contain duplicates")
        missing_services = service_ids - set(self._service_handlers)
        if missing_services:
            raise ExecutionPolicyError(
                f"required service id {min(missing_services)} is not registered"
            )
        boundaries: set[int] = set()
        for address in boundaries_raw:
            if (
                not isinstance(address, int)
                or isinstance(address, bool)
                or not code_start <= address < code_end
            ):
                raise ExecutionPolicyError("verified boundary is outside CODE")
            boundaries.add(address)
        if len(boundaries) != len(boundaries_raw):
            raise ExecutionPolicyError("verified boundaries contain duplicates")
        extras: set[int] = set()
        for address in extra_entries:
            if not isinstance(address, int) or isinstance(address, bool):
                raise ExecutionPolicyError("extra execution entry must be an integer")
            self.memory.check_fetch(address, 1)
            extras.add(address)
        seal = getattr(self.memory, "seal_executable_region", None)
        if not callable(seal):
            raise ExecutionPolicyError(
                "verified execution sealing requires protected RegionMemory"
            )
        seal(code_region)
        self.verified_boundaries = frozenset(boundaries | extras)
        self.verified_code_start = code_start
        self.verified_code_end = code_end
        self.allowed_service_ids = frozenset(service_ids)
        self.service_registry_sealed = True

    def run(self, *, max_steps: int = 100_000, on_step=None) -> list[int]:
        start_steps = self.steps
        while not self.halted:
            if self.steps - start_steps >= max_steps:
                raise StepLimitExceeded(f"step limit {max_steps} exceeded")
            opcode_address = self.ip
            data_stack_before = list(self.data_stack)
            self.step()
            if on_step is not None:
                on_step(opcode_address, data_stack_before)
        return list(self.data_stack)

    def resume(
        self,
        address: int,
        *,
        return_to: int | None = None,
        max_steps: int = 100_000,
        on_step=None,
    ) -> list[int]:
        """Enter code while preserving data-stack and cumulative VM state.

        ``return_to`` is pushed on the return stack before entry.  The outer
        interpreter uses a HALT trampoline there when entering colon code.
        """

        self._jump(address)
        if return_to is not None:
            self._check_execution_target(return_to)
            self.memory.check_fetch(return_to, 1)
            self._push_return(return_to)
        self.halted = False
        return self.run(max_steps=max_steps, on_step=on_step)

    def step(self) -> None:
        opcode_address = self.ip
        self._check_execution_target(opcode_address)
        raw_opcode = self._read_u8()
        try:
            op = Op(raw_opcode)
        except ValueError as exc:
            raise InvalidOpcode(
                f"invalid opcode 0x{raw_opcode:02X} at 0x{opcode_address:08X}"
            ) from exc

        self.steps += 1

        if op is Op.NOP:
            return
        if op is Op.LIT:
            self.push(self._read_cell())
            return
        if op is Op.CALL:
            target = self._read_cell()
            self._push_return(self.ip)
            self._jump(target)
            return
        if op is Op.ICALL:
            slot_address = self._read_cell()
            target_xt = self.read_cell(slot_address)
            if target_xt == 0:
                raise UnassignedDefer(
                    f"unassigned DEFER slot at 0x{slot_address:08X}"
                )
            target_kind = self.read_cell(target_xt)
            if target_kind != 1:
                raise InvalidIndirectCall(
                    f"indirect XT 0x{target_xt:08X} is not a colon word"
                )
            target = self.read_cell(target_xt + CELL_BYTES)
            self._push_return(self.ip)
            self._jump(target)
            return
        if op is Op.DSET:
            slot_address = self._read_cell()
            if not self.allow_defer_store:
                raise DeferStoreDenied("compiled IS is disabled in this VM profile")
            self._require_data(1)
            if slot_address < CELL_BYTES or self.read_cell(slot_address - CELL_BYTES) != 7:
                raise InvalidIndirectCall(
                    f"DEFER store slot 0x{slot_address:08X} is invalid"
                )
            target_xt = self.data_stack[-1]
            if target_xt == 0 or self.read_cell(target_xt) != 1:
                raise InvalidIndirectCall(
                    f"DEFER target XT 0x{target_xt:08X} is not a colon word"
                )
            target = self.read_cell(target_xt + CELL_BYTES)
            self._check_execution_target(target)
            self.memory.check_fetch(target, 1)
            self.memory.check_write(slot_address, CELL_BYTES)
            self.pop()
            self.write_cell(slot_address, target_xt)
            return
        if op is Op.SERVICE:
            self._invoke_service(self._read_cell())
            return
        if op is Op.EXIT:
            if not self.return_stack:
                raise StackUnderflow("return stack underflow in EXIT")
            self._jump(self.return_stack.pop())
            return
        if op is Op.BRANCH:
            self._jump(self._read_cell())
            return
        if op is Op.ZBRANCH:
            target = self._read_cell()
            if self.pop() == 0:
                self._jump(target)
            return
        if op is Op.FETCH:
            self._require_data(1)
            value = self.read_cell(self.data_stack[-1])
            self.pop()
            self.push(value)
            return
        if op is Op.STORE:
            self._require_data(2)
            address = self.data_stack[-1]
            self.memory.check_write(address, CELL_BYTES)
            address = self.pop()
            value = self.pop()
            self.write_cell(address, value)
            return
        if op is Op.DROP:
            self.pop()
            return
        if op is Op.DUP:
            self._require_data(1)
            self.push(self.data_stack[-1])
            return
        if op is Op.SWAP:
            self._require_data(2)
            self.data_stack[-1], self.data_stack[-2] = (
                self.data_stack[-2],
                self.data_stack[-1],
            )
            return
        if op is Op.OVER:
            self._require_data(2)
            self.push(self.data_stack[-2])
            return

        if op in (Op.ADD, Op.SUB, Op.MUL, Op.AND, Op.OR, Op.XOR, Op.LESS, Op.EQUAL):
            self._require_data(2)
            right = self.pop()
            left = self.pop()
            if op is Op.ADD:
                result = left + right
            elif op is Op.SUB:
                result = left - right
            elif op is Op.MUL:
                result = left * right
            elif op is Op.AND:
                result = left & right
            elif op is Op.OR:
                result = left | right
            elif op is Op.XOR:
                result = left ^ right
            elif op is Op.LESS:
                result = CELL_MASK if signed(left) < signed(right) else 0
            else:
                result = CELL_MASK if left == right else 0
            self.push(result)
            return

        if op is Op.HALT:
            self.halted = True
            return

        if op is Op.DO:
            self._require_data(2)
            self._require_loop_capacity()
            start = self.pop()
            limit = self.pop()
            self._push_loop(limit, start)
            return
        if op is Op.LOOP:
            target = self._read_cell()
            frame = self._current_loop()
            frame.index = cell(frame.index + 1)
            if frame.index == frame.limit:
                self.loop_stack.pop()
            else:
                self._jump(target)
            return
        if op is Op.I:
            self.push(self._current_loop().index)
            return
        if op is Op.UNLOOP:
            self._current_loop()
            self.loop_stack.pop()
            return
        if op is Op.PLOOP:
            target = self._read_cell()
            self._require_data(1)
            frame = self._current_loop()
            increment = signed(self.pop())
            old_delta = signed(frame.index - frame.limit)
            frame.index = cell(frame.index + increment)
            new_delta = signed(frame.index - frame.limit)
            crossed = (
                increment > 0 and old_delta < 0 <= new_delta
            ) or (
                increment < 0 and old_delta > 0 >= new_delta
            )
            if crossed:
                self.loop_stack.pop()
            else:
                self._jump(target)
            return
        if op is Op.J:
            if len(self.loop_stack) < 2:
                raise LoopStackUnderflow("J requires two active loop frames")
            self.push(self.loop_stack[-2].index)
            return
        if op is Op.QDO:
            target = self._read_cell()
            self._require_data(2)
            start = self.data_stack[-1]
            limit = self.data_stack[-2]
            if start != limit:
                self._require_loop_capacity()
            start = self.pop()
            limit = self.pop()
            if start == limit:
                self._jump(target)
            else:
                self._push_loop(limit, start)
            return
        if op is Op.LEAVE:
            target = self._read_cell()
            self._current_loop()
            self.loop_stack.pop()
            self._jump(target)
            return
        if op is Op.CELL_PLUS:
            self.push(self.pop() + CELL_BYTES)
            return
        if op is Op.CELLS:
            self.push(self.pop() * CELL_BYTES)
            return
        if op is Op.ALIGNED:
            self.push((self.pop() + CELL_BYTES - 1) & ~(CELL_BYTES - 1))
            return
        if op is Op.C_FETCH:
            self._require_data(1)
            address = self.data_stack[-1]
            self.memory.check_read(address, 1)
            value = self.memory.read_u8(address)
            self.pop()
            self.push(value)
            return
        if op is Op.C_STORE:
            self._require_data(2)
            address = self.data_stack[-1]
            self.memory.check_write(address, 1)
            address = self.pop()
            value = self.pop()
            self.memory.write_u8(address, value)
            return
        if op is Op.CHAR_PLUS:
            self.push(self.pop() + 1)
            return
        if op is Op.CHARS:
            self._require_data(1)
            return

        raise AssertionError(f"unhandled opcode {op!r}")

    def push(self, value: int) -> None:
        if len(self.data_stack) >= self.max_data_depth:
            raise DataStackOverflow(
                f"data stack limit {self.max_data_depth} cell(s) exceeded"
            )
        self.data_stack.append(cell(value))

    def pop(self) -> int:
        self._require_data(1)
        return self.data_stack.pop()

    def read_cell(self, address: int) -> int:
        return int.from_bytes(self.memory.read(address, CELL_BYTES), "little", signed=False)

    def write_cell(self, address: int, value: int) -> None:
        self.memory.write(
            address, cell(value).to_bytes(CELL_BYTES, "little", signed=False)
        )

    def read_u8(self, address: int) -> int:
        return self.memory.read_u8(address)

    def write_u8(self, address: int, value: int) -> None:
        self.memory.write_u8(address, value)

    def read_bytes(self, address: int, size: int) -> bytes:
        return self.memory.read(address, size)

    def write_bytes(self, address: int, data: bytes) -> None:
        self.memory.write(address, data)

    def fill_bytes(self, address: int, size: int, value: int = 0) -> None:
        if value < 0 or value > 0xFF:
            raise ValueError("fill byte must be in range 0..255")
        self.memory.write(address, bytes([value]) * size)

    def _read_u8(self) -> int:
        value = self.memory.fetch_u8(self.ip)
        self.ip += 1
        return value

    def _read_cell(self) -> int:
        value = int.from_bytes(
            self.memory.fetch(self.ip, CELL_BYTES), "little", signed=False
        )
        self.ip += CELL_BYTES
        return value

    def _jump(self, address: int) -> None:
        self._check_execution_target(address)
        self.memory.check_fetch(address, 1)
        self.ip = address

    def _check_execution_target(self, address: int) -> None:
        if self.verified_boundaries is None:
            return
        if address not in self.verified_boundaries:
            raise InvalidExecutionTarget(
                f"address 0x{address:08X} is not a verified instruction boundary"
            )

    def _invoke_service(self, service_id: int) -> None:
        if (
            self.service_registry_sealed
            and self.allowed_service_ids is not None
            and service_id not in self.allowed_service_ids
        ):
            raise UnknownService(
                f"service id {service_id} is not allowed by verified CODE"
            )
        handler = self._service_handlers.get(service_id)
        if handler is None:
            raise UnknownService(f"service id {service_id} is not registered")
        handler()

    def _require_data(self, count: int) -> None:
        if len(self.data_stack) < count:
            raise StackUnderflow(
                f"data stack needs {count} cell(s), has {len(self.data_stack)}"
            )

    def _push_return(self, value: int) -> None:
        if len(self.return_stack) >= self.max_return_depth:
            raise ReturnStackOverflow(
                f"return stack limit {self.max_return_depth} cell(s) exceeded"
            )
        self.return_stack.append(cell(value))

    def _push_loop(self, limit: int, index: int) -> None:
        self._require_loop_capacity()
        self.loop_stack.append(LoopFrame(cell(limit), cell(index)))

    def _require_loop_capacity(self) -> None:
        if len(self.loop_stack) >= self.max_loop_depth:
            raise LoopStackOverflow(
                f"loop stack limit {self.max_loop_depth} frame(s) exceeded"
            )

    def _current_loop(self) -> LoopFrame:
        if not self.loop_stack:
            raise LoopStackUnderflow("loop stack is empty")
        return self.loop_stack[-1]

    def _check_range(self, address: int, size: int) -> None:
        self.memory.check_read(address, size)


class Assembler:
    """Small label-aware assembler used to specify executable VM examples."""

    def __init__(self) -> None:
        self.code = bytearray()
        self.labels: dict[str, int] = {}
        self.fixups: list[tuple[int, str]] = []

    @property
    def address(self) -> int:
        return len(self.code)

    def label(self, name: str) -> None:
        if name in self.labels:
            raise ValueError(f"duplicate label {name!r}")
        self.labels[name] = self.address

    def emit(self, op: Op, operand: int | str | None = None) -> None:
        self.code.append(int(op))
        if operand is not None:
            if op not in (
                Op.LIT, Op.CALL, Op.ICALL, Op.DSET, Op.BRANCH, Op.ZBRANCH, Op.LOOP,
                Op.PLOOP, Op.QDO, Op.LEAVE, Op.SERVICE,
            ):
                raise ValueError(f"{op.name} does not accept an operand")
            if isinstance(operand, str):
                self.fixups.append((self.address, operand))
                value = 0
            else:
                value = operand
            self.code.extend(cell(value).to_bytes(CELL_BYTES, "little"))
        elif op in (
            Op.LIT, Op.CALL, Op.ICALL, Op.DSET, Op.BRANCH, Op.ZBRANCH, Op.LOOP,
            Op.PLOOP, Op.QDO, Op.LEAVE, Op.SERVICE,
        ):
            raise ValueError(f"{op.name} requires an operand")

    def build(self) -> bytes:
        result = bytearray(self.code)
        for offset, label in self.fixups:
            try:
                value = self.labels[label]
            except KeyError as exc:
                raise ValueError(f"unknown label {label!r}") from exc
            result[offset : offset + CELL_BYTES] = value.to_bytes(CELL_BYTES, "little")
        return bytes(result)


def assemble(items: Iterable[tuple[Op, int | str | None]]) -> bytes:
    assembler = Assembler()
    for op, operand in items:
        assembler.emit(op, operand)
    return assembler.build()
