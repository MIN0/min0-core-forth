# MIN0 CORE FORTH Split Dictionary v0.1

Status: executable design draft.

## Purpose

The original reference dictionary interleaves headers, XTs, and data bodies in
one upward-growing address range. Split mode preserves that layout as the
default but optionally gives dictionary metadata and Forth data space
independent upward-growing allocators.

This permits dictionary headers in EEPROM/FRAM, executable bytecode in a CODE
region, and `CREATE`/`VARIABLE` bodies in SRAM without requiring physical
adjacency.

## Configuration

`RuntimeDictionary` retains `base` and `limit` for the header allocator. The
optional `body_base` and `body_limit` select a separate body allocator.

- no `body_base`: legacy unified layout, byte-for-byte compatible
- `body_base` present: split layout; header and body ranges must not overlap
- all allocator bases are cell aligned
- both allocators grow upward and fail before exceeding their limits

The executable three-region example uses:

| Region | Logical range | Access | Use |
| --- | --- | --- | --- |
| CODE | `0000..3FFF` | `rwx` development; `rx` sealed runtime | compiled code and fixed dispatch |
| DICTIONARY | `4000..7FFF` | `rw`; runtime capability-protected | links, names, XT kind and payload |
| DATA | `8000..FFFF` | `rw` | `CREATE` data and variables |

Runtime publication uses a physically separate `rw,nx` staging map before the
sealed `rx` CODE map; see `W_X_PUBLICATION_R0.md`.

## HERE and data-space words

In split mode, Forth `HERE` reports the body allocator's `data_here`, not the
header allocator's position. These words operate on the body allocator:

- `,`
- `C,`
- `ALLOT`
- `ALIGN`
- `CREATE`
- `VARIABLE`

`dictionary.here` remains the header allocator position for dictionary
inspection and persistence. `dictionary.data_here` is the Forth data-space
position. `image()` returns the header image; `body_image()` returns allocated
body bytes.

## CREATE and VARIABLE

`CREATE name` aligns the body allocator and stores that logical address in the
entry payload. Later data-space words extend the body from that address.

`VARIABLE name` aligns the body allocator, stores that address in the entry
payload, and allocates one zero-initialized cell there.

No consumer may derive a body address from `XT + 8` in split mode. The payload
is authoritative. This rule is required before adding `DOES>`.

## Atomic rollback

A definition operation snapshots header HERE, data HERE, and LATEST. If header
or body allocation fails, bytes added in both ranges are cleared and all three
values are restored. An incomplete name does not remain searchable.

Persistent targets will later replace byte clearing with storage-appropriate
transaction/commit behavior, while preserving the same visible result.

## Executable agreement test

`cross_split_dictionary_check.py` requires the Python and Ruby implementations
to agree on addresses, body bytes, header digest, stack, and instruction count
for a program that creates a two-cell table, a variable, and a colon word that
sums the table and stores the result in the variable.
