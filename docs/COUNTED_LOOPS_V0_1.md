# MIN0 CORE FORTH counted loops v0.1

Status: executable `DO ?DO LOOP +LOOP FOR NEXT I J UNLOOP LEAVE` experiment.

## Logical frame

Each active `DO` contributes one loop-stack frame:

```text
LIMIT  one 32-bit cell
INDEX  one 32-bit cell
```

The top frame is the innermost loop.

## Bytecode

| Opcode | Name | Meaning |
|---:|---|---|
| `15` | `DO` | `( limit start -- )`; push frame |
| `16` | `LOOP a` | increment index; branch to `a` unless it equals limit |
| `17` | `I` | `( -- index )`; copy innermost index to data stack |
| `18` | `UNLOOP` | discard innermost loop frame |
| `19` | `PLOOP a` | consume signed increment; continue or finish `+LOOP` |
| `1A` | `J` | `( -- index )`; copy next-outer loop index |
| `1B` | `QDO a` | `( limit start -- )`; skip loop when the values are equal |
| `1C` | `LEAVE a` | discard innermost frame and branch past its loop terminator |

`LOOP` has one 32-bit absolute byte-address operand under the provisional VM
profile. Index increment wraps modulo `2^32`. Plain `DO` does not skip its body
when start equals limit; without `?DO`, that case requires a complete cell-space
wrap before equality and should be avoided in ordinary source.

`?DO` has one absolute exit target. If start equals limit, it branches there
without allocating a loop frame; otherwise it behaves like `DO`.

`+LOOP` compiles as `PLOOP a`. Its increment is interpreted as a signed
32-bit value and index arithmetic wraps modulo `2^32`. For a positive
increment, the loop finishes when the signed difference `index-limit` changes
from negative to zero or positive. For a negative increment, it finishes when
that difference changes from positive to zero or negative. Thus an increment
may reach or pass the limit. Increment zero never finishes by itself and is
therefore bounded only by the VM instruction-step limit.

`J` requires at least two active frames. `I` and `J` push through the normal
checked data-stack path. `LEAVE` removes only the innermost frame before it
branches, so execution after a nested inner loop sees the outer frame again.

## Interactive compilation

`DO` emits opcode `DO`; `?DO` emits `QDO` plus an unresolved exit target. Both
push `(DO, BODY, EXIT-PATCHES)` on the compile-time control-flow stack.
`LOOP` or `+LOOP` requires and removes the top `DO` record, emits its backward
body target, then patches every exit to the address after the terminator.
`LEAVE` searches inward-to-outward for the nearest `DO` record and adds its
operand to that record's exit-patch list. This also permits `LEAVE` inside an
unresolved `IF` belonging to the loop body.

`I`, `J`, and `UNLOOP` are ordinary primitive dictionary entries. In a definition, `DO`, `?DO`,
`LOOP`, `+LOOP`, and `LEAVE` are structural compilation words. In direct input the opener starts
buffered collection, and an unmatched closer remains an error. Malformed structures roll back the
definition or direct-input block.

`FOR ... NEXT` is a CF-inspired MIN0 extension with `( u -- )` run-time input and a zero-based index.
In a colon definition, `FOR` compiles `LIT 0` followed by `QDO`; `NEXT` compiles `LOOP`. This reuses the
same loop frames and gives zero iterations when `u` is zero. At the prompt, the outer interpreter
buffers through the matching closer. Direct `DO` and `?DO` now run with `LOOP` or `+LOOP`, including
nested `IF`, `BEGIN`, and `FOR` structures. The generalized contract and current restrictions are in
`DIRECT_CONTROL_V0_3.md`; `FOR_NEXT_DIRECT_V0_2.md` records the earlier FOR-only stage.

## Nesting and limits

Nested loops push independent frames. `I` observes the innermost frame and `J`
the next-outer frame.
The reference limit is 32 frames; minimum portable guarantee is eight. Overflow
and underflow are checked as specified by `STACK_LIMITS_V0_1.md`.

## Example

```forth
: INDEXES 5 0 DO I LOOP ;
```

produces stack values `0 1 2 3 4` and leaves the loop stack empty.

```forth
: EVENS 10 0 DO I 2 +LOOP ;
: ZERO 0 0 ?DO I LOOP ;
: STOP 10 0 DO I DUP 3 = IF LEAVE THEN LOOP ;
```

These produce `0 2 4 6 8`, no values, and `0 1 2 3`, respectively.
