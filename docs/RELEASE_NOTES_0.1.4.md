# MIN0 CORE FORTH 0.1.4 local-candidate notes

[Read this page in Japanese](RELEASE_NOTES_0.1.4_JP.md)

Candidate: `0.1.4-rc.1` (published evaluation pre-release)

This candidate integrates the published 0.1.3 compatibility work with browser learning, a portable
virtual assembler, and the RP2350 code-generation and audit experiments.

## Browser learning

- Mobile Learning lets PC and iPhone users edit and execute a learning subset of FORTH while observing
  terminal output, final stack state, and per-word stack transitions. It supports `( ... )` comments and
  `RECURSE`.
- The virtual assembler Viewer reference-executes arithmetic, conditional branches, and checked memory
  access. It displays virtual-register changes, before-and-after stacks, and commit or abort results.
- Both environments run in the browser and do not access physical memory, IO, or a Pico 2 W.

## Virtual assembler and RP2350 backend

- The virtual ISA uses a fixed entry frame, named virtual registers, staged outputs, labels, branches,
  arithmetic, logic, shifts, rotates, and named memory capabilities.
- `LD32` and `ST32` lower to checked helpers instead of unchecked raw memory operations.
- The linked RP2350 image is independently decoded and bound to an audit receipt.
- The publication host model checks the one-way `rw,nx` to `sealed rx` transition.

## Compatibility baseline

This candidate retains the 0.1.3 comments, direct control structures, `FOR ... NEXT`, and compilable
`. EMIT CR TYPE`. The combined vocabulary is documented and checked after integration.

## Explicit exclusions

- Generated RP2350 code is not executed on a Pico 2 W.
- Physical MPU setup, target-side `rx` sealing, and live patching remain future work.
- Viewer CODE definitions are not installed in the normal FORTH dictionary.
- Array and structure descriptors remain a design direction rather than a 0.1.4 implementation.

The restricted Codex sandbox may reject `ruby.exe`; the final Ruby gate must therefore also run from
the user's normal PowerShell session.
