# MIN0 CORE FORTH 0.1.4-rc.4 candidate audit

[日本語版はこちらです](RELEASE_AUDIT_0.1.4_RC4_JP.md)

Candidate: `0.1.4-rc.4`

Status: Gate A is in progress after correcting the Windows Ruby baseline. The Ruby-inclusive run in the user's normal PowerShell remains.

## Candidate delta

- Preserve the safe `VARIABLE`, checked `@`/`!`, paused editing, and `BREAK` implementation already evaluated.
- Correct Quick Start from Ruby 4.0 to the Ruby 3.4.x release baseline.
- Record Ruby 3.4.11 x64-mingw-ucrt as the Windows Gate A interpreter.
- Add the device-availability guide and Capability Tour direction.
- Leave the existing `v0.1.4-rc.3` tag unchanged and unpublished.

## Gate A - before publication

- [ ] Record Ruby, JSON, and OpenSSL versions from the user's normal PowerShell.
- [ ] Run `python tools\run_all_checks.py` and obtain `ALL CHECKS PASSED` with Ruby 3.4.11.
- [x] Complete the release allowlist audit: 500 selected files, zero issues.
- [x] Pass focused documentation and release-tool tests: 14/14.
- [x] Produce byte-identical ZIP files in two independent directories (record the final value in the external `SHA256SUMS.txt`).

## Gate B - evaluation pre-release publication

- [ ] Create annotated tag `v0.1.4-rc.4`.
- [ ] Publish as a pre-release, not as `Latest`.
- [ ] Attach the ZIP and `SHA256SUMS.txt` assets.
- [ ] Do not modify existing tags or assets.

## Gate C - after publication

- [ ] Fetch the published assets into a fresh directory.
- [ ] Match ZIP size, SHA-256, and every manifest entry to the candidate.
- [ ] Run the allowlist audit and focused Mobile tests from the extracted tree.
- [ ] Verify the Mobile Learning and Virtual Assembler Pages deployments.
