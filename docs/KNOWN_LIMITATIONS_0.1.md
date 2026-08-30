# MIN0 CORE FORTH 0.1 known limitations

Status: applies to releases `0.1.0` and `0.1.1`.

## Language and compatibility

- This release does not claim complete compliance with a Forth standard.
- The implemented word set is intentionally small and educational.
- The 32-bit, little-endian, 64 KiB virtual memory profile is a reference profile, not a universal CORE
  limit and not yet configurable at runtime.
- Quoted text uses one byte per character, U+0000..U+00FF. UTF-8 and Japanese source strings are not yet
  a frozen target profile.
- `.`, `EMIT`, `CR`, and `TYPE` remain interpret-state host words. Compiled `."` is available through the
  verified `terminal-type-v0.1` service boundary.
- APIs, image formats, and machine identifiers are experimental `0.1` interfaces and may evolve in later releases.

## Host and target boundary

- Python and Ruby are executable specifications. No physical MPU, FPGA, Flash, EEPROM, UART, TPM, or
  hardware memory-protection target is included in this release.
- The reference terminal collects output deterministically instead of automatically writing arbitrary
  control bytes to a real terminal.
- The offline Viewer displays measured traces but does not execute edited source.
- Spinel packaging is not currently supported; compatibility depends on future Spinel support for the
  Ruby runtime features and libraries used here.

## Security boundary

- All embedded signing seeds and HMAC keys are public deterministic fixtures and provide no deployment
  security.
- The security models demonstrate policies and rejection behavior; they are not a certification.
- Trusted host service handlers are not sandboxed by the VM. Each new service requires a narrow contract
  and separate threat review.
- Resource exhaustion, hostile host code, side channels, fault injection, physical attacks, compromised
  build systems, and secure production key custody are outside the present guarantee.
- Development mode intentionally permits source definition and experimentation. Only the explicitly
  sealed safe-runtime path applies W^X and structural dictionary protection.

## Release boundary

- Source and documentation use the MIT License. This permits reuse but does not certify security or
  guarantee fitness for a particular use; see `LICENSE_AND_SECURITY.md`.
- The official repository is <https://github.com/MIN0/min0-core-forth>. Release tag `v0.1.0` identifies
  the first release; `v0.1.1` is its navigation, packaging, and documentation maintenance release.
- Forks and modified builds are welcome but should use a distinct build name or version suffix so users
  can distinguish them from the official release.
