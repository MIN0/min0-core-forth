# MIN0 CORE FORTH 0.1.3 compatibility release notes

[Read this page in Japanese](RELEASE_NOTES_0.1.3_JP.md)

Candidate: `0.1.3-rc.1`

This version incorporates source notation and execution-model lessons from standard FORTH and CF. It
reduces unnecessary differences between direct input and colon definitions while keeping the VM independent
of a particular terminal or hardware target. Python and Ruby remain equivalent executable specifications.

## Comments

- `( ... )` skips source through the next `)` without changing interpretation/compilation state or the
  DATA stack.
- Parenthesis comments may span physical lines. An unterminated comment executes none of its input block
  and rolls back an active definition.
- `\` is formally documented as the standard-style physical-line comment.

## Direct control structures

- The prompt accepts `IF ... ELSE ... THEN`, `BEGIN ... UNTIL`, `BEGIN ... AGAIN`, and
  `BEGIN ... WHILE ... REPEAT`.
- Direct `DO`/`?DO` through `LOOP`/`+LOOP` produces the same index results as definitions.
- Based on CF's `for ... next`, MIN0 defines `u FOR ... NEXT` as a zero-based, exactly `u`-iteration
  structure.
- Multiline input, mixed nesting, `I`, `J`, `LEAVE`, zero iterations, and buffer/execution/depth limits are
  covered.
- Mismatch, incomplete input, resource-limit, and execution failures restore the DATA and loop stacks to
  their state at direct-structure entry.

## Compilable output words

- `.`, `EMIT`, `CR`, and `TYPE` work both directly and inside colon definitions.
- Compiled forms use the CPU-independent `SERVICE` boundary.

| Word | Service | Stack effect |
| --- | ---: | --- |
| `TYPE` | 1 | `( c-addr u -- )` |
| `EMIT` | 2 | `( x -- )` |
| `.` | 3 | `( n -- )` |
| `CR` | 4 | `( -- )` |

Direct execution and services share handlers. Dedicated service 4 uses no temporary DATA-stack cell, so
`CR ( -- )` remains valid on a full DATA stack. An image requiring an unavailable service is rejected before
sealed execution.

## Documentation and compatibility audit

- Bilingual pocket references cover all 65 startup words printed by `WORDS`.
- A 65-word matrix records interpretation, compilation, and execution semantics plus required context.
- The execution-phase learning note explains why `: ... ;`, `[']`, `CREATE ... DOES>`, and `UNLOOP` are not
  all simple directly buffered pairs.
- Remaining compilation-semantics decisions for `WORDS` and selected allocation/source-defining words are
  explicit future work.

## Preserved boundaries

- No terminal-specific VM opcode is added.
- No physical MPU, FPGA, UART, or other target implementation is included.
- APIs, image formats, and service IDs remain experimental 0.1 interfaces.
- Signing seeds and HMAC keys remain public test fixtures unsuitable for deployment.
- Published `v0.1.0` through `v0.1.2` tags and assets remain unchanged.

Local Gate A evidence is recorded in the [0.1.3 release audit](RELEASE_AUDIT_0.1.3.md).
