# MIN0 CORE FORTH terminal output v0.1

Status: executable host/service-boundary experiment. `.`, `EMIT`, `CR`, `TYPE`, and interpret／compiled
quoted strings are implemented in Python and Ruby.

## Boundary

Terminal policy remains outside the minimal VM. Direct output words use target-owned handlers; their
compiled forms call generic verified services 1 through 4. The VM knows only a numeric service boundary
and therefore does not depend on UART, USB, console, operating-system, or FPGA display hardware. A target
port may bind those IDs to its own adapters without changing FORTH source semantics.

The host reference implementation accumulates ordered output fragments in `output` and exposes their
exact concatenation as `terminal_text`. It does not automatically print those fragments to the real
host terminal.

## Character unit

- One MIN0 character storage unit is one byte, matching `C@`, `C!`, `C,`, `CHAR+`, and `CHARS`.
- `EMIT ( x -- )` uses the low eight bits of `x`.
- Python and Ruby map byte values 0–255 to Unicode code points U+0000–U+00FF in the host collector.
- The portable visible teaching subset is ASCII `0x20`–`0x7E`.
- Target device encoding outside that subset is target-profile policy and is not frozen by this file.
- `CR ( -- )` appends LF (`0x0A`) to the normalized host stream. A target adapter may translate that
  logical newline to the sequence required by its terminal.

## Current words

```forth
65 EMIT 66 EMIT CR
```

produces the exact host stream `"AB\n"` and leaves the DATA stack empty.

`EMIT` checks stack depth before changing output. On `StackUnderflow`, both the stack and output remain
unchanged. `CR` takes no stack argument. The low-byte rule makes `0x141 EMIT` produce `A`, matching the
existing `C!` and `C,` behavior.

```forth
CREATE TEXT 0x46 C, 0x4F C, 0x52 C, 0x54 C, 0x48 C,
TEXT 5 TYPE
```

produces the exact stream `"FORTH"`. `TYPE ( c-addr u -- )` treats `c-addr` as the first byte address
and `u` as an unsigned byte count. Before changing the stack or output, it reads and validates the
complete range. A range fault or read-permission fault therefore leaves both stack arguments and the
entire prior output unchanged; a partial terminal fragment is impossible.

The complete non-empty range must fit in one readable memory region. Read-only Flash／EEPROM-like
regions are valid sources. When `u` is zero, `TYPE` consumes both arguments without dereferencing or
validating `c-addr`, and adds no output fragment. Host byte-to-character mapping is the same
U+0000–U+00FF rule used by `EMIT`.

`.`, `EMIT`, `CR`, and `TYPE` are reserved ordinary output words usable both directly and inside a colon
definition. Direct and compiled paths call the same target-owned handlers. Compilation emits `SERVICE 3`,
`SERVICE 2`, `SERVICE 4`, and `SERVICE 1` respectively; it does not create target-dependent terminal opcodes.
Dedicated `SERVICE 4` lets `CR ( -- )` succeed even when the DATA stack is full, because it does not need a
temporary line-feed cell.

`S"` stores case-preserved quoted byte text in dictionary DATA and returns `c-addr u`; `."` adds quoted
text directly to the collector. Their same-line grammar, byte restriction, allocator behavior, and
failure atomicity are defined in `STRING_LITERALS_V0_1.md`. Both are supported in interactive colon
definitions with typed DATA relocation; compiled `."` additionally emits verified `SERVICE 1`.

## Control-character safety

Arbitrary byte output can contain ESC and other terminal control characters. The core collector stores
them as data and does not execute or print them. A future terminal adapter must explicitly choose one of
these policies:

- raw device mode for a trusted serial console;
- escaped teaching mode that renders control bytes visibly;
- restricted protocol mode with a profile-specific allowlist.

Viewer and AI explanations must continue to treat terminal output as observed data, never as commands or
markup. In particular, Viewer insertion must use text nodes rather than HTML interpretation.

## Verified compiled-output boundary

`OUTPUT_SERVICE_BOUNDARY_R0.md` defines registry ownership, verifier-derived service requirements,
one-way sealing, and all four terminal service contracts. Python and Ruby execute compiled output calls
with CODE=`rx` and DATA=`r`; an absent required service prevents sealing before CODE runs.
