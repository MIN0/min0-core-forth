# MIN0 CORE FORTH data definitions v0.1

Status: executable `HERE , C, ALLOT ALIGN CONSTANT VARIABLE CREATE` experiment.

## Shared dictionary/data region

Dictionary `HERE` is the first unused byte in the upward-growing region that
contains linked headers and allocated data. It is independent of `CODE-HERE`,
which remains in the lower compiled-code region. Headers, cells, constants,
and variables use 32-bit little-endian values.

`ALLOT` may leave `HERE` unaligned. A later cell allocation or dictionary
header inserts zero padding up to the next four-byte boundary.

## Interpret-state words

| Word | Stack effect | v0.1 behavior |
|---|---|---|
| `HERE` | `( -- address )` | push the current dictionary/data `HERE` |
| `,` | `( x -- )` | align `HERE`, store one cell, and advance it |
| `C,` | `( char -- )` | store the low eight bits at exact `HERE` |
| `ALLOT` | `( byte-count -- )` | reserve and zero nonnegative bytes |
| `ALIGN` | `( -- )` | advance `HERE` to the next cell boundary |
| `CONSTANT name` | `( x -- )` | add a kind-2 entry whose payload is `x` |
| `VARIABLE name` | `( -- )` | allocate a zero cell and add a kind-3 entry pointing to it |
| `CREATE name` | `( -- )` | add a kind-4 entry pointing just after its XT |

Negative `ALLOT` is deliberately rejected in v0.1. Supporting downward
allocation is deferred until image-space ownership and forgetting semantics
are specified.

`CONSTANT`, `VARIABLE`, and `CREATE` require their name in the same input call.
The eight data words are reserved and cannot themselves be redefined in this
experiment. They are interpret-only host services; compiling one directly in
a colon definition is an error.

## Executing and compiling defined words

Executing a constant pushes its payload. Executing a variable or created word
pushes its data-field address. When any of these appears inside a colon
definition, the interactive compiler emits `LIT payload`. Therefore the
resulting colon bytecode needs no host callback to use them.

`VARIABLE` uses the same post-header data-field model as `CREATE` and appends
one zero cell. `CREATE` itself appends no body bytes; following `,` or `ALLOT`
constructs its body beginning exactly at the address returned by the created
word.

## Failure atomicity

All capacity checks happen before committing a data allocation. If `,`, `C,`,
`ALLOT`, or `CONSTANT` fails, its stack argument remains available. If a
`VARIABLE` header fits but its following zero cell does not, the header and any
alignment padding are rolled back; `HERE` and `LATEST` return to their prior
values. A failed `CREATE` likewise leaves no partial header.

Allocated bytes and alignment padding are zero-filled for deterministic image
comparison. Successful VM stores are not transactional.

## Example

```forth
123 CONSTANT ANSWER
VARIABLE SLOT

: USE ANSWER SLOT ! SLOT @ ;
USE
```

`USE` leaves `123` on the data stack and stores the same value in `SLOT`.

```forth
CREATE TABLE 10 , 20 ,
: SECOND TABLE CELL+ @ ;
```

`TABLE` returns the address of the cell containing `10`; `SECOND` returns
`20`.

## Cell address words

The VM primitive vocabulary includes these profile-dependent address words:

| Word | Stack effect at 32 bits |
|---|---|
| `CELL+` | `( address -- address+4 )` |
| `CELLS` | `( n -- n*4 )` |
| `ALIGNED` | `( address -- next-address-divisible-by-4 )` |

Their arithmetic wraps as one VM cell. Unlike `ALIGN`, `ALIGNED` changes only
the value on the data stack and never changes dictionary `HERE`.

## Character and byte words

The v0.1 character is one unsigned 8-bit byte, and one character occupies one
byte-address unit.

| Word | Stack effect | Meaning |
|---|---|---|
| `C@` | `( byte-address -- char )` | read and zero-extend one byte |
| `C!` | `( char byte-address -- )` | store the low eight bits |
| `CHAR+` | `( byte-address -- byte-address+1 )` | advance one character |
| `CHARS` | `( n -- n )` | convert character count to address units |

`C,` never aligns `HERE`. A later `,`, `ALIGN`, or aligned header inserts
zero-filled padding when required. VM fetch/store instructions validate the
entire address range before consuming stack operands, so a memory fault leaves
their arguments available to the outer interpreter's recovery path.
