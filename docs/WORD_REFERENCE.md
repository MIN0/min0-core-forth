# MIN0 CORE FORTH pocket word reference

[Read this page in Japanese](WORD_REFERENCE_JP.md)

This is the short manual for the 61 startup words printed by `WORDS` in release 0.1.2. It is designed
for use beside the terminal. Detailed rationale and implementation limits remain in the specification
documents.

## Look here first: what becomes possible

| Goal | Words to notice |
| --- | --- |
| Calculate with a visible stack | `DUP SWAP OVER DROP + - * .` |
| Define a new operation | `: ;` |
| Make decisions and loops | `IF ELSE THEN BEGIN UNTIL DO LOOP` |
| Store and retrieve values | `VARIABLE ! @ CONSTANT` |
| Build new kinds of words | `CREATE DOES>` |
| Change one chosen action without recompiling callers | `DEFER ' ['] IS ACTION-OF` |
| See what is available | `WORDS` |

> [!TIP]
> **Dynamic switching is a deliberate FORTH feature here.** `DEFER` creates a named call slot. `IS`
> selects its current target, and `ACTION-OF` reports that target. Already compiled callers continue to
> call the slot, so they do not need to be recompiled when the selected action changes.

```forth
: OLD-ACTION 10 ;
: NEW-ACTION 20 ;
DEFER ACTION
' OLD-ACTION IS ACTION
: USE-ACTION ACTION ;
USE-ACTION          \ leaves 10
' NEW-ACTION IS ACTION
USE-ACTION          \ leaves 20; USE-ACTION was not recompiled
```

Current 0.1 limit: a `DEFER` target must be a colon definition. After an authenticated Monitor locks the
runtime dictionary, ordinary source `IS` is rejected; switching must use the Monitor's narrow audited
control path.

## How to read stack effects

`( before -- after )` shows the DATA stack. The rightmost item is the top.

- `DUP ( x -- x x )`: duplicate the top item.
- `! ( x addr -- )`: consume a value and its destination address.
- `WORDS ( -- )`: no DATA-stack input or output.
- `flag` is `0` for false and `0xFFFFFFFF` for true.
- `xt` is an execution token, not a raw CODE address.

“Interpret” means entering the word directly at the prompt. “Compile” means using it inside `: name ... ;`.
“Structure” means a compile-only word whose effect occurs when the definition later runs.

## Stack, arithmetic, logic, and comparison

| Word | Stack effect | Use | Meaning |
| --- | --- | --- | --- |
| `NOP` | `( -- )` | interpret/compile | Do nothing. |
| `DROP` | `( x -- )` | interpret/compile | Remove the top item. |
| `DUP` | `( x -- x x )` | interpret/compile | Duplicate the top item. |
| `SWAP` | `( x1 x2 -- x2 x1 )` | interpret/compile | Exchange the top two items. |
| `OVER` | `( x1 x2 -- x1 x2 x1 )` | interpret/compile | Copy the second item to the top. |
| `+` | `( x1 x2 -- sum )` | interpret/compile | Add as one wrapping 32-bit cell. |
| `-` | `( x1 x2 -- difference )` | interpret/compile | Calculate `x1-x2`. |
| `*` | `( x1 x2 -- product )` | interpret/compile | Multiply as one wrapping 32-bit cell. |
| `AND` | `( x1 x2 -- x3 )` | interpret/compile | Bitwise AND. |
| `OR` | `( x1 x2 -- x3 )` | interpret/compile | Bitwise OR. |
| `XOR` | `( x1 x2 -- x3 )` | interpret/compile | Bitwise exclusive OR. |
| `<` | `( x1 x2 -- flag )` | interpret/compile | Signed comparison `x1<x2`. |
| `=` | `( x1 x2 -- flag )` | interpret/compile | Compare cells for equality. |

## Memory, cells, and characters

| Word | Stack effect | Use | Meaning |
| --- | --- | --- | --- |
| `@` | `( addr -- x )` | interpret/compile | Fetch one 32-bit little-endian cell. |
| `!` | `( x addr -- )` | interpret/compile | Store one cell where writing is permitted. |
| `C@` | `( c-addr -- char )` | interpret/compile | Fetch and zero-extend one byte. |
| `C!` | `( char c-addr -- )` | interpret/compile | Store the low eight bits. |
| `CELL+` | `( addr -- addr+4 )` | interpret/compile | Advance one 32-bit cell. |
| `CELLS` | `( n -- n*4 )` | interpret/compile | Convert a cell count to bytes. |
| `ALIGNED` | `( addr -- aligned-addr )` | interpret/compile | Round an address up to a four-byte boundary. |
| `CHAR+` | `( c-addr -- c-addr+1 )` | interpret/compile | Advance one character byte. |
| `CHARS` | `( n -- n )` | interpret/compile | Convert a character count to byte-address units. |

`!` cannot bypass the memory backend's permissions. Sealed CODE is not writable through ordinary `!`.

## Dictionary allocation and data definitions

| Word | Stack effect | Use | Meaning |
| --- | --- | --- | --- |
| `HERE` | `( -- addr )` | interpret | Return the next free dictionary/data address. |
| `,` | `( x -- )` | interpret/definer | Align, store one cell, and advance `HERE`. |
| `C,` | `( char -- )` | interpret/definer | Store one byte at exact `HERE`. |
| `ALLOT` | `( u -- )` | interpret/definer | Reserve and clear `u` nonnegative bytes. |
| `ALIGN` | `( -- )` | interpret/definer | Advance `HERE` to a cell boundary. |
| `CONSTANT name` | `( x -- )` | interpret | Define `name`; executing it leaves `x`. |
| `VARIABLE name` | `( -- )` | interpret | Define a zero cell; executing `name` leaves its address. |
| `CREATE name` | `( -- )` | interpret/definer | Define a word that leaves its body address. |

`CONSTANT`, `VARIABLE`, and interactive `CREATE` require the new name in the same input. Negative
`ALLOT` is rejected. Allocation failures roll back incomplete dictionary changes.

```forth
123 CONSTANT ANSWER
VARIABLE SLOT
ANSWER SLOT !
SLOT @ .             \ prints 123
```

## Colon definitions and conditional structures

| Word | Run-time stack effect | Use | Meaning |
| --- | --- | --- | --- |
| `: name` | `( -- )` | interpret | Begin a hidden colon definition. |
| `;` | `( -- )` | compile only | Finish and publish the current definition. |
| `IF` | `( flag -- )` | structure | Run the following part only when true. |
| `ELSE` | `( -- )` | structure | Begin the alternative part. |
| `THEN` | `( -- )` | structure | End `IF` or `ELSE`. |
| `BEGIN` | `( -- )` | structure | Mark the start of an indefinite loop. |
| `UNTIL` | `( flag -- )` | structure | Repeat from `BEGIN` while false. |
| `AGAIN` | `( -- )` | structure | Always repeat from `BEGIN`. |
| `WHILE` | `( flag -- )` | structure | Exit a `BEGIN ... REPEAT` loop when false. |
| `REPEAT` | `( -- )` | structure | Return to `BEGIN` and close `WHILE`. |

Mismatched structures abort the definition and restore dictionary and compiled-code allocation.

## Counted loops

| Word | Run-time stack effect | Use | Meaning |
| --- | --- | --- | --- |
| `DO` | `( limit start -- )` | structure | Start a counted loop; avoid equal start/limit. |
| `?DO` | `( limit start -- )` | structure | Skip the loop when start equals limit. |
| `LOOP` | `( -- )` | structure | Add one to the index and continue if needed. |
| `+LOOP` | `( increment -- )` | structure | Add a signed increment and test limit crossing. |
| `I` | `( -- index )` | interpret/compile | Copy the innermost loop index. |
| `J` | `( -- index )` | interpret/compile | Copy the next-outer loop index. |
| `LEAVE` | `( -- )` | structure | Exit the innermost counted loop. |
| `UNLOOP` | `( -- )` | interpret/compile | Remove one loop frame explicitly. |

The reference limit is 32 loop frames; the minimum portable guarantee is eight. `I`, `J`, and
`UNLOOP` fault when the required loop frame does not exist.

## Character, string, and numeric output

| Word | Stack effect | Use | Meaning |
| --- | --- | --- | --- |
| `.` | `( n -- )` | interpret | Print signed decimal and remove `n`. |
| `EMIT` | `( x -- )` | interpret | Output the low byte as one character. |
| `CR` | `( -- )` | interpret | Output one logical line feed. |
| `TYPE` | `( c-addr u -- )` | interpret | Validate and output `u` bytes atomically. |
| `S" text"` | `( -- c-addr u )` | interpret/compile | Store or compile a quoted byte string and return its range. |
| `." text"` | `( -- )` | interpret/compile | Output a quoted byte string; compiled form uses verified SERVICE 1. |

Quoted text is currently one byte per character, U+0000 through U+00FF. The portable visible teaching
subset is ASCII. Interpret-state `.`, `EMIT`, `CR`, and `TYPE` are host words and are not compiled directly.

## Defining words: `CREATE` and `DOES>`

| Word | Stack effect | Use | Meaning |
| --- | --- | --- | --- |
| `CREATE` | `( -- )` | first definer body item | Create a child that initially returns its body address. |
| `DOES>` | `( -- )` | definer structure | End constructor actions and begin the child's run-time behavior. |

```forth
: VALUE: CREATE , DOES> @ ;
123 VALUE: ANSWER
ANSWER .              \ prints 123
```

In this 0.1 stage, `CREATE` must be the first body item of a defining word. Constructor actions are
limited to `,`, `C,`, `ALLOT`, and `ALIGN`.

## Dynamic action selection

| Word | Stack effect | Use | Meaning |
| --- | --- | --- | --- |
| `DEFER name` | `( -- )` | interpret | Create an initially unassigned dynamic call slot. |
| `' name` | `( -- xt )` | interpret | Return the dictionary execution token of `name`. |
| `['] name` | `( -- xt )` | compile only | Compile code that leaves `name`'s execution token. |
| `IS defer-name` | `( xt -- )` | build-time interpret | Set the selected target of a `DEFER` word. |
| `ACTION-OF defer-name` | `( -- xt )` | interpret/compile | Return the currently selected target token. |

Executing an unassigned `DEFER` word or querying it with `ACTION-OF` is an error. Compiled `IS` is
rejected in the default `safe-runtime` profile and is available only in the explicit `standard-build`
experiment. Monitor attachment locks ordinary mutation and leaves only authenticated switching.

## Inspection

| Word | Stack effect | Use | Meaning |
| --- | --- | --- | --- |
| `WORDS` | `( -- )` | interpret | List startup words, then visible user definitions separately. |

`WORDS` lists only the newest searchable definition of a name. Hidden, failed, and rolled-back entries
are omitted.

## Input syntax that is not a startup word

- Decimal numbers such as `123` and hexadecimal numbers such as `0x7B` push one cell.
- `\` starts a comment that continues to the end of the line.
- Input is case-insensitive except for quoted text.
- `BYE` and `EXIT` leave the host reference REPL; they are launcher commands, not frozen CORE words.

## Continue learning

The [FORTH design and learning references](REFERENCES.md) provide a reading path from introductory books
to dictionaries, interpreters, compact VMs, and small-MPU implementations.
