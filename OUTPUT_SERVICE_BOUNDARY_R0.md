# MIN0 CORE FORTH verified output-service boundary R0

Status: executable R0 experiment in Python and Ruby.

## Problem

Compiled `."` must emit text while a colon word is running inside the VM. Adding a terminal-specific
opcode would couple the CPU-independent VM to UART, USB, a host console, or Viewer. Calling an arbitrary
host callback selected by image data would instead create an unsafe extension surface.

R0 therefore uses a generic, verified service-call boundary. The VM knows how to request a numbered
service but does not know how a terminal works.

## Instruction

```text
SERVICE <u32 service-id>
```

`service-id` is an immediate non-address value, not a relocation. The bytecode verifier must decode the
complete instruction, keep its operand out of the instruction-boundary set, and reject IDs absent from
the selected target profile.

The first profile service is symbolically named `terminal-type-v0.1` and has R0 numeric ID `1`.
ID zero is reserved and rejected.

Compiled `." text"` will then be equivalent to:

```text
LIT <relocated DATA address>
LIT <byte length>
SERVICE 1  # terminal-type-v0.1
```

The first two instructions are the compiled `S"` path already implemented and tested.

## Authority boundary

- The trusted target/host constructs the service registry before verified execution is sealed.
- Image source, dictionary contents, DATA bytes, Viewer text, and Monitor commands cannot register or
  replace a service handler.
- The verifier derives the required service-ID set from actual decoded CODE; SERVICE operands never use
  relocation records. The signed envelope already binds the CODE and manifest bytes, and the Loader reruns
  the verifier instead of trusting a separate mutable declaration.
- Sealing requires every derived ID to exist in the target-owned registry. It then freezes both the exact
  image allowlist and the registry before CODE runs. A failed requirement leaves CODE unsealed.
- The R0 terminal handler is trusted host code and deliberately receives no image-selected callback. It
  uses only the VM stack, readable memory, and target-owned output collector. The VM does not sandbox a
  buggy trusted handler, so every future service needs its own narrow contract and threat review.

This keeps image freedom separate from device authority. A port may implement the same symbolic service
with a host collector, UART driver, FPGA FIFO, debug channel, or intentionally no service at all.

## `terminal-type-v0.1` contract

The service has Forth stack effect `( c-addr u -- )` and reuses the exact byte policy of interpret-state
`TYPE`:

1. require two DATA-stack cells without popping them;
2. for nonzero `u`, validate and read the complete range from one readable region;
3. prepare the complete output fragment before changing stack or sink;
4. commit the fragment to the target-owned sink;
5. only after successful commit, remove `c-addr u`.

Zero length consumes both arguments without dereferencing `c-addr`. Stack underflow, unknown service,
range fault, permission fault, sink rejection, or unavailable device leaves stack and prior output
unchanged. Partial output is outside the reference contract.

## Executable verification and audit records

The Python/Ruby experiment now checks:

- valid compiled `."` and nested colon calls;
- duplicate or unknown service registration/use;
- service operand truncation, zero ID, forbidden relocation, and branch into its four operand bytes;
- missing required service before seal and immutable registration after seal;
- invalid string range with unchanged stack and prior output;
- zero-length output;
- exact output and audit trace agreement across Python and Ruby.

`service_output_demo.py/.rb` compile `: HELLO ." Hello" ;` and a nested caller, derive required ID `[1]`,
seal CODE to `rx` and DATA to `r`, and then emit the exact stream `Hello Service`. The cross-language check
requires both implementations to agree on those facts.

Viewer and AI explanations continue to treat the output bytes as observed data, never as HTML, code,
service declarations, or instructions.

## Deliberately excluded

- loading callback code from the image;
- resolving service names from mutable dictionary strings at runtime;
- silently falling back to raw host execution;
- granting a service general dictionary, loader, signing-key, or Monitor authority;
- defining network, file, or shell services as a side effect of terminal output.

This boundary is intentionally narrower than a general foreign-function interface.
