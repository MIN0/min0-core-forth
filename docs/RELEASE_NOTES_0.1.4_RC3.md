# MIN0 CORE FORTH 0.1.4-rc.3 evaluation notes

[日本語版はこちらです](RELEASE_NOTES_0.1.4_RC3_JP.md)

Candidate: `0.1.4-rc.3` (local and unpublished)

This evaluation update keeps the Mobile execution observation, pause/resume control, and bounded input
published in `v0.1.4-rc.2`, then adds safe one-cell variables and an explicit Monitor break point.

## Safe VARIABLE

- `VARIABLE` registers one zero-initialized cell in a dedicated logical region.
- Checked `@` and `!` accept only registered logical addresses. Arbitrary or stale values stop with
  `InvalidAddress` while preserving the pre-check stack.
- A confirmed Pause shows each registered variable name, logical address, and current value.
- Paused editing validates the session state, variable name, and 32-bit cell range and records the change.
- Abort restores variable values, definitions, and the allocator to the pre-run snapshot.

## BREAK

- `BREAK ( -- )` pauses at its confirmed instruction boundary in a colon word or main sequence.
- The snapshot exposes the current word, instruction number, source position, caller history, and `BREAK` token.
- Continue resumes immediately after `BREAK`; Step, safe Stop, and Abort use the normal paused-state rules.
- A synchronous reference run without a Monitor reports `BreakUnavailable` instead of discarding the request.

## Diagnostic display

- Trace and word-catalog data retained after Abort are explicitly identified as pre-rollback observation records.
- VM rollback is separate from diagnostic retention; Screen Reset removes the retained display records.

## Evaluation scope

- Safe variables, paused editing, and `BREAK` passed focused automation and PC visual evaluation.
- iPhone Safari visual evaluation, full Gate A, reproducible packaging, and post-publication Gate C remain required
  before publication.

## Explicit exclusions

- Arbitrary memory addresses, arrays and structures, persistent variables, and general I/O access are not provided.
- Generated RP2350 machine code is not executed on Pico 2 W; MPU setup and live patching remain future work.
- This is an evaluation candidate, not the final `0.1.4` release.

Existing published tags and assets remain immutable.
