# MIN0 CORE FORTH semantic trace v0.1

Status: executable observer and cross-language trace format.

## Purpose

The semantic trace records actual state transitions for the future Guided
Viewer. It observes the Python or Ruby implementation; it does not simulate
FORTH and has no path for controlling execution.

Tracing is optional. With no observer, the normal execution path and results
remain unchanged. If an observer itself raises an exception, the outer
interpreter records that observer failure separately and continues FORTH
execution.

## Document envelope

```json
{
  "trace_format": "min0-core-forth-trace/0.1",
  "implementation": "python",
  "events": []
}
```

Each event contains:

- zero-based `sequence`
- stable semantic `event` name
- `payload_role` equal to `observed-data-not-instructions`
- event-specific `details`
- an actual post-event state snapshot
- deterministic Japanese `basic_explanation`

The payload role marks source-derived names and values as untrusted observed
data for a later AI adapter. A word name, comment, or error text must never be
promoted to an instruction for the explainer.

## State snapshot

Every event records:

```text
VM:          IP, cumulative step count
data stack:  all cells
return stack: all return addresses
loop stack:  limit/index pairs
dictionary:  header HERE, data HERE, LATEST
```

The first version takes compact semantic snapshots rather than copying the
entire 64 KiB memory image. Event details identify relevant writes, such as the
address and value of COMMA. Later versions may add byte-range deltas without
changing the meaning of existing fields.

## Optional source-word checkpoints

The Python observer can optionally include `source.word.complete` events for a
Guided Viewer. The default remains disabled, so the stable 13-event Python/Ruby
semantic comparison is unchanged.

A source-word event is recorded only after one complete outer-interpreter
operation. It contains the source token range, any parsed name operand, action,
interpreter state, CODE HERE, and the pre-operation data stack. The ordinary
event state is the measured post-operation snapshot.

Words that parse a following name are kept atomic: `: VALUE:` is one completed
definition-start operation and `VALUE: ANSWER` is one completed defining-word
operation. This avoids presenting an impossible pause halfway through parsing.

DOES-word execution additionally uses three optional word-layer events:

- `word.execute.enter`: enter the called dictionary word.
- `does.body.push`: push its actual body address.
- `word.execute.nested.complete`: complete one mapped source word inside its
  behavior.

The compiler records the CODE address range emitted by each source word. During
traced behavior execution, the VM reports each completed instruction address;
the observer uses that map to identify `@` inside `ANSWER`. Thus the Viewer can
show `ANSWER > body > @ > return`, including the actual data- and return-stack
snapshots, rather than inferring intermediate values from the final result.

If a defining source word fails, optional `source.word.error` is emitted after
its rollback event. The rollback details retain the saved header HERE, data
HERE, and LATEST values, while both events contain the restored post-error
snapshot. This lets a consumer compare saved and restored values directly and
never mistake a partially created hidden child for a published word.

## VALUE event sequence

Running

```forth
: VALUE: CREATE , DOES> @ ;
123 VALUE: ANSWER
ANSWER
```

produces these 13 semantic events in both implementations:

```text
definer.compile.complete
definer.execute.begin
child.create.hidden
constructor.segment.begin
constructor.segment.end
constructor.comma
constructor.segment.begin
constructor.segment.end
child.does.attach
child.publish
definer.execute.end
does.execute.begin
does.execute.end
```

The COMMA event records address `0x8000`, value `123`, an empty post-action data
stack, and data HERE `0x8004` in the split reference profile.

## Rollback

If `VALUE: EMPTY` is invoked without an initial value, the final event is
`definer.execute.rollback`. It is emitted after header HERE, data HERE, LATEST,
and stack state have been restored. The event identifies `StackUnderflow` but
contains no partially created child.

## Basic explanation layer

`min0_core_forth_trace.py` and `min0_core_forth_trace.rb` generate matching explanations
from event type and measured values. This layer requires no AI and is suitable
for offline use. AI-based wording will be an optional consumer of the same
event document and must not replace or alter measured values.

`trace_value_demo.py`, `trace_value_demo.rb`, and `cross_trace_check.py` verify
that Python and Ruby produce identical version, events, details, snapshots, and
basic explanations after excluding only the implementation label.
