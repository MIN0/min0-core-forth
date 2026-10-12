# CORE word compilation-compatibility plan

[Read this page in Japanese](CORE_WORD_COMPILATION_PLAN_JP.md)

Status: implemented and verified on 2026-09-14. This page preserves the decision and acceptance record.

## Decision

The old implementation executed `.`, `EMIT`, `CR`, and `TYPE` at the prompt but could not compile them in a
colon definition. This was classified as a CORE-compatibility implementation gap, not a permanent MIN0 rule,
and is resolved in the current development version.

An ordinary executable word should follow this default principle:

> A normal word that executes at the prompt can be compiled into a colon definition and has the same
> execution semantics in direct and compiled use.

Control structures, definition delimiters, parsing words, and words requiring an active frame have their own
semantics and must be classified separately. Calling host code internally is not by itself a reason to reject
compilation at the source-language boundary.

## CF comparison

The inspected CF commit is `07ec6a7a2a65d382d0c54111ec2a2c5b93cc0cf4`. CF registers `emit` as a VM
primitive that calls its C output function, and its outer interpreter compiles that ordinary word in COMPILE
state. CF's own boot source uses `emit` inside the definitions of `space`, `tab`, and `cr`.

MIN0's rejection of compiled `EMIT` is therefore not CF-compatible behavior.

## Implemented result

These four words are now usable both directly and inside colon definitions:

| Word | Stack effect | Compiled form |
| --- | --- | --- |
| `TYPE` | `( c-addr u -- )` | Emit existing `SERVICE 1 terminal-type-v0.1`. |
| `EMIT` | `( x -- )` | Emit new `SERVICE 2 terminal-emit-v0.1`. |
| `CR` | `( -- )` | Emit dedicated `SERVICE 4 terminal-cr-v0.1`. |
| `.` | `( n -- )` | Emit new `SERVICE 3 terminal-dot-v0.1`. |

`terminal-emit-v0.1` outputs the low eight bits of `x` and consumes `x` only after a successful commit.
`terminal-dot-v0.1` emits the same signed decimal representation as direct `.`, with no added spacing. Direct
execution and service handlers must share implementation so output, stack effects, and errors agree.

The original plan encoded compiled `CR` as `LIT 10` plus `SERVICE 2`. Although its external stack effect
would be `( -- )`, that sequence temporarily needs one free DATA-stack cell and could raise `StackOverflow`
on an otherwise valid full stack. Dedicated service 4 needs no temporary cell and preserves the real `( -- )`
contract. Direct and compiled `CR` call the same logical-line-feed handler.

`WORDS` also needs compilation-semantics review, but its dictionary-introspection role makes it a separate
TOOLS concern that must not block these four CORE output words.

## Whole-CORE audit

A matrix for all 65 startup words now records interpretation, compilation, and execution semantics, required
context, and whether each restriction is intentional or still requires a decision. See
[CORE word semantics matrix](CORE_WORD_SEMANTICS_MATRIX.md).

Priority groups are `. EMIT CR TYPE WORDS`, `HERE , C, ALLOT ALIGN`, `CONSTANT VARIABLE CREATE`, and
`DEFER ' IS ACTION-OF`. Parsing and defining words must not be made compilable blindly; first specify their
relationship with source parsing and run-time input.

## Acceptance tests

Both Python and Ruby now run:

```forth
65 EMIT
: EMIT-A 65 EMIT ;
EMIT-A

: NEWLINE CR ;
NEWLINE

: SAY-ABC S" ABC" TYPE ;
SAY-ABC

: SHOW-NUMBER -42 . ;
SHOW-NUMBER

: DIGITS 3 FOR I 48 + EMIT NEXT ;
DIGITS
```

Acceptance requires matching direct/compiled output and final DATA stacks; exact output `A`, `ABC`, `-42`,
and `012`; atomic underflow/range/unavailable-service failures; verifier checks for IDs, operands, and branch
boundaries; required frozen services before sealed publication; Python/Ruby agreement on bytecode, required
services, output, and errors; and removal of obsolete compilation-limit documentation.

The complete 2026-09-14 validation passed 336 Python tests, 48 Ruby test files, and 49 Python/Ruby
cross-language checks.

## Changed locations

- Python and Ruby outer interpreters: compile dispatch, shared output logic, and service registration
- Python and Ruby compiled-output tests: direct/compiled semantics and failure atomicity
- service-boundary, CLI, and cross-language tests: four services, sealed execution, and language agreement
- pocket references, known limitations, terminal/service specifications, and the 65-word audit matrix

Do not add terminal-specific opcodes. Keep the CPU-independent `SERVICE` boundary so UART, host console, and
test buffer remain target-adapter choices without changing FORTH source semantics.
