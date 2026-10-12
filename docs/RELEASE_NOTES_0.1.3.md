# MIN0 CORE FORTH 0.1.3 release notes

[Read this page in Japanese](RELEASE_NOTES_0.1.3_JP.md)

This interactive-learning and virtual-assembler release adds browser entry points for experimenting
with FORTH and for executing the CPU-independent virtual assembler reference model. It also includes
RP2350 Thumb generation, linking, independent decoding, and publication audits, but does not authorize
execution of the generated machine code on a Pico 2 W.

## Two browser learning environments

- Mobile Learning lets PC and iPhone users edit and execute a learning subset of FORTH while observing
  terminal output, final stack state, and per-word stack transitions. It includes `( ... )` comments and
  `RECURSE`.
- The virtual assembler Viewer lets users change source and input values, then reference-execute
  arithmetic, conditional branches, and checked memory access. It displays virtual-register changes,
  before-and-after stacks, and commit or abort results.
- The out-of-range memory example discards pending writes and restores the input stack.
- Both environments run inside the browser and do not access physical memory, IO, or a Pico 2 W.

## Virtual assembler and RP2350 backend

- The virtual ISA provides four registers, a fixed entry frame, staged outputs, labels, comparisons,
  branches, arithmetic, logic, shifts, rotates, and named memory capabilities.
- `LD32` and `ST32` lower to helpers that check range, alignment, and permission rather than to unchecked
  raw loads and stores.
- Main CODE, helper thunks, and private ABI veneers form one linked image whose complete byte coverage is
  checked by an independent decoder and bound to a SHA-256 receipt.
- The internal-SRAM target-publication host model tests the one-way `rw,nx` to `sealed rx` sequence and
  rejects ordering errors, modification, and post-seal writes.

## Learning through safe failure

- Producing an untyped cell value remains separate from permission to use it for memory, IO, or an
  indirect transfer.
- The design separates a Safety kernel, target-specific adapter, and explanatory Learning interface.
- Constrained targets may move long explanations to a Viewer, but retain compact error facts and recovery
  results on the target.

## Explicitly excluded from this release

- Generated RP2350 machine code is not executed on a Pico 2 W.
- Physical MPU configuration, target-side `rx` sealing, and live patching remain future work.
- Viewer CODE definitions are not yet installed as words in the normal FORTH dictionary.
- Array and structure descriptors remain a design direction rather than a 0.1.3 implementation.

## Pre-release verification

The release gate covers Python, Ruby, cross-implementation checks, JavaScript Viewers, the release
audit, and a reproducible ZIP. Final counts, checksums, and post-publication retrieval evidence belong
in the 0.1.3 release audit.
