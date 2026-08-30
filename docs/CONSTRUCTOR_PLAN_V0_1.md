# MIN0 CORE FORTH constructor plan v0.1

Status: candidate-frozen on 2026-08-28 for format version 1 and action IDs 0-4.

## Purpose

A defining word may interleave ordinary VM computation with dictionary
allocator operations. The allocator operations do not become VM opcodes.
Instead, the compiler divides constructor code into executable segments and
stores the ordered segments and actions in dictionary metadata.

The first demonstrated source is:

```forth
: VALUE:  CREATE , DOES> @ ;
123 VALUE: ANSWER
ANSWER
```

The final stack is `123`. `ANSWER` has a DATA-region body containing `123` and
a CODE-region behavior containing `@`.

## Dictionary layout

A kind-6 definer XT points to the existing two-cell descriptor:

```text
descriptor +0  u32  constructor plan address
descriptor +4  u32  DOES behavior address; zero means CREATE-only
```

The plan is cell aligned in DICTIONARY space:

```text
plan +0  u32  MAGIC = 0x4E4C5043 (bytes "CPLN")
plan +4  u32  FORMAT-VERSION = 1
plan +8  u32  STEP-COUNT, at least one

for each step:
  +0  u32  executable CODE segment address
  +4  u32  allocator action ID
```

Action IDs in v0.1 are:

| ID | Name | Effect after the CODE segment returns |
|---:|---|---|
| 0 | END | Finish constructor execution; final step only |
| 1 | COMMA | Pop one cell, store it at aligned data HERE, advance HERE |
| 2 | C-COMMA | Pop one cell, store its low eight bits at exact data HERE, advance one byte |
| 3 | ALLOT | Pop a nonnegative byte count, reserve from exact data HERE, advance by that count |
| 4 | ALIGN | Consume no stack item; advance data HERE to the next cell boundary |

Version 1 fixes this 12-byte header, the eight-byte step layout, and the
meaning of action IDs 0 through 4. A reader rejects any other version rather
than guessing its layout. Any incompatible layout change, action renumbering,
or action semantic change requires a new format version.

Every CODE segment ends in `EXIT`. The outer interpreter enters a segment using
the ordinary return trampoline, performs the associated action, and proceeds to
the next segment.

For `CREATE , DOES>`, the plan contains two steps:

```text
segment 0 -> COMMA
segment 1 -> END
```

The segments may be empty; an empty segment consists only of `EXIT`. Keeping
explicit segment boundaries makes later arithmetic or colon calls before and
after allocator actions use the same VM execution path.

The byte-sized counterpart is:

```forth
: BYTE:  CREATE C, DOES> C@ ;
0x1AB BYTE: FLAG
FLAG
```

Its plan is `C-COMMA, END`. The constructor stores `0xAB` at DATA `0x8000`
and advances data HERE to `0x8001` without alignment. `FLAG` later uses `C@`
and leaves decimal `171` on the stack.

An unaligned byte buffer can be defined as:

```forth
: BUFFER:  CREATE ALLOT ;
5 BUFFER: BUF
BUF
```

Its plan is `ALLOT, END`. The count `5` is consumed only after allocation
succeeds. `BUF` has body `0x8000`, data HERE becomes `0x8005`, and executing
the ordinary CREATEd child leaves its body address on the stack. Negative
counts are rejected by the current v0.1 allocator contract.

The four action types can participate in one plan:

```forth
: RECORD:  CREATE C, ALLOT ALIGN ;
2 0x1AB RECORD: ITEM
ITEM
```

The input stack is `( reserve-count byte-value -- )`. C-COMMA stores `0xAB`
and advances HERE from `0x8000` to `0x8001`; ALLOT consumes `2` and advances
to `0x8003`; ALIGN inserts one zero padding byte and advances to `0x8004`.
The plan is `C-COMMA, ALLOT, ALIGN, END`, and `ITEM` leaves body `0x8000`.

## Separation of concerns

- CODE contains executable bytecode segments and DOES behavior.
- DICTIONARY contains names, XTs, descriptors, and constructor plans.
- DATA contains child bodies and values stored by allocator actions.
- The VM executes bytecode without knowing HERE, LATEST, or dictionary limits.
- The outer dictionary layer performs COMMA/C-COMMA and their allocation checks.
- ALLOT is likewise performed by the dictionary layer and is not a VM opcode.
- ALIGN is an argument-free dictionary action and is not a VM opcode.

The plan is stored in VM-visible memory rather than a Python list or Ruby array,
so it can later be included in a persistent target image.

## Atomic construction

The child is hidden before plan execution. If any segment or action fails, the
outer interpreter restores header HERE, data HERE, LATEST, and all stack depths.
For example, invoking `VALUE: EMPTY` without an initial cell raises stack
underflow and leaves no `EMPTY` entry or allocated body behind.
`BUFFER: EMPTY`, a negative count, and a capacity failure follow the same rule;
an available count remains on the restored data stack when allocation fails.
If only ALIGN padding exceeds capacity, all earlier C-COMMA and ALLOT changes
in the same plan are cleared and both original arguments are restored.

## Candidate validation contract

Both the Python and Ruby readers validate a dictionary-resident plan before a
child is created:

- the definer descriptor is cell-aligned and wholly inside the live DICTIONARY;
- the plan is cell-aligned, starts in DICTIONARY, and ends before its descriptor;
- MAGIC is `CPLN` and FORMAT-VERSION is exactly 1;
- STEP-COUNT is nonzero and all steps fit before the descriptor;
- every segment address is executable in the active memory map;
- every action ID is known;
- END occurs exactly once, as the final action.

The writer applies the equivalent checks before changing dictionary memory.
Corrupt magic, unknown version, zero or overlapping length, unknown action,
early or missing END, non-CODE segment address, and unaligned descriptor are
covered by direct corruption tests. If valid metadata reaches a damaged CODE
segment and VM execution fails, the hidden child, allocator state, and all
three stacks are rolled back.

The detailed freeze scope and audit evidence are recorded in
`CONSTRUCTOR_PLAN_AUDIT_R0.md`.

## Current restrictions

- `CREATE` remains the first body token of a defining word.
- Allocator actions cannot currently occur inside unresolved conditional or loop
  control structures; plan actions are linear in v0.1.
- Constructor-plan events are emitted through the optional semantic observer
  specified by `TRACE_V0_1.md`.
- The complete persistent FORTH image format and target ABI are not frozen by
  this constructor-plan candidate.

`value_constructor_demo.py`, `value_constructor_demo.rb`, and
`cross_value_constructor_check.py` provide the executable agreement example.
`byte_constructor_demo.py`, `byte_constructor_demo.rb`, and
`cross_byte_constructor_check.py` provide the matching byte-sized example and
also compare the `constructor.c_comma` semantic event.
`allot_constructor_demo.py`, `allot_constructor_demo.rb`, and
`cross_allot_constructor_check.py` compare the buffer allocation, plan, stack,
and `constructor.allot` semantic event.
`align_constructor_demo.py`, `align_constructor_demo.rb`, and
`cross_align_constructor_check.py` compare the combined four-step plan, body
bytes, and all three allocator-action events.
