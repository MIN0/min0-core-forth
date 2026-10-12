# Semantics audit for all 69 startup words

[Read this page in Japanese](CORE_WORD_SEMANTICS_MATRIX_JP.md)

Status: audit record matching the Python and Ruby implementations as of 2026-09-14.

The matrix separates interpretation semantics from compilation semantics. “Implemented” means covered in both
hosts and tests; “context-dependent” means a required structure or frame may produce an error; “review” means
the current restriction has not been approved as final CORE behavior.

## Comments and ordinary primitives

| Word | Interpretation semantics | Compilation semantics | Status or required context |
| --- | --- | --- | --- |
| `(` | Skip source through the next `)`. | Same; emit no code. | Standard/CF-compatible; unfinished input errors. |
| `\` | Skip through the physical line end. | Same; emit no code. | Conventional line comment. |
| `NOP` | Do nothing. | Emit `NOP`. | Implemented. |
| `DROP` | Remove the top cell. | Emit `DROP`. | Implemented. |
| `DUP` | Duplicate the top cell. | Emit `DUP`. | Implemented. |
| `SWAP` | Exchange the top two cells. | Emit `SWAP`. | Implemented. |
| `OVER` | Copy the second cell. | Emit `OVER`. | Implemented. |
| `ROT` | Move the third cell to the top. | Emit `ROT`. | Implemented. |
| `DEPTH` | Push the current DATA-stack depth. | Emit `DEPTH`. | Implemented. |
| `+` | Add 32-bit cells. | Emit `ADD`. | Implemented. |
| `-` | Subtract 32-bit cells. | Emit `SUB`. | Implemented. |
| `*` | Return the low 32 bits of a product. | Emit `MUL`. | Implemented; double-cell product remains future work. |
| `/MOD` | Return signed remainder and quotient, rounding toward zero. | Emit `DIVMOD`. | Rejects zero and signed overflow without changing inputs. |
| `AND` | Perform bitwise AND. | Emit `AND`. | Implemented. |
| `OR` | Perform bitwise OR. | Emit `OR`. | Implemented. |
| `XOR` | Perform bitwise XOR. | Emit `XOR`. | Implemented. |
| `<` | Return a signed comparison flag. | Emit `LESS`. | Implemented. |
| `=` | Return a cell-equality flag. | Emit `EQUAL`. | Implemented. |
| `@` | Read one cell. | Emit `FETCH`. | Memory permissions checked. |
| `!` | Write one cell. | Emit `STORE`. | Memory permissions checked. |
| `C@` | Read and zero-extend one byte. | Emit `C_FETCH`. | Implemented. |
| `C!` | Write the low eight bits. | Emit `C_STORE`. | Implemented. |
| `CELL+` | Advance an address by four. | Emit `CELL_PLUS`. | 32-bit reference profile. |
| `CELLS` | Convert cells to bytes. | Emit `CELLS`. | 32-bit reference profile. |
| `ALIGNED` | Round up to a four-byte boundary. | Emit `ALIGNED`. | 32-bit reference profile. |
| `CHAR+` | Advance a character address by one. | Emit `CHAR_PLUS`. | One character address unit is one byte. |
| `CHARS` | Convert characters to address units. | Emit `CHARS`. | Identity in the current profile. |
| `I` | Copy the innermost loop index. | Emit `I`. | Requires an active loop frame. |
| `J` | Copy the next-outer loop index. | Emit `J`. | Requires at least two loop frames. |
| `UNLOOP` | Remove the innermost loop frame. | Emit `UNLOOP`. | Run-time loop context; not accepted in a direct buffer. |

## Output, strings, and inspection

| Word | Interpretation semantics | Compilation semantics | Status or required context |
| --- | --- | --- | --- |
| `.` | Emit signed decimal. | Emit `SERVICE 3 terminal-dot-v0.1`. | Direct/compiled agreement implemented. |
| `EMIT` | Emit the low eight bits as one character. | Emit `SERVICE 2 terminal-emit-v0.1`. | Same source-level availability as CF. |
| `CR` | Emit one logical newline. | Emit `SERVICE 4 terminal-cr-v0.1`. | Uses no temporary DATA-stack cell. |
| `TYPE` | Validate and atomically emit a byte range. | Emit `SERVICE 1 terminal-type-v0.1`. | Fault preserves arguments and prior output. |
| `S"` | Allocate bytes and return address and length. | Emit relocated DATA address and length literals. | U+0000 through U+00FF. |
| `."` | Emit quoted bytes immediately. | Emit address, length, and `SERVICE 1`. | Implemented. |
| `WORDS` | Display classified visible dictionary words. | Currently rejected. | TOOLS concern; compilation semantics under review. |
| `.S` | Display stack depth and signed contents without changing the stack. | Currently rejected. | Interpret-only inspection word. |

## Allocation and defining words

| Word | Interpretation semantics | Compilation semantics | Status or required context |
| --- | --- | --- | --- |
| `HERE` | Return the next DATA allocation address. | Currently rejected. | Review as an ordinary executable word. |
| `,` | Store a cell and advance `HERE`. | Constructor action only after `CREATE`. | General compilation semantics under review. |
| `C,` | Store a byte and advance `HERE`. | Constructor action only after `CREATE`. | General compilation semantics under review. |
| `ALLOT` | Reserve a nonnegative byte count. | Constructor action only after `CREATE`. | General compilation semantics under review. |
| `ALIGN` | Advance `HERE` to a cell boundary. | Constructor action only after `CREATE`. | General compilation semantics under review. |
| `CONSTANT` | Parse a name and define a word returning the stack value. | Currently rejected. | Run-time source parsing needs design. |
| `VARIABLE` | Parse a name and define a zero-cell word. | Currently rejected. | Run-time source parsing needs design. |
| `CREATE` | Parse a name and define a body-address word. | Begin a constructor as the first defining-word token. | Implemented with MIN0 v0.1 restrictions. |

## Definition delimiters and control structures

| Word | Interpretation semantics | Compilation semantics | Status or required context |
| --- | --- | --- | --- |
| `:` | Parse a name and begin a hidden colon definition. | Reject nested `:`. | Keep compilation state through `;`. |
| `;` | Error when no definition is open. | Emit `EXIT` and publish the definition. | Requires matching `:`. |
| `IF` | Collect through `THEN`, then branch on the flag. | Emit unresolved zero branch. | Direct and definition forms implemented. |
| `ELSE` | Begin the alternative of a collected direct `IF`. | Patch `IF` and emit an end branch. | Requires matching `IF`. |
| `THEN` | Close direct `IF` and execute its block. | Patch the `IF` or `ELSE` branch. | Requires matching `IF`. |
| `BEGIN` | Collect direct input through a terminator. | Record the loop start address. | Needs `UNTIL`, `AGAIN`, or `WHILE ... REPEAT`. |
| `UNTIL` | Repeat direct `BEGIN` while false. | Emit conditional backward branch. | Requires matching `BEGIN`. |
| `AGAIN` | Repeat direct `BEGIN` unconditionally. | Emit unconditional backward branch. | Execution-step limit applies. |
| `WHILE` | Handle the direct `BEGIN ... REPEAT` condition. | Emit unresolved loop-exit branch. | Requires `BEGIN` and `REPEAT`. |
| `REPEAT` | Close direct `BEGIN ... WHILE`. | Emit backward branch and patch the exit. | Requires matching `BEGIN WHILE`. |
| `DO` | Collect through `LOOP` or `+LOOP` and run a counted loop. | Emit `DO` and a compile-control record. | Equal start/limit is a long-running loop. |
| `?DO` | Run zero times when start equals limit. | Emit `QDO` and exit patch. | Implemented. |
| `LOOP` | Close direct `DO` or `?DO`. | Emit increment-by-one backward loop. | Requires matching `DO` family opener. |
| `+LOOP` | Close direct `DO` or `?DO` with an increment. | Emit `PLOOP` and backward target. | Prefer a nonzero signed increment. |
| `FOR` | Repeat `u` times with index starting at zero. | Emit `LIT 0` and `QDO`. | CF-inspired MIN0 extension. |
| `NEXT` | Close direct `FOR`. | Emit `LOOP`. | Requires matching `FOR`. |
| `LEAVE` | Exit the innermost direct counted loop. | Emit an exit patch for the innermost loop. | Requires counted-loop context. |

## Execution tokens and dynamic calls

| Word | Interpretation semantics | Compilation semantics | Status or required context |
| --- | --- | --- | --- |
| `DEFER` | Parse a name and create an unassigned call slot. | Currently rejected. | Run-time source parsing needs design. |
| `'` | Parse a name and return its `xt`. | Currently rejected. | Compare standard/CF role with `[']` before deciding. |
| `[']` | Context error in direct input. | Emit an `xt` literal for the following name. | Implemented compile-only syntax. |
| `IS` | Set the target of the following DEFER name. | Emit `DSET` only in `standard-build`. | Deliberately disabled in `safe-runtime`. |
| `ACTION-OF` | Return the current target `xt` of a DEFER name. | Emit code that reads the DEFER slot. | Unassigned target errors. |
| `DOES>` | Context error in direct input. | End constructor and begin child behavior. | Requires earlier definition-level `CREATE`. |

## Audit result

- The unjustified compilation restriction on `. EMIT CR TYPE` is removed.
- `WORDS` and allocation/source-defining words still have compilation semantics to review.
- Direct control uses buffering while definition control emits bytecode; both paths aim for the same results.
- Errors from `I J UNLOOP LEAVE` indicate missing loop context, not missing words.
- Every future word should define these three semantics and its required context before implementation.
