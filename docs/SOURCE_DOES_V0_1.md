# MIN0 CORE FORTH source CREATE/DOES> v0.1

Status: executable first stage.

## Supported source form

The outer interpreter can now compile and execute a defining word:

```forth
: MAKER
  CREATE
  7 +
DOES>
  1 +
;

5 MAKER CHILD
CHILD
```

`MAKER CHILD` consumes `CHILD` as a name, creates a hidden child, executes the
constructor portion, attaches the DOES behavior, and only then publishes the
child. In the example, the constructor changes `5` to `12`; later execution of
`CHILD` returns its body address plus one.

The generated defining word has dictionary kind 6 (`KIND_DEFINER`). Its fixed
XT points to a two-cell descriptor:

```text
descriptor +0  u32  constructor plan address
descriptor +4  u32  behavior code address; zero means CREATE-only
```

The generated child is initially kind 4 (`KIND_CREATED`) and becomes kind 5
(`KIND_DOES`) when a nonzero behavior address is attached. Consequently the
existing DOES descriptor remains the single representation used to execute
children.

## Compilation

- `CREATE` must be the first body token in this v0.1 stage.
- Constructor code occupies the first CODE segment and ends in `EXIT`.
- `DOES>` closes that segment and begins the behavior segment.
- `;` ends the behavior with `EXIT` and publishes the defining word.
- Omitting `DOES>` creates an ordinary kind-4 child.
- `DOES>` is compile-only and may occur once, after `CREATE`.
- A defining word itself is interpret-only because it must consume the next
  source token as the child name.

Definitions and defining-word invocations currently require their name in the
same call to the outer interpreter, consistently with the existing `:` and
interpret-state `CREATE` prototype.

## Atomic visibility and errors

The child remains hidden while its constructor runs and while DOES metadata is
attached. Name errors, constructor failures, descriptor failures, and memory
exhaustion restore header HERE, data HERE, LATEST, and all three stacks. No
partially built child remains searchable.

Malformed `CREATE`/`DOES>` definitions roll back dictionary and code allocation
to their pre-definition positions.

## Constructor allocator operations

Constructor code may currently use literals, primitives, colon words, and
control flow. `,` is now callable between `CREATE` and `DOES>` through the
dictionary-resident plan specified by `CONSTRUCTOR_PLAN_V0_1.md`.

The conventional form below is executable in Python and Ruby:

```forth
: VALUE:  CREATE , DOES> @ ;
```

`C,`, `ALLOT`, and `ALIGN` are now constructor plan actions 2, 3, and 4. All
remain outside the VM opcode set. Together with action 1 for `,`, the initial
constructor allocator vocabulary is executable in both implementations.
