# MIN0 CORE FORTH raw bytecode v0.1

Status: executable draft for cross-implementation experiments. It is not yet a
persistent or release image format.

## Scalar representation

- Cell: unsigned 32-bit storage value
- Signed interpretation: 32-bit two's complement
- Address: 32-bit byte address
- Cell encoding: four bytes, little-endian
- False: `0x00000000`
- True: `0xFFFFFFFF`
- Arithmetic overflow: wrap modulo `2^32`

## Instruction encoding

Every instruction begins with one 8-bit opcode. `LIT`, `CALL`, `ICALL`, `BRANCH`,
`ZBRANCH`, `LOOP`, `PLOOP`, `QDO`, `LEAVE`, and `SERVICE` are followed immediately by
one 32-bit little-endian operand. All other v0.1 instructions are one byte
long.

| Opcode | Name | Stack effect / meaning |
|---:|---|---|
| `00` | `NOP` | no effect |
| `01` | `LIT x` | `( -- x )` |
| `02` | `CALL a` | push next `IP` on return stack; set `IP=a` |
| `03` | `EXIT` | pop return stack into `IP` |
| `04` | `BRANCH a` | set `IP=a` |
| `05` | `ZBRANCH a` | `( flag -- )`; branch when flag is zero |
| `06` | `FETCH` | `( a -- x )`; read one little-endian cell |
| `07` | `STORE` | `( x a -- )`; write one little-endian cell |
| `08` | `DROP` | `( x -- )` |
| `09` | `DUP` | `( x -- x x )` |
| `0A` | `SWAP` | `( x y -- y x )` |
| `0B` | `OVER` | `( x y -- x y x )` |
| `0C` | `ADD` | `( x y -- x+y )` |
| `0D` | `SUB` | `( x y -- x-y )` |
| `0E` | `MUL` | `( x y -- x*y )` |
| `0F` | `AND` | bitwise AND |
| `10` | `OR` | bitwise OR |
| `11` | `XOR` | bitwise XOR |
| `12` | `LESS` | signed comparison; return Forth true or false |
| `13` | `EQUAL` | cell equality; return Forth true or false |
| `14` | `HALT` | stop the VM normally |
| `15` | `DO` | `( limit start -- )`; push loop frame |
| `16` | `LOOP a` | increment index and branch until limit |
| `17` | `I` | copy innermost loop index to data stack |
| `18` | `UNLOOP` | discard innermost loop frame |
| `19` | `PLOOP a` | `( increment -- )`; signed increment and loop-boundary test |
| `1A` | `J` | copy next-outer loop index to data stack |
| `1B` | `QDO a` | `( limit start -- )`; branch to `a` if equal, else push frame |
| `1C` | `LEAVE a` | discard innermost loop frame and branch to `a` |
| `1D` | `CELL_PLUS` | `( address -- address+cell-bytes )` |
| `1E` | `CELLS` | `( n -- n*cell-bytes )` |
| `1F` | `ALIGNED` | `( address -- aligned-address )` |
| `20` | `C_FETCH` | `( byte-address -- char )`; zero-extend one byte |
| `21` | `C_STORE` | `( char byte-address -- )`; store low eight bits |
| `22` | `CHAR_PLUS` | `( byte-address -- byte-address+1 )` |
| `23` | `CHARS` | `( n -- n )` in the 8-bit byte-addressed profile |
| `24` | `ICALL slot` | read a colon XT from `slot`, validate it, then call its code address |
| `25` | `DSET slot` | `( xt -- )`; validate and store a colon XT into a DEFER slot when enabled |
| `26` | `SERVICE id` | invoke one target-owned numeric service; ID zero is reserved |

Binary operations pop the right operand first and the left operand second.
`ICALL` rejects a zero slot as an unassigned DEFER. It validates the slot read,
requires XT kind 1, reads the XT payload as a code address, and validates the
target instruction fetch before transferring control.
`DSET` additionally requires an image-build VM configuration bit. It validates
that the destination belongs to a kind-7 XT and that the supplied XT names an
executable colon word before changing the single slot cell. Runtime VMs and
Monitor-controlled VMs keep this instruction disabled.
`SERVICE` takes a non-address 32-bit immediate and therefore has no relocation. Before verified CODE is
sealed, the target registers trusted handlers. The verifier derives every required ID from actual CODE;
sealing rejects missing handlers and freezes both the exact image allowlist and the registry. R0 assigns
ID 1 to `terminal-type-v0.1 ( c-addr u -- )` as specified in `OUTPUT_SERVICE_BOUNDARY_R0.md`.

## Current addressing rule

Control-flow operands are absolute byte offsets from the beginning of a raw
image loaded at VM address zero. This keeps the first experiment simple, but
the image is not relocatable. Relative branches, relocation records, and an
image header remain open design decisions.

## Conformance rule

For each canonical `.fcb` vector, independent implementations must agree on:

1. final data-stack cells;
2. number of executed instructions;
3. success or VM-error category.

Python and Ruby implementations are intentionally separate. Neither may call
the other to implement VM behavior.
