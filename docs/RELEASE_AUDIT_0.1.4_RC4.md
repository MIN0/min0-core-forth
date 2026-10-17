# MIN0 CORE FORTH 0.1.4-rc.4 candidate audit

[日本語版はこちらです](RELEASE_AUDIT_0.1.4_RC4_JP.md)

Candidate: `0.1.4-rc.4`

Status: Gate A passed. The full run succeeded with Ruby 3.4.11, JSON 2.9.1, and OpenSSL 3.6.4.

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

- [ ] Fetch the published assets into a fresh directory.
- [ ] Match ZIP size, SHA-256, and every manifest entry to the candidate.
- [ ] Run the allowlist audit and focused Mobile tests from the extracted tree.
- [ ] Verify the Mobile Learning and Virtual Assembler Pages deployments.
