# MIN0 CORE FORTH interactive compiler v0.1

Status: executable experiment layered on the runtime dictionary and
interpret-state outer interpreter.

## State

- `STATE_INTERPRET = 0`
- `STATE_COMPILE = 1`
- Initial compiled-code address: `0x00001000`
- Current compiled-code pointer: `CODE-HERE`
- Code limit: the fixed primitive dispatch table immediately below dictionary base

`CODE-HERE` and dictionary `HERE` are separate in this experiment. This
supports the current split code/dictionary layout but is not yet a permanent
MIN0 CORE FORTH image decision.

## `:`

In interpret state, `:` consumes the following token as the definition name.
It records the current dictionary and code pointers for rollback, creates a
hidden colon entry whose payload is `CODE-HERE`, and changes `STATE` to compile.
The name must appear in the same input call as `:`.

## Compile-state token handling

1. Integer: emit `LIT` and one 32-bit cell.
2. Non-immediate primitive: emit its opcode.
3. Non-immediate colon word: emit `CALL` and its code address.
4. Constant, variable, or created word: emit `LIT` and its payload value/address.
5. Immediate word: execute its XT at compile time.
6. Unknown word: abort the current definition and report `UnknownWord`.

The hidden definition is absent from ordinary lookup. Therefore, redefining a
word can still refer to the previous visible definition of the same name.
Undefined forward references are not supported by the interactive compiler.

`HERE`, `,`, `C,`, `ALLOT`, `ALIGN`, `CONSTANT`, `VARIABLE`, and `CREATE` are
interpret-only in this stage. Their allocation and failure behavior is specified by
`DATA_DEFINITIONS_V0_1.md`.

## `;`

In compile state, `;` emits `EXIT`, clears the hidden flag on the current
dictionary entry, and returns `STATE` to interpret. Outside a definition it is
an error.

## Error rollback

Any exception during compilation restores dictionary `HERE`, `LATEST`, and
`CODE-HERE` to their values before `:`. Partially emitted code and the hidden
dictionary entry are cleared. The outer interpreter returns to interpret state.

## Deferred architecture decision

Before a persistent image format or target ABI is frozen, the project must
choose whether the portable profile requires one unified data space or permits
separate code and dictionary regions. The present split is an experiment, not
a final answer.
