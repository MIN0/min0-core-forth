# MIN0 CORE FORTH conditional control flow v0.1

Status: executable interactive-compiler experiment.

## Compile-only words

`IF`, `ELSE`, and `THEN` are recognized by the interactive compiler only while
`STATE=COMPILE`. Using one in interpret state is a `CompileStateError`.

## Control-flow stack

The host compiler maintains a stack of pairs:

```text
( kind, operand-address )
```

`operand-address` is the address of a 32-bit branch target cell that must be
patched later. This control-flow stack is separate from the VM data and return
stacks and persists when one definition spans multiple input calls.

## `IF`

```text
emit ZBRANCH
remember address of its zero placeholder as (IF, address)
```

At runtime, `ZBRANCH` consumes the flag. Zero takes the branch; any nonzero
cell continues into the true clause.

## `ELSE`

`ELSE` requires `IF` at the top of the control-flow stack.

```text
remove the IF record
emit BRANCH with a new zero placeholder
patch IF to the first byte of the false clause
push (ELSE, new-placeholder-address)
```

## `THEN`

`THEN` requires `IF` or `ELSE` at the top of the control-flow stack. It removes
that record and patches its target to current `CODE-HERE`.

## Definition completion and errors

`;` is accepted only when the control-flow stack is empty. An unmatched,
misordered, or unresolved control word aborts the current definition. Code,
dictionary entry, dictionary `HERE`/`LATEST`, `CODE-HERE`, `STATE`, and the
control-flow stack are restored to the state before `:`.

Nested conditionals are supported naturally by the LIFO control-flow stack.

## Example encoding

```forth
: CHOOSE IF 111 ELSE 222 THEN ;
```

at code base `0x1000` produces:

```text
05 0F 10 00 00       ZBRANCH 0x100F
01 6F 00 00 00       LIT 111
04 14 10 00 00       BRANCH  0x1014
01 DE 00 00 00       LIT 222
03                   EXIT
```

Targets remain absolute byte addresses under the current provisional VM
profile.
