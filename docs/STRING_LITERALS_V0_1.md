# MIN0 CORE FORTH quoted strings v0.1

Status: interpret-state and compiled `S"`／`."` executable experiment in Python and Ruby.

## Purpose and current boundary

This increment connects source text to the existing byte-character and terminal-output model without
adding a target-console-specific VM opcode.

```forth
S" Hello World" TYPE
." Done"
```

produces the exact host stream `Hello WorldDone` and leaves the DATA stack empty.

Both words have interpret-state behavior in this increment:

- `S" ccc" ( -- c-addr u )` stores `ccc` in dictionary DATA and returns its byte address and length.
- `." ccc" ( -- )` appends `ccc` directly to the host output collector without allocating DATA.

Both quoted words can be compiled by the interactive runtime compiler:

```forth
: MESSAGE S" Compiled" ;
MESSAGE TYPE
: GREETING ." Hello" ;
GREETING
```

At execution, `MESSAGE` pushes the relocated string address and byte length; the following interpret-state
`TYPE` emits `Compiled`. `GREETING` emits `Hello` through verified service ID 1 and leaves no string
arguments on the stack. The raw standalone compiler still rejects quoted words with `CompileError`;
compiled quoted words belong to the runtime dictionary/image compiler.

## Source grammar

- The introducer is case-insensitive `S"` or `."` at a token boundary.
- One immediate space or tab after the introducer is the source delimiter and is not part of `ccc`.
- Any additional leading spaces, internal spaces, case, and backslash characters are preserved.
- Backslash starts a line comment only outside quoted text.
- The closing quote must occur on the same source line.
- v0.1 has no escape syntax for embedding a double quote inside `ccc`.
- `S""` and `.""` represent empty text.

The tokenizer reads and validates the complete input passed to one `interpret()` call before executing
its first word. An unterminated quote therefore prevents every word in that input from running.

## Byte model

Each source character must be in U+0000..U+00FF and becomes one byte with the same numeric value. This
is the inverse of the host mapping already used by `EMIT` and `TYPE`.

- ASCII is the portable visible teaching subset.
- Latin-1 values such as `é` are preserved as one byte (`0xE9`) by the reference host.
- Characters above U+00FF, including Japanese source text, are rejected before stack, allocator, or
  output changes. A target encoding or UTF-8 profile is deliberately not implied by v0.1.

## `S"` storage and atomicity

Interpret-state `S"` uses the existing dictionary DATA allocator. Its bytes are persistent within the
current development image; each non-empty use advances data HERE by its byte length. This is not a
transient-buffer promise. Repeated interactive use therefore consumes DATA space until the image is
reset or reloaded.

Before allocation, `S"` validates:

1. every source character fits the byte model;
2. two DATA-stack cells are available;
3. the destination range is writable;
4. the dictionary allocator can reserve the complete range.

Only after those checks and allocation does it write the bytes and push `c-addr u`. Capacity, write,
and stack failures leave DATA stack and data HERE unchanged. A sealed safe-runtime dictionary rejects
new `S"` allocation; already packaged strings remain readable by `TYPE` from a read-only region.

For zero length, `S""` returns the current data HERE and zero without advancing HERE. `TYPE` then
consumes that pair without dereferencing the address.

## Compiled quoted strings, relocation, and rollback

Compiled `S"` places non-empty bytes in image DATA and emits bytecode equivalent to:

```text
LIT <typed DATA address>
LIT <byte length>
```

The address cell produces a `string-address` relocation record whose target is `data`; length is an
ordinary numeric literal. An empty compiled string uses DATA offset zero and length zero, so relocation
remains valid without allocating bytes.

Definition rollback treats CODE bytes, string DATA bytes, dictionary header state, source mapping, and
relocation records as one transaction. An unknown later word, nonbyte character, allocator failure, or
unresolved control structure removes the incomplete definition and restores every saved boundary.

The executable relocation experiment moved a string from DATA base `0x8000` to `0x9000`, then sealed the
destination DATA region to permission `r`. `TYPE` still emitted `Relocated`; normal write, host program,
and whole-memory clear were all rejected. `RegionMemory.seal_read_only_region` is a one-way transition
and removes host programmability as well as ordinary write permission.

## `."` output and safety

Interpret-state `."` validates the complete text before adding one output fragment. It does not allocate
memory and does not automatically print control bytes to the real host terminal. Viewer insertion
continues to use text nodes, and quoted text is observed data rather than instructions or markup.

Compiled `."` uses the same DATA placement and `string-address` relocation as compiled `S"`, followed by:

```text
SERVICE 1  # terminal-type-v0.1
```

The verifier derives service ID `[1]` from actual CODE, rejects malformed operands and any relocation on
the ID, and protects all four operand bytes from branch entry. Before CODE is sealed, the target must have
registered that service. Sealing freezes the image allowlist and registry; image data and source cannot
install or replace callbacks. The handler reuses `TYPE`'s complete-range validation, zero-length rule, and
failure atomicity.

The complete authority boundary is recorded in `OUTPUT_SERVICE_BOUNDARY_R0.md`.
