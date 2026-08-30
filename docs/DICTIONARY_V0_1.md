# MIN0 CORE FORTH runtime dictionary v0.1

Status: executable layout experiment shared by the Python and Ruby reference
implementations.

## Memory region

- Default base: `0x00008000`
- Growth direction: upward
- Alignment: four bytes
- Empty `LATEST`: zero
- `HERE`: first unused byte after the newest entry or data allocation
- Multibyte cells: 32-bit little-endian

The default leaves the lower half of the initial 64 KiB VM memory for compiled
code. Dictionary headers and data allocations share the upper region. This
split is provisional and configurable by the host implementation.

## Entry layout

```text
header +0   u32  LINK        previous header address; zero ends the chain
header +4   u8   FLAGS
header +5   u8   NAME-LENGTH 1..31
header +6   u16  RESERVED    must be zero
header +8   byte NAME        uppercase ASCII, no terminator
             ... zero padding to a four-byte boundary
XT     +0   u32  KIND        see table below
XT     +4   u32  PAYLOAD     interpretation depends on KIND
```

`XT` is the aligned address of the `KIND` cell. The next entry begins eight
bytes after `XT`.

| KIND | Entry | PAYLOAD |
|---:|---|---|
| 0 | primitive | one-byte VM opcode |
| 1 | colon definition | compiled-code byte address |
| 2 | constant | cell value |
| 3 | variable | VM byte address of its data cell |
| 4 | created word | VM byte address of its data-field start |
| 5 | DOES word | address of the two-cell DOES descriptor |
| 6 | defining word | address of the two-cell definer descriptor |
| 7 | deferred word | current colon-word XT; zero means unassigned |

For kind 5, the descriptor contains the created word's body address followed
by its behavior code address. See `DOES_DESCRIPTOR_V0_1.md`. The indirection
allows XT metadata, body data, and executable code to occupy separate memory
regions without changing the fixed eight-byte XT layout.

For kind 6, the descriptor contains the dictionary-resident constructor-plan
address followed by the optional DOES behavior address. Zero in the second cell
means that the defining word creates an ordinary kind-4 child. See
`SOURCE_DOES_V0_1.md` and `CONSTRUCTOR_PLAN_V0_1.md`.

For kind 7, compiled code contains `ICALL XT+4`; it therefore reads the current
target XT at each invocation instead of copying its code address into the
caller. R0 restricts assignments to colon definitions. See
`MONITOR_PATCH_R0.md` and `DEFER_SOURCE_R0.md`.

Raw data and alignment padding may occur between linked headers. They are not
visited during lookup. New headers always begin at a four-byte boundary.
In the default flat layout, variable and created-word data fields begin
immediately after their entry's two-cell XT representation. In split mode,
their payload is the authoritative body address and adjacency is not assumed.

## Flags

| Bit | Value | Meaning |
|---:|---:|---|
| 0 | `0x01` | immediate |
| 1 | `0x02` | hidden from normal lookup |
| 2..7 | — | reserved; zero in v0.1 |

## Lookup

Names are canonicalized to uppercase ASCII. Lookup starts at `LATEST` and
follows `LINK`, so a newer definition shadows an older definition with the
same name. Hidden entries are skipped unless explicitly requested. Link cycles
and malformed headers are errors.

## Current boundary

The dictionary bytes and variable cells reside in VM memory, but Python or
Ruby still performs registration, lookup, and `HERE` allocation. Moving these
services into a self-hosted FORTH layer remains a separate design step.
