# MIN0 CORE FORTH stack limits and faults v0.1

Status: executable reference-profile experiment.

## Reference defaults

| Logical stack | Unit | Default limit | Storage at 32 bits |
|---|---:|---:|---:|
| data | cell | 256 | 1024 bytes |
| return | cell | 256 | 1024 bytes |
| loop | two-cell frame | 32 | 256 bytes |

A conforming target profile must guarantee at least eight nested loop frames
(64 bytes at 32-bit cells). All limits are configurable and must be exposed by
the implementation. Smaller values may be used by tests or explicitly
documented constrained profiles.

## Required checks

Every push checks capacity before modifying its stack. Every operation that
requires existing cells or frames checks depth before removing anything.

- `DataStackOverflow`
- `ReturnStackOverflow`
- `LoopStackOverflow`
- data `StackUnderflow`
- return `StackUnderflow`
- `LoopStackUnderflow`

An overflow attempt does not append the rejected value or frame. `reset`
empties all three logical stacks.

Memory fetch/store instructions validate their full byte range before
consuming data-stack arguments. This applies to both cell words `@ !` and byte
words `C@ C!`.

## Outer-interpreter recovery

Before executing one XT, the reference outer interpreter records the data
stack contents and the return/loop depths. If VM execution raises an exception,
those three stacks are restored before the exception is reported. This prevents
return addresses or loop frames from leaking into subsequent commands.

VM-memory writes are not transactional and are not rolled back by this rule.
A later `CATCH`/`THROW` specification must define broader recovery semantics.

## Target mapping

The MIN0 CORE FORTH semantics define three logical stacks. A target may combine the
return and loop stacks physically if it preserves all specified behavior,
capacity reporting, nesting, and fault checks.
