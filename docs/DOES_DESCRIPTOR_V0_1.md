# MIN0 CORE FORTH DOES descriptor v0.1

Status: executable representation used by the first source-level defining-word
stage in `SOURCE_DOES_V0_1.md`.

## Purpose

A word made by `CREATE` initially returns its body address. Attaching DOES
behavior changes that word so execution first places the same body address on
the data stack and then enters its behavior code.

The model must not require the dictionary header, data body, and executable
code to be physically adjacent. It therefore works with the split
CODE/DICTIONARY/DATA profile and with the legacy flat profile.

## XT and descriptor layout

The existing XT remains exactly two cells (eight bytes):

```text
XT +0  u32  KIND = 5 (KIND_DOES)
XT +4  u32  descriptor address
```

The cell-aligned descriptor is allocated from dictionary metadata space:

```text
descriptor +0  u32  body address
descriptor +4  u32  behavior code address
```

In the three-region reference profile these addresses normally point to three
different regions:

| Value | Region | Meaning |
| --- | --- | --- |
| XT and descriptor | DICTIONARY | searchable name and execution metadata |
| body address | DATA | per-word data created by `CREATE` |
| behavior address | CODE | bytecode ending in `EXIT` |

The descriptor indirection preserves the fixed XT size and all existing kind
layouts. Dictionary persistence must include descriptor bytes.

## Execution semantics

Interpret-state execution of a kind-5 word performs:

```text
push(body address)
enter behavior code with the outer return trampoline
```

Compiling a reference to the same word emits:

```text
LIT  body address
CALL behavior code address
```

Thus interpreted and compiled calls have the same stack effect. The compiled
form intentionally captures both addresses at compilation time; later
dictionary mutation does not silently retarget already compiled code.

## Safe transformation

`set_does(created_entry, code_address)` is the current host-side construction
operation. It:

1. accepts only a current kind-4 `CREATE` entry;
2. verifies that the behavior address is executable;
3. verifies descriptor and XT write ranges before mutation;
4. writes the descriptor and changes the XT to kind 5;
5. leaves `LATEST` and the body allocator unchanged;
6. restores bytes and header `HERE` if an unexpected write fails.

A full dictionary, a non-created entry, or a non-executable target leaves the
original word unchanged.

## Current boundary

Source-level `CREATE` and `DOES>` now create children through this descriptor.
Constructor calls to outer dictionary allocator words such as `,` and `ALLOT`
remain the next stage; they do not change this child execution format.

`does_descriptor_demo.py`, `does_descriptor_demo.rb`, and
`cross_does_descriptor_check.py` exercise the representation in both host
languages.
