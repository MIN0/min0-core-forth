"""Runtime dictionary stored inside MIN0 CORE FORTH VM memory (draft v0.1)."""

from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass

from min0_core_forth_vm import Min0CoreForthVM, Op


DICTIONARY_BASE = 0x8000
ALIGNMENT = 4
MAX_NAME_BYTES = 31

FLAG_IMMEDIATE = 0x01
FLAG_HIDDEN = 0x02

KIND_PRIMITIVE = 0
KIND_COLON = 1
KIND_CONSTANT = 2
KIND_VARIABLE = 3
KIND_CREATED = 4
KIND_DOES = 5
KIND_DEFINER = 6
KIND_DEFER = 7

DOES_DESCRIPTOR_BYTES = 8
DEFINER_DESCRIPTOR_BYTES = 8
CONSTRUCTOR_PLAN_MAGIC = 0x4E4C5043  # "CPLN" in little-endian memory
CONSTRUCTOR_PLAN_VERSION = 1
CONSTRUCTOR_ACTION_END = 0
CONSTRUCTOR_ACTION_COMMA = 1
CONSTRUCTOR_ACTION_C_COMMA = 2
CONSTRUCTOR_ACTION_ALLOT = 3
CONSTRUCTOR_ACTION_ALIGN = 4
CONSTRUCTOR_ACTIONS = frozenset(
    {
        CONSTRUCTOR_ACTION_END,
        CONSTRUCTOR_ACTION_COMMA,
        CONSTRUCTOR_ACTION_C_COMMA,
        CONSTRUCTOR_ACTION_ALLOT,
        CONSTRUCTOR_ACTION_ALIGN,
    }
)


class DictionaryError(ValueError):
    pass


class DictionaryFull(DictionaryError):
    pass


class InvalidDictionary(DictionaryError):
    pass


@dataclass(frozen=True)
class DictionaryEntry:
    header_address: int
    link: int
    flags: int
    name: str
    xt: int
    kind: int
    payload: int

    @property
    def immediate(self) -> bool:
        return bool(self.flags & FLAG_IMMEDIATE)

    @property
    def hidden(self) -> bool:
        return bool(self.flags & FLAG_HIDDEN)


class RuntimeDictionary:
    """A linked Forth dictionary that grows upward in VM byte memory."""

    def __init__(
        self,
        vm: Min0CoreForthVM,
        *,
        base: int = DICTIONARY_BASE,
        limit: int | None = None,
        body_base: int | None = None,
        body_limit: int | None = None,
    ) -> None:
        self.vm = vm
        self.base = base
        self.limit = vm.memory_size if limit is None else limit
        if base <= 0 or base % ALIGNMENT:
            raise DictionaryError("dictionary base must be nonzero and 4-byte aligned")
        if self.limit < base or self.limit > vm.memory_size:
            raise DictionaryError("dictionary limit is outside VM memory")
        self.here = base
        self.split_body = body_base is not None
        if self.split_body:
            assert body_base is not None
            self.body_base = body_base
            self.body_limit = vm.memory_size if body_limit is None else body_limit
            if body_base < 0 or body_base % ALIGNMENT:
                raise DictionaryError("body base must be 4-byte aligned")
            if self.body_limit < body_base or self.body_limit > vm.memory_size:
                raise DictionaryError("body limit is outside VM memory")
            if not (self.body_limit <= base or body_base >= self.limit):
                raise DictionaryError("dictionary header and body ranges overlap")
            self._body_here = body_base
        else:
            if body_limit is not None:
                raise DictionaryError("body_limit requires body_base")
            self.body_base = base
            self.body_limit = self.limit
            self._body_here = base
        self.latest = 0
        self._defer_authority: object | None = None
        self._runtime_structure_sealed = False
        self._dictionary_region_name: str | None = None
        self._defer_write_authority: object | None = None

    @property
    def data_here(self) -> int:
        """HERE for data-space words; equal to header HERE in flat mode."""

        return self._body_here if self.split_body else self.here

    def add_primitive(
        self,
        name: str,
        opcode: Op | int,
        *,
        immediate: bool = False,
        hidden: bool = False,
    ) -> DictionaryEntry:
        self._require_structure_mutable()
        value = int(opcode)
        try:
            Op(value)
        except ValueError as exc:
            raise DictionaryError(f"invalid primitive opcode 0x{value:02X}") from exc
        return self._add(
            name,
            kind=KIND_PRIMITIVE,
            payload=value,
            immediate=immediate,
            hidden=hidden,
        )

    def add_colon(
        self,
        name: str,
        code_address: int,
        *,
        immediate: bool = False,
        hidden: bool = False,
    ) -> DictionaryEntry:
        self._require_structure_mutable()
        if code_address < 0 or code_address >= self.vm.memory_size:
            raise DictionaryError("colon code address is outside VM memory")
        return self._add(
            name,
            kind=KIND_COLON,
            payload=code_address,
            immediate=immediate,
            hidden=hidden,
        )

    def add_constant(
        self,
        name: str,
        value: int,
        *,
        immediate: bool = False,
        hidden: bool = False,
    ) -> DictionaryEntry:
        self._require_structure_mutable()
        return self._add(
            name,
            kind=KIND_CONSTANT,
            payload=value,
            immediate=immediate,
            hidden=hidden,
        )

    def add_defer(
        self,
        name: str,
        target: DictionaryEntry | None = None,
        *,
        immediate: bool = False,
        hidden: bool = False,
    ) -> DictionaryEntry:
        """Add a dynamic call slot, optionally assigned to a colon word."""

        self._require_structure_mutable()
        self._require_defer_authority(None)
        target_xt = 0 if target is None else self._defer_xt_target(target)
        return self._add(
            name,
            kind=KIND_DEFER,
            payload=target_xt,
            immediate=immediate,
            hidden=hidden,
        )

    def set_defer(
        self,
        entry: DictionaryEntry,
        target: DictionaryEntry,
        *,
        authorization: object | None = None,
    ) -> DictionaryEntry:
        """Atomically replace the target of one DEFER entry."""

        self._require_defer_authority(authorization)
        current = self.read_entry(entry.header_address)
        if current.kind != KIND_DEFER:
            raise DictionaryError("IS requires a DEFER word")
        target_xt = self._defer_xt_target(target)
        scope = nullcontext()
        if self._runtime_structure_sealed:
            assert self._dictionary_region_name is not None
            assert self._defer_write_authority is not None
            scope = self.vm.memory.authorized_writes(
                self._dictionary_region_name, self._defer_write_authority
            )
        with scope:
            self.vm.memory.check_write(current.xt + 4, 4)
            self.vm.write_cell(current.xt + 4, target_xt)
        return self.read_entry(current.header_address)

    @property
    def runtime_structure_sealed(self) -> bool:
        return self._runtime_structure_sealed

    def seal_runtime_structure(self, region_name: str = "DICTIONARY") -> None:
        """Freeze headers/allocators and permit only checked DEFER-slot writes."""

        if self._runtime_structure_sealed:
            raise DictionaryError("runtime dictionary structure is already sealed")
        memory = self.vm.memory
        protect = getattr(memory, "protect_region_writes", None)
        authorize = getattr(memory, "authorized_writes", None)
        regions = getattr(memory, "regions", None)
        if not callable(protect) or not callable(authorize) or not isinstance(regions, list):
            raise DictionaryError(
                "runtime dictionary sealing requires protected RegionMemory"
            )
        region = next((item for item in regions if item.name == region_name), None)
        if region is None or self.base < region.start or self.limit > region.end:
            raise DictionaryError("dictionary allocator is outside protected region")
        token = object()
        protect(region_name, [token])
        self._dictionary_region_name = region_name
        self._defer_write_authority = token
        self._runtime_structure_sealed = True

    def lock_defer_updates(self, authorization: object) -> None:
        if authorization is None:
            raise DictionaryError("DEFER authorization marker must not be null")
        if self._defer_authority is not None:
            raise DictionaryError("DEFER updates are already controlled")
        self._defer_authority = authorization

    def _require_defer_authority(self, authorization: object | None) -> None:
        if self._runtime_structure_sealed and self._defer_authority is None:
            raise DictionaryError("DEFER update requires Monitor authorization")
        if self._defer_authority is not None and authorization is not self._defer_authority:
            raise DictionaryError("DEFER update requires Monitor authorization")

    def _require_structure_mutable(self) -> None:
        if self._runtime_structure_sealed:
            raise DictionaryError("runtime dictionary structure is sealed")

    def read_defer_target(self, entry: DictionaryEntry) -> int:
        current = self.read_entry(entry.header_address)
        if current.kind != KIND_DEFER:
            raise DictionaryError("word is not DEFERred")
        if current.payload:
            target = self.entry_for_xt(current.payload)
            if target.kind != KIND_COLON:
                raise InvalidDictionary("DEFER target XT is not a colon word")
            try:
                self.vm.memory.check_fetch(target.payload, 1)
            except Exception as exc:
                raise InvalidDictionary("DEFER target is not executable") from exc
        return current.payload

    def _defer_xt_target(self, target: DictionaryEntry) -> int:
        current = self.read_entry(target.header_address)
        if current.kind != KIND_COLON:
            raise DictionaryError("DEFER R0 target must be a colon word")
        try:
            self.vm.memory.check_fetch(current.payload, 1)
        except Exception as exc:
            raise DictionaryError("DEFER target is not executable") from exc
        return current.xt

    def entry_for_xt(self, xt: int) -> DictionaryEntry:
        for entry in self.entries(include_hidden=True):
            if entry.xt == xt:
                return entry
        raise InvalidDictionary(f"unknown execution token 0x{xt:08X}")

    def add_variable(
        self,
        name: str,
        *,
        immediate: bool = False,
        hidden: bool = False,
    ) -> DictionaryEntry:
        self._require_structure_mutable()
        saved_here = self.here
        saved_data_here = self.data_here
        saved_latest = self.latest
        try:
            if self.split_body:
                data_address = self.align_here()
            else:
                data_address = self._data_field_address(name)
            entry = self._add(
                name,
                kind=KIND_VARIABLE,
                payload=data_address,
                immediate=immediate,
                hidden=hidden,
            )
            if self.comma(0) != data_address:
                raise AssertionError("variable data-field address mismatch")
            return entry
        except Exception:
            self.restore(
                here=saved_here, latest=saved_latest, data_here=saved_data_here
            )
            raise

    def add_created(
        self,
        name: str,
        *,
        immediate: bool = False,
        hidden: bool = False,
    ) -> DictionaryEntry:
        self._require_structure_mutable()
        saved_here = self.here
        saved_data_here = self.data_here
        saved_latest = self.latest
        try:
            payload = (
                self.align_here()
                if self.split_body
                else self._data_field_address(name)
            )
            return self._add(
                name,
                kind=KIND_CREATED,
                payload=payload,
                immediate=immediate,
                hidden=hidden,
            )
        except Exception:
            self.restore(
                here=saved_here, latest=saved_latest, data_here=saved_data_here
            )
            raise

    def set_does(
        self, entry: DictionaryEntry, code_address: int
    ) -> DictionaryEntry:
        """Turn one CREATEd word into a DOES>-style executable word.

        The fixed eight-byte XT remains unchanged in size.  Its payload points
        to an eight-byte descriptor in dictionary space containing, in order,
        the body address and the behavior code address.
        """

        self._require_structure_mutable()
        current = self.read_entry(entry.header_address)
        if current.kind != KIND_CREATED:
            raise DictionaryError("DOES behavior requires a CREATEd word")
        if code_address < 0 or code_address >= self.vm.memory_size:
            raise DictionaryError("DOES code address is outside VM memory")
        try:
            self.vm.memory.check_fetch(code_address, 1)
        except Exception as exc:
            raise DictionaryError("DOES code address is not executable") from exc

        descriptor = _align(self.here)
        next_here = descriptor + DOES_DESCRIPTOR_BYTES
        if next_here > self.limit:
            raise DictionaryFull(
                f"DOES descriptor exceeds limit 0x{self.limit:08X}"
            )

        # Check every destination before changing either the descriptor or XT.
        self.vm.memory.check_write(self.here, next_here - self.here)
        self.vm.memory.check_write(current.xt, 8)
        old_here = self.here
        old_xt = self.vm.read_bytes(current.xt, 8)
        old_descriptor = self.vm.read_bytes(old_here, next_here - old_here)
        try:
            self.vm.fill_bytes(old_here, descriptor - old_here)
            self.vm.write_cell(descriptor, current.payload)
            self.vm.write_cell(descriptor + 4, code_address)
            self.vm.write_cell(current.xt, KIND_DOES)
            self.vm.write_cell(current.xt + 4, descriptor)
            self.here = next_here
            return self.read_entry(current.header_address)
        except Exception:
            self.vm.write_bytes(current.xt, old_xt)
            self.vm.write_bytes(old_here, old_descriptor)
            self.here = old_here
            raise

    def read_does_descriptor(self, entry: DictionaryEntry) -> tuple[int, int]:
        """Return ``(body_address, code_address)`` for a DOES word."""

        current = self.read_entry(entry.header_address)
        if current.kind != KIND_DOES:
            raise DictionaryError("word has no DOES descriptor")
        descriptor = current.payload
        if (
            descriptor < self.base
            or descriptor % ALIGNMENT
            or descriptor + DOES_DESCRIPTOR_BYTES > self.here
        ):
            raise InvalidDictionary("invalid DOES descriptor address")
        body_address = self.vm.read_cell(descriptor)
        code_address = self.vm.read_cell(descriptor + 4)
        try:
            self.vm.memory.check_fetch(code_address, 1)
        except Exception as exc:
            raise InvalidDictionary("DOES code address is not executable") from exc
        return body_address, code_address

    def set_definer(
        self,
        entry: DictionaryEntry,
        constructor_steps: int | list[tuple[int, int]],
        behavior_address: int = 0,
    ) -> DictionaryEntry:
        """Turn a colon entry into a source-level defining word.

        The descriptor stores a constructor-plan address followed by optional
        DOES behavior code.  Passing one integer creates a one-step END plan.
        """

        self._require_structure_mutable()
        current = self.read_entry(entry.header_address)
        if current.kind != KIND_COLON:
            raise DictionaryError("defining-word metadata requires a colon word")
        steps = (
            [(constructor_steps, CONSTRUCTOR_ACTION_END)]
            if isinstance(constructor_steps, int)
            else list(constructor_steps)
        )
        if not steps:
            raise DictionaryError("constructor plan must contain at least one step")
        for index, (address, action) in enumerate(steps):
            if address < 0 or address >= self.vm.memory_size:
                raise DictionaryError("constructor code address is outside VM memory")
            try:
                self.vm.memory.check_fetch(address, 1)
            except Exception as exc:
                raise DictionaryError("constructor code address is not executable") from exc
            if action not in CONSTRUCTOR_ACTIONS:
                raise DictionaryError(f"unknown constructor action {action}")
            if (action == CONSTRUCTOR_ACTION_END) != (index == len(steps) - 1):
                raise DictionaryError("constructor END must be the final plan action")
        if behavior_address:
            if behavior_address < 0 or behavior_address >= self.vm.memory_size:
                raise DictionaryError("definer behavior address is outside VM memory")
            try:
                self.vm.memory.check_fetch(behavior_address, 1)
            except Exception as exc:
                raise DictionaryError("definer behavior address is not executable") from exc

        plan = _align(self.here)
        plan_bytes = 12 + len(steps) * 8
        descriptor = _align(plan + plan_bytes)
        next_here = descriptor + DEFINER_DESCRIPTOR_BYTES
        if next_here > self.limit:
            raise DictionaryFull(
                f"constructor plan exceeds limit 0x{self.limit:08X}"
            )
        self.vm.memory.check_write(self.here, next_here - self.here)
        self.vm.memory.check_write(current.xt, 8)
        old_here = self.here
        old_xt = self.vm.read_bytes(current.xt, 8)
        old_metadata = self.vm.read_bytes(old_here, next_here - old_here)
        try:
            self.vm.fill_bytes(old_here, plan - old_here)
            self.vm.write_cell(plan, CONSTRUCTOR_PLAN_MAGIC)
            self.vm.write_cell(plan + 4, CONSTRUCTOR_PLAN_VERSION)
            self.vm.write_cell(plan + 8, len(steps))
            cursor = plan + 12
            for code_address, action in steps:
                self.vm.write_cell(cursor, code_address)
                self.vm.write_cell(cursor + 4, action)
                cursor += 8
            self.vm.fill_bytes(cursor, descriptor - cursor)
            self.vm.write_cell(descriptor, plan)
            self.vm.write_cell(descriptor + 4, behavior_address)
            self.vm.write_cell(current.xt, KIND_DEFINER)
            self.vm.write_cell(current.xt + 4, descriptor)
            self.here = next_here
            return self.read_entry(current.header_address)
        except Exception:
            self.vm.write_bytes(current.xt, old_xt)
            self.vm.write_bytes(old_here, old_metadata)
            self.here = old_here
            raise

    def read_definer_descriptor(self, entry: DictionaryEntry) -> tuple[int, int]:
        """Return ``(plan_address, behavior_address)`` for a definer."""

        current = self.read_entry(entry.header_address)
        if current.kind != KIND_DEFINER:
            raise DictionaryError("word has no definer descriptor")
        descriptor = current.payload
        if (
            descriptor < self.base
            or descriptor % ALIGNMENT
            or descriptor + DEFINER_DESCRIPTOR_BYTES > self.here
        ):
            raise InvalidDictionary("invalid definer descriptor address")
        plan_address = self.vm.read_cell(descriptor)
        behavior_address = self.vm.read_cell(descriptor + 4)
        self._read_constructor_plan_at(plan_address, descriptor)
        if behavior_address:
            try:
                self.vm.memory.check_fetch(behavior_address, 1)
            except Exception as exc:
                raise InvalidDictionary("definer behavior address is not executable") from exc
        return plan_address, behavior_address

    def read_constructor_plan(
        self, entry: DictionaryEntry
    ) -> list[tuple[int, int]]:
        """Decode and validate one dictionary-resident constructor plan."""

        current = self.read_entry(entry.header_address)
        if current.kind != KIND_DEFINER:
            raise DictionaryError("word has no constructor plan")
        descriptor = current.payload
        if (
            descriptor < self.base
            or descriptor % ALIGNMENT
            or descriptor + DEFINER_DESCRIPTOR_BYTES > self.here
        ):
            raise InvalidDictionary("invalid definer descriptor address")
        plan_address = self.vm.read_cell(descriptor)
        return self._read_constructor_plan_at(plan_address, descriptor)

    def _read_constructor_plan_at(
        self, plan_address: int, descriptor_address: int
    ) -> list[tuple[int, int]]:
        if (
            plan_address < self.base
            or plan_address % ALIGNMENT
            or plan_address + 12 > descriptor_address
        ):
            raise InvalidDictionary("invalid constructor plan address")
        if self.vm.read_cell(plan_address) != CONSTRUCTOR_PLAN_MAGIC:
            raise InvalidDictionary("invalid constructor plan magic")
        if self.vm.read_cell(plan_address + 4) != CONSTRUCTOR_PLAN_VERSION:
            raise InvalidDictionary("unsupported constructor plan version")
        count = self.vm.read_cell(plan_address + 8)
        if count == 0 or plan_address + 12 + count * 8 > descriptor_address:
            raise InvalidDictionary("invalid constructor plan length")
        result: list[tuple[int, int]] = []
        cursor = plan_address + 12
        for index in range(count):
            code_address = self.vm.read_cell(cursor)
            action = self.vm.read_cell(cursor + 4)
            try:
                self.vm.memory.check_fetch(code_address, 1)
            except Exception as exc:
                raise InvalidDictionary("constructor code address is not executable") from exc
            if action not in CONSTRUCTOR_ACTIONS:
                raise InvalidDictionary(f"unknown constructor action {action}")
            if (action == CONSTRUCTOR_ACTION_END) != (index == count - 1):
                raise InvalidDictionary("constructor END must be the final plan action")
            result.append((code_address, action))
            cursor += 8
        return result

    def comma(self, value: int) -> int:
        """Align HERE, store one cell, and return its VM byte address."""

        address = _align(self.data_here)
        self._reserve_to(address + 4)
        self.vm.write_cell(address, value)
        return address

    def c_comma(self, value: int) -> int:
        """Store the low eight bits at exact HERE and advance one byte."""

        address = self.data_here
        self._reserve_to(self.data_here + 1)
        self.vm.write_u8(address, value)
        return address

    def allot(self, byte_count: int) -> int:
        """Reserve nonnegative bytes and return the previous HERE value."""

        if byte_count < 0:
            raise DictionaryError("ALLOT byte count must be nonnegative in v0.1")
        address = self.data_here
        self._reserve_to(self.data_here + byte_count)
        return address

    def align_here(self) -> int:
        """Advance HERE to the next cell boundary and return it."""

        address = _align(self.data_here)
        self._reserve_to(address)
        return address

    def find(self, name: str, *, include_hidden: bool = False) -> DictionaryEntry | None:
        wanted = self._encode_name(name)
        address = self.latest
        visited: set[int] = set()
        while address:
            if address in visited:
                raise InvalidDictionary("dictionary link cycle detected")
            visited.add(address)
            entry = self.read_entry(address)
            if (include_hidden or not entry.hidden) and entry.name.encode("ascii") == wanted:
                return entry
            address = entry.link
        return None

    def entries(self, *, include_hidden: bool = True) -> list[DictionaryEntry]:
        result: list[DictionaryEntry] = []
        address = self.latest
        visited: set[int] = set()
        while address:
            if address in visited:
                raise InvalidDictionary("dictionary link cycle detected")
            visited.add(address)
            entry = self.read_entry(address)
            if include_hidden or not entry.hidden:
                result.append(entry)
            address = entry.link
        return result

    def read_entry(self, address: int) -> DictionaryEntry:
        if address < self.base or address + 8 > self.here or address % ALIGNMENT:
            raise InvalidDictionary(f"invalid dictionary header 0x{address:08X}")
        link = self.vm.read_cell(address)
        flags = self.vm.read_u8(address + 4)
        name_length = self.vm.read_u8(address + 5)
        reserved = int.from_bytes(self.vm.read_bytes(address + 6, 2), "little")
        if reserved != 0:
            raise InvalidDictionary("dictionary reserved field is not zero")
        if name_length == 0 or name_length > MAX_NAME_BYTES:
            raise InvalidDictionary(f"invalid dictionary name length {name_length}")
        name_end = address + 8 + name_length
        xt = _align(name_end)
        if xt + 8 > self.here:
            raise InvalidDictionary("dictionary entry extends beyond HERE")
        raw_name = self.vm.read_bytes(address + 8, name_length)
        try:
            name = raw_name.decode("ascii")
        except UnicodeDecodeError as exc:
            raise InvalidDictionary("dictionary name is not ASCII") from exc
        kind = self.vm.read_cell(xt)
        payload = self.vm.read_cell(xt + 4)
        if kind not in (
            KIND_PRIMITIVE,
            KIND_COLON,
            KIND_CONSTANT,
            KIND_VARIABLE,
            KIND_CREATED,
            KIND_DOES,
            KIND_DEFINER,
            KIND_DEFER,
        ):
            raise InvalidDictionary(f"unknown dictionary kind {kind}")
        return DictionaryEntry(address, link, flags, name, xt, kind, payload)

    def image(self) -> bytes:
        return self.vm.read_bytes(self.base, self.here - self.base)

    def body_image(self) -> bytes:
        return self.vm.read_bytes(self.body_base, self.data_here - self.body_base)

    def load_images(
        self,
        header_image: bytes,
        *,
        latest: int,
        body_image: bytes = b"",
    ) -> None:
        """Adopt raw dictionary/body bytes into a new empty dictionary.

        This is a component loader, not a persistent-image file format.  CODE
        bytes must already be present so executable metadata can be validated.
        """

        self._require_structure_mutable()
        if self.here != self.base or self.latest != 0 or self.data_here != self.body_base:
            raise DictionaryError("dictionary image loading requires an empty dictionary")
        headers = bytes(header_image)
        body = bytes(body_image)
        next_here = self.base + len(headers)
        if next_here > self.limit:
            raise InvalidDictionary("dictionary image exceeds header limit")
        if bool(headers) != bool(latest):
            raise InvalidDictionary("dictionary image and LATEST disagree")
        if latest and (
            latest < self.base or latest >= next_here or latest % ALIGNMENT
        ):
            raise InvalidDictionary("dictionary image has invalid LATEST")
        if self.split_body:
            next_data_here = self.body_base + len(body)
            if next_data_here > self.body_limit:
                raise InvalidDictionary("dictionary image exceeds body limit")
        else:
            if body:
                raise InvalidDictionary("flat dictionary cannot load a separate body image")
            next_data_here = next_here

        self.vm.memory.check_write(self.base, len(headers))
        if self.split_body:
            self.vm.memory.check_write(self.body_base, len(body))
        old_headers = self.vm.read_bytes(self.base, len(headers))
        old_body = (
            self.vm.read_bytes(self.body_base, len(body)) if self.split_body else b""
        )
        try:
            self.vm.write_bytes(self.base, headers)
            if self.split_body:
                self.vm.write_bytes(self.body_base, body)
            self.here = next_here
            self.latest = latest
            if self.split_body:
                self._body_here = next_data_here
            for entry in self.entries():
                if entry.kind == KIND_DEFINER:
                    self.read_definer_descriptor(entry)
                elif entry.kind == KIND_DOES:
                    self.read_does_descriptor(entry)
                elif entry.kind == KIND_DEFER:
                    self.read_defer_target(entry)
        except Exception:
            self.vm.write_bytes(self.base, old_headers)
            if self.split_body:
                self.vm.write_bytes(self.body_base, old_body)
                self._body_here = self.body_base
            self.here = self.base
            self.latest = 0
            raise

    def set_hidden(self, entry: DictionaryEntry, hidden: bool) -> DictionaryEntry:
        """Change only the hidden flag of an existing dictionary entry."""

        self._require_structure_mutable()
        current = self.read_entry(entry.header_address)
        flags = current.flags | FLAG_HIDDEN if hidden else current.flags & ~FLAG_HIDDEN
        self.vm.write_u8(current.header_address + 4, flags)
        return self.read_entry(current.header_address)

    def restore(
        self, *, here: int, latest: int, data_here: int | None = None
    ) -> None:
        """Roll back entries added after a previously recorded state."""

        self._require_structure_mutable()
        if here < self.base or here > self.here:
            raise DictionaryError("invalid dictionary rollback HERE")
        if latest != 0 and (latest < self.base or latest >= here or latest % ALIGNMENT):
            raise DictionaryError("invalid dictionary rollback LATEST")
        if self.split_body:
            if data_here is None:
                raise DictionaryError("split dictionary rollback requires data HERE")
            if data_here < self.body_base or data_here > self.data_here:
                raise DictionaryError("invalid dictionary rollback data HERE")
        self.vm.fill_bytes(here, self.here - here)
        if self.split_body:
            assert data_here is not None
            self.vm.fill_bytes(data_here, self.data_here - data_here)
            self._body_here = data_here
        self.here = here
        self.latest = latest

    def _add(
        self,
        name: str,
        *,
        kind: int,
        payload: int,
        immediate: bool,
        hidden: bool,
    ) -> DictionaryEntry:
        self._require_structure_mutable()
        encoded_name = self._encode_name(name)
        header = _align(self.here)
        xt = _align(header + 8 + len(encoded_name))
        next_here = xt + 8
        if next_here > self.limit:
            raise DictionaryFull(
                f"dictionary entry {encoded_name.decode()!r} exceeds limit 0x{self.limit:08X}"
            )
        flags = (FLAG_IMMEDIATE if immediate else 0) | (FLAG_HIDDEN if hidden else 0)
        self.vm.fill_bytes(self.here, header - self.here)
        self.vm.write_cell(header, self.latest)
        self.vm.write_u8(header + 4, flags)
        self.vm.write_u8(header + 5, len(encoded_name))
        self.vm.fill_bytes(header + 6, 2)
        self.vm.write_bytes(header + 8, encoded_name)
        padding_start = header + 8 + len(encoded_name)
        self.vm.fill_bytes(padding_start, xt - padding_start)
        self.vm.write_cell(xt, kind)
        self.vm.write_cell(xt + 4, payload)
        self.here = next_here
        self.latest = header
        return self.read_entry(header)

    def _reserve_to(self, next_here: int) -> None:
        self._require_structure_mutable()
        current = self.data_here
        limit = self.body_limit if self.split_body else self.limit
        if next_here > limit:
            raise DictionaryFull(
                f"dictionary data exceeds limit 0x{limit:08X}"
            )
        self.vm.fill_bytes(current, next_here - current)
        if self.split_body:
            self._body_here = next_here
        else:
            self.here = next_here

    def _data_field_address(self, name: str) -> int:
        encoded_name = self._encode_name(name)
        header = _align(self.here)
        xt = _align(header + 8 + len(encoded_name))
        return xt + 8

    @staticmethod
    def _encode_name(name: str) -> bytes:
        canonical = name.upper()
        try:
            encoded = canonical.encode("ascii")
        except UnicodeEncodeError as exc:
            raise DictionaryError("v0.1 dictionary names must be ASCII") from exc
        if not encoded or len(encoded) > MAX_NAME_BYTES or any(chr(byte).isspace() for byte in encoded):
            raise DictionaryError("dictionary name must contain 1..31 non-space ASCII bytes")
        return encoded


def _align(address: int) -> int:
    return (address + ALIGNMENT - 1) & ~(ALIGNMENT - 1)
