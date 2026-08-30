# MIN0 CORE FORTH loop control v0.1

Status: executable interactive-compiler experiment.

## Compile-only words

- `BEGIN`
- `UNTIL`
- `AGAIN`
- `WHILE`
- `REPEAT`

They share the compile-time control-flow stack with `IF ELSE THEN` and may be
nested with conditionals or other loops.

## `BEGIN`

`BEGIN` emits no bytecode. It pushes `(BEGIN, CODE-HERE)`, recording the first
byte of the loop body.

## `UNTIL`

`UNTIL` requires `BEGIN` at the top of the control-flow stack, removes it, and
emits `ZBRANCH begin-address`. At runtime it consumes a flag: zero repeats the
loop and any nonzero cell exits.

## `AGAIN`

`AGAIN` requires and removes `BEGIN`, then emits unconditional
`BRANCH begin-address`. Code following it is unreachable unless entered by
another path. VM step limits remain the reference protection against an
unintended infinite loop.

## `WHILE`

`WHILE` requires `BEGIN` at the top of the stack. It leaves that record in
place, emits `ZBRANCH` with a zero placeholder, and pushes
`(WHILE, placeholder-address)` above `BEGIN`.

## `REPEAT`

`REPEAT` requires `BEGIN WHILE` as the top two control records. It removes both,
emits `BRANCH begin-address`, and patches the earlier `WHILE` target to current
`CODE-HERE`, immediately after that backward branch.

## Structural validation

`;` requires an empty control-flow stack. Missing, extra, or misordered loop
words abort the definition and restore code, dictionary, compiler state, and
control-flow state to their values before `:`. A structure may span multiple
outer-interpreter input calls.

## Examples

```forth
: COUNTDOWN BEGIN 1 - DUP 0 = UNTIL ;
: DOWN BEGIN 0 OVER < WHILE 1 - REPEAT ;
: FOREVER BEGIN 1 AGAIN ;
```

Forward and backward branch operands remain absolute 32-bit byte addresses in
the provisional VM profile.
