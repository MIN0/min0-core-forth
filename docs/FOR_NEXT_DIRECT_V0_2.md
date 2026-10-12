# MIN0 CORE FORTH `FOR ... NEXT` direct-loop design v0.2

[Read this page in Japanese](FOR_NEXT_DIRECT_V0_2_JP.md)

Status: implemented experiment in the Python and Ruby host references.

## Decision

`DO ... LOOP` remains the standard-compatible structure for colon definitions. Direct counted loops
use the CF-inspired MIN0 extension `FOR ... NEXT`. The extension has matching iteration results in
direct input and compiled definitions:

```forth
3 FOR I NEXT
: INDEXES 3 FOR I NEXT ;
```

Both forms produce `0 1 2`. `0 FOR ... NEXT` executes zero times.

The word “direct” means interpret-state prompt or source execution. It is distinct from execution of
code that was compiled inside `: ... ;`.

## Relationship to CF

CF supplies `for`, `i`, and `next` as VM primitives. Its loop frame stores index, count, and the code
address following `for`. This naturally repeats compiled code. CF's outer interpreter executes each
direct token through a small temporary code slot, so directly entered body tokens are not buffered and
replayed as a block.

MIN0 adopts CF's count input, zero-based index, and loop-frame idea, but intentionally extends direct
input by buffering a complete token body. This is “CF-inspired”, not a claim of exact CF behavior.

## Semantics

```forth
FOR   ( u -- )
I     ( -- index )
J     ( -- outer-index )
NEXT  ( -- )
```

- `u` is one unsigned 32-bit cell.
- The index sequence is `0` through `u-1`.
- `u=0` skips the body.
- Nested loops use the existing VM loop stack; `I` observes the innermost frame and `J` the next one.
- The VM's configured loop-depth limit applies to direct and compiled loops.

In compile state, `FOR` emits `LIT 0`, then `QDO` with an exit patch. `NEXT` emits `LOOP` targeting the
body and resolves the exit. No new VM opcode or image-ABI field is introduced.

## Direct-input collection

When interpret state encounters `FOR`, it consumes `u`, enters direct-loop state, and collects parsed
tokens until the matching `NEXT`. Nested `FOR ... NEXT` pairs are counted while collecting. No body
token executes before the outer terminator is present and the body passes validation.

The host references currently use these configurable defaults:

- token-buffer maximum: 4096 tokens;
- direct execution budget: 100,000 token/iteration units;
- nesting limit: the VM loop-stack limit, normally 32 frames.

The interactive launchers display `...> ` while awaiting `NEXT`. File input and interactive EOF call
`finish_input`; an unfinished loop is rolled back and reported.

## Current direct-body boundary

Direct bodies accept numbers, ordinary executable dictionary words, `I`, `J`, output words, `."`, and
nested `FOR ... NEXT`. The initial implementation rejects compile structures, `DO`-family structures,
`UNLOOP`, source defining/allocation words, and `S"`. A colon word called from the body may still use
compiled control structures normally.

Before repetition, structural tokens and dictionary names are validated. On collection, validation,
or execution failure, DATA stack and loop-stack state are restored to the beginning of the direct-loop
input block. Already emitted external output and arbitrary memory effects from words that completed
before a run-time failure are not transactional.

## Diagnostics

This section records the v0.2 behavior. `DIRECT_CONTROL_V0_3.md` supersedes it by supporting direct
`DO ... LOOP` and `DO ... +LOOP` with the same buffered model. Unmatched or missing closers, buffer
overflow, execution-budget overflow, and loop-stack overflow remain deterministic errors.
