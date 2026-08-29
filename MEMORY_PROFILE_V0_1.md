# MIN0 CORE FORTH Memory Profile v0.1

Status: executable design draft. This document separates the CPU-independent
memory contract from the current 64 KiB reference machine.

## 1. Core rule

MIN0 CORE FORTH addresses are logical byte addresses. A target maps those logical
addresses to physical ROM, Flash, EEPROM, FRAM, SRAM, MMIO, or another storage
technology. The 64 KiB flat memory used by the executable draft is one
reference profile; it is not a minimum or maximum imposed by MIN0 CORE FORTH.

An address is meaningful together with an access operation. Instruction fetch,
data read, and data write are distinct operations even when a flat target maps
all three to the same physical byte.

## 2. Required memory-bus operations

The execution engine uses these operations:

- `fetch(address, size)` and `fetch_u8(address)` for opcodes and immediate data
- `read(address, size)` and `read_u8(address)` for `@` and `C@`
- `write(address, bytes)` and `write_u8(address, value)` for `!` and `C!`
- `program(address, bytes)` for host-side image loading; this may access a
  region explicitly marked programmable but is not exposed as ordinary `!`
- `check_fetch`, `check_read`, and `check_write` when an operation must be
  validated before stack arguments are consumed
- `clear` for development-machine reset; a persistent target may define a
  more selective reset above this interface

Every failed operation raises a deterministic memory fault. A VM instruction
must validate its complete access before consuming stack arguments. Multi-byte
cells never wrap around the end of a region.

Cell encoding remains a VM-profile property. Reference32 reads and writes
32-bit little-endian cells using the byte operations above.

## 3. Logical roles

A target may provide any compatible map, but its platform profile should name
the roles below when present:

| Role | Typical storage | Normal access |
| --- | --- | --- |
| `CODE` | ROM or Flash | fetch, optional read |
| `RODATA` | ROM or Flash | read |
| `DICTIONARY` | SRAM, EEPROM, FRAM, or Flash | read/write while extending |
| `DATA` | SRAM | read/write |
| `STACK` | internal SRAM | VM-private read/write |
| `NVM-DATA` | EEPROM or FRAM | persistent read/write |
| `MMIO` | device registers | target-defined read/write |

The roles are not required to be physically adjacent. A dictionary header,
the code executed by its XT, and the body address returned by `CREATE` may all
reside in different regions.

## 4. Harvard and split-memory targets

Fetch and data access are deliberately separate so that a Harvard target can
map a code address to program memory without pretending that program memory is
ordinary writable RAM. A target must document whether `@` can read `CODE`.
Writing a ROM/Flash code region through ordinary `!` or `C!` must fault unless
the target explicitly provides a controlled programming service.

No core definition may assume that a word body is adjacent to its executable
code. Dictionary entries therefore carry logical addresses rather than
deriving every location from physical adjacency.

## 5. Reference32-Flat64K profile

The current executable implementation supplies `FlatMemory`:

- logical range `0x00000000` through `0x0000FFFF`
- every byte is fetchable, readable, and writable
- volatile zero-filled storage
- 32-bit little-endian cells and 32-bit logical addresses
- sequence/String compatibility temporarily retained while dictionary and
  compiler code are migrated to explicit bus operations

This profile preserves every existing bytecode image and test. Its permissive
access rights are for reference and development, not a security or hardware
requirement.

## 6. RegionMemory executable prototype

Python and Ruby also supply `RegionMemory`. A map contains named,
non-overlapping regions with any combination of these permissions:

- `r`: data read
- `w`: ordinary data write
- `x`: instruction fetch
- `programmable`: host image loading even when ordinary write is denied

Every multi-byte operation must fit completely inside one region. An operation
that crosses a boundary, enters a gap, or lacks permission raises a memory
fault. `VM.load` uses the controlled `program` operation, while Forth `!` and
`C!` continue to use ordinary write permission.

The current cross-language test executes code from a programmable `rx` region,
stores and fetches a cell in an `rw` region, and verifies faults for code write,
data execution, a boundary-crossing cell, and an unmapped address.

`SEALED_EXECUTION_R0.md` adds a one-way runtime transition. After bytecode
verification, the CODE region becomes `rx`, loses `programmable`, and cannot be
cleared or reopened. The VM also retains verified instruction boundaries and
checks every direct, indirect, return, and resume target.

`seal_read_only_region` supplies the corresponding one-way transition for loaded
data such as immutable string literals. The region becomes exactly `r`, loses
`programmable`, and blocks ordinary write, host reprogramming, and whole-memory
clear while remaining available to `TYPE`. The compiled-string relocation test
moves DATA from `0x8000` to `0x9000` and executes the relocated literal after this
seal in both Python and Ruby.

The prototype deliberately forbids overlapping logical regions. A later
Harvard profile may allow operation-specific overlapping maps.

## 7. Planned profiles

- `Tiny16`: smaller address/cell encoding for constrained MPUs
- `Split-Dictionary`: separately allocated dictionary headers, code, and bodies
- `Harvard`: different fetch and data maps
- `Persistent`: append-oriented dictionary storage with atomic publication

Flash/EEPROM implementations must additionally specify erase granularity,
write endurance policy, interrupted-write recovery, and dictionary commit
rules. An incomplete definition must remain hidden after reset.

Region allocation and wear-leveling are services above the byte bus and are
not fixed by v0.1.
