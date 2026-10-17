# MIN0 CORE FORTH 0.1.4-rc.2 evaluation notes

[Read this page in Japanese](RELEASE_NOTES_0.1.4_RC2_JP.md)

Candidate: `0.1.4-rc.2` (local and unpublished)

This evaluation update keeps the published `v0.1.4-rc.1` browser-learning and virtual-assembler
baseline, then adds the Mobile Learning observation, execution-control, and bounded-input work that
passed PC and iPhone evaluation after that release.

## Mobile execution observation

- The Viewer shows initial and final DATA stacks, top-level and colon-definition execution, numbered
  words and invocations, source positions, typed call/return history, and a searchable word catalog.
- Loop traces are summarized by default and can be expanded when detailed repetition is needed.
- Chunked execution regularly returns control to the browser instead of monopolizing the UI thread.

## Monitor execution control

- Run, Pause, one-instruction Step, Continue, safe Stop, and rollback Abort use an explicit state
  machine and confirmed instruction-boundary snapshots.
- The current word, next instruction, source position, and caller history remain observable at safe
  stopping points.
- A Blob Worker normally isolates execution. A compatibility mode uses the same engine when the browser
  cannot create that Worker.

## Bounded input

- `KEY? ( -- flag )` observes a bounded transactional input queue without consuming it.
- `KEY ( -- byte )` consumes one UTF-8 byte or enters a non-busy `waiting-input` state.
- The queue and each input command are limited to 256 UTF-8 bytes. Invalid input is rejected without
  changing the running session.
- Input can be queued while paused without resuming execution. Stop preserves the current snapshot;
  Abort restores the pre-run stack, dictionary, and queue.

## Evaluated environments

- Focused Python and JavaScript regression checks pass in the development workspace.
- PC visual evaluation covers execution, monitoring, input, rejection, Stop, Abort, and screen reset.
- iPhone Safari evaluation covers one-byte input, paused two-byte input, capacity rejection, Stop,
  Abort, and screen reset on the GitHub Pages build.

## Explicit exclusions

- Safe `VARIABLE`, `@`, `!`, stopped-variable editing, and `BREAK` remain later Phase C work.
- Generated RP2350 code is not executed on a Pico 2 W. Physical MPU setup and live patching remain
  future work.
- Viewer CODE definitions are not installed in the normal FORTH dictionary.
- This is an evaluation candidate, not the final `0.1.4` release.

Full Python/Ruby Gate A, release allowlist audit, reproducible packaging, public-asset retrieval, and
Gate C verification must complete before publication. Published tags and assets remain unchanged.
