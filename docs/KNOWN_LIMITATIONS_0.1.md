# MIN0 CORE FORTH 0.1 known limitations

Status: applies to releases `0.1.0` through `0.1.3` and the local `0.1.4` candidate.

## Language and compatibility

- This release does not claim complete compliance with a Forth standard.
- The implemented word set is intentionally small and educational.
- The 32-bit, little-endian, 64 KiB virtual memory profile is a reference profile, not a universal CORE
  limit and not yet configurable at runtime.
- Quoted text uses one byte per character, U+0000..U+00FF. UTF-8 and Japanese source strings are not yet
  a frozen target profile.
- In releases `0.1.0` through `0.1.2`, `.`, `EMIT`, `CR`, and `TYPE` are interpret-state-only host words.
  The current post-release development version resolves this gap through verified services 1 through 4.
  Until that work is included in a release, note the behavioral difference between released tags and the
  development tree.
- APIs, image formats, and machine identifiers are experimental `0.1` interfaces and may evolve in later releases.

## Host and target boundary

- Python and Ruby are executable specifications. No physical MPU, FPGA, Flash, EEPROM, UART, TPM, or
  hardware memory-protection target is included in this release.
- The reference terminal collects output deterministically instead of automatically writing arbitrary
  control bytes to a real terminal.
- The Guided Viewer displays measured traces and does not execute edited source. Mobile Learning and the
  virtual assembler Viewer execute browser reference models but do not access physical memory, IO, or a Pico 2 W.
- The RP2350 backend generates, links, and audits Thumb code, but the 0.1.4 candidate does not execute it on hardware,
  configure a physical MPU, or perform target-side `rx` sealing.
- Viewer CODE definitions are not installed in the normal FORTH dictionary, and an integrated trace across
  normal words and virtual assembler CODE is not yet implemented.
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
  the first release; `v0.1.1` improves navigation and packaging; `v0.1.2` formally packages the
  bilingual entry paths, pocket word reference, and learning references; evaluation pre-release
  `v0.1.3-rc.1` adds compatibility improvements; the unpublished `0.1.4-rc.1` candidate adds browser
  learning environments and the virtual assembler/RP2350 audit pipeline.
- Forks and modified builds are welcome but should use a distinct build name or version suffix so users
  can distinguish them from the official release.
