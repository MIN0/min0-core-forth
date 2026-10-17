# MIN0 CORE FORTH 0.1.4-rc.4 candidate audit

[日本語版はこちらです](RELEASE_AUDIT_0.1.4_RC4_JP.md)

Candidate: `0.1.4-rc.4`

Status: Gates A, B, and C passed. The published pre-release was independently downloaded and verified.

## Candidate delta

- Preserve the safe `VARIABLE`, checked `@`/`!`, paused editing, and `BREAK` implementation already evaluated.
- Correct Quick Start from Ruby 4.0 to the Ruby 3.4.x release baseline.
- Record Ruby 3.4.11 x64-mingw-ucrt as the Windows Gate A interpreter.
- Add the device-availability guide and Capability Tour direction.
- Leave the existing `v0.1.4-rc.3` tag unchanged and unpublished.

## Gate A - before publication

- [x] Confirm Ruby 3.4.11 x64-mingw-ucrt in the user's normal PowerShell.
- [x] Confirm JSON 2.9.1 and OpenSSL 3.6.4 in the user's normal PowerShell.
- [x] Run `python tools\run_all_checks.py` with Ruby 3.4.11: `ALL CHECKS PASSED` (1 Python suite, 50 Ruby files, 51 cross-language checks).
- [x] Complete the release allowlist audit: 500 selected files, zero issues.
- [x] Pass focused documentation and release-tool tests: 14/14.
- [x] Produce byte-identical ZIP files in two independent directories (record the final value in the external `SHA256SUMS.txt`).

## Gate B - evaluation pre-release publication

- [x] Create annotated tag `v0.1.4-rc.4`.
- [x] Publish as a pre-release, not as `Latest`.
- [x] Attach the ZIP and `SHA256SUMS.txt` assets.
- [x] Do not modify existing tags or assets.

Published at <https://github.com/MIN0/min0-core-forth/releases/tag/v0.1.4-rc.4>.

## Gate C - after publication

- [x] Fetch the published assets into a fresh directory.
- [x] Match ZIP size (986153 bytes), SHA-256 (`91E577A3C5F79DC2186FD7C88A5F562892D075391956CC120FF5DD4537D9733D`), and all 500 manifest entries to the candidate.
- [x] Run the allowlist audit (500 files, zero issues) and focused Mobile tests (10/10 passed) from the extracted tree.
- [x] Verify the [Mobile Learning](https://min0.github.io/min0-core-forth/viewer/mobile-forth.html) and [Virtual Assembler](https://min0.github.io/min0-core-forth/viewer/virtual-assembler.html) Pages deployments.
