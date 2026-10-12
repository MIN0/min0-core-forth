# MIN0 CORE FORTH direct control structures v0.3

[Read this page in Japanese](DIRECT_CONTROL_V0_3_JP.md)

Status: experimental specification implemented by the Python and Ruby host references.

## Decision

Finding a control opener in direct input does not prove that its closer is absent. The outer interpreter
collects parsed tokens through the matching closer, validates the complete structure, and only then executes
it. The original `FOR ... NEXT` mechanism now covers all of these forms:

```forth
flag IF true-part [ ELSE false-part ] THEN
BEGIN body flag UNTIL
BEGIN body AGAIN
BEGIN test WHILE body REPEAT
limit start DO body LOOP
limit start ?DO body LOOP
limit start DO body increment +LOOP
limit start ?DO body increment +LOOP
u FOR body NEXT
```

Inside colon definitions these forms still compile to bytecode. At the prompt they use buffered direct
execution.

## Collection

- Openers are `IF`, `BEGIN`, `DO`, `?DO`, and `FOR`.
- Input may span physical lines; the continuation prompt is `...> `.
- A LIFO structure stack matches mixed nested structures.
- Tokens following the outer closer on the same input are interpreted after the structure executes.
- EOF with an unfinished structure reports the required closer.

The opener removes its `flag`, `limit start`, or `u` input from the DATA stack and holds it in the collection.
After successful validation, those values are restored as execution inputs. They therefore do not appear in
the stack while continuation input is being collected.

## Execution and nesting

Collected tokens are parsed into a direct-control tree and every branch is validated before execution.
Structures may contain any other supported direct structure. `I` observes the innermost active `DO`, `?DO`,
or `FOR` frame, and `J` observes the next outer frame.

`LEAVE` exits the innermost directly entered `DO`, `?DO`, or `FOR`, including when it appears inside a nested
`IF` or `BEGIN` that is lexically enclosed by that counted loop.

## Limits and rollback

```text
token buffer       4096 tokens
direct execution  100,000 node/iteration units
loop depth         VM setting, normally 32 frames
```

The execution budget bounds `BEGIN ... AGAIN`, a non-terminating `UNTIL`, zero-step `+LOOP`, equal-start plain
`DO`, and similar cases. Collection, validation, and execution failures restore the DATA and loop stacks to
the beginning of the outer direct-control input block. Output already emitted and completed memory writes are
not transactionally rolled back.

## Out of scope

`;` closes a colon definition and is not a direct-control opener. `[']` compiles a following name, and `DOES>`
belongs to defining-word compilation, so neither uses this buffer. Standalone `UNLOOP` also requires a valid
execution context.

The initial direct body accepts numbers, ordinary executable dictionary words, host output words, `."`, and
the structures listed above. `S"`, DATA/source defining words, and colon-definition delimiters remain rejected
until their semantics are unified separately.

## Relationship to v0.2

This document generalizes the collection, limits, and rollback model in `FOR_NEXT_DIRECT_V0_2.md`. The count,
zero-based index, and zero-trip behavior of `FOR ... NEXT` do not change. This v0.3 supersedes the former rule
that rejected the `DO` family in direct input.
