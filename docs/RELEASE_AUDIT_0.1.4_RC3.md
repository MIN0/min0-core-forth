# MIN0 CORE FORTH 0.1.4-rc.3 candidate audit

[日本語版はこちらです](RELEASE_AUDIT_0.1.4_RC3_JP.md)

Candidate: `0.1.4-rc.3`

Status: in preparation. No tag or release is created until the pre-publication gates pass.

## Implemented evidence

- Focused safe `VARIABLE` and checked `@`/`!` tests: PASS.
- Focused paused-variable edit and Abort rollback tests: PASS.
- Focused `BREAK` Pause, Continue, and Abort tests: PASS.
- PC Viewer visual evaluation: PASS.
- Release allowlist audit: PASS.

## Gate A - before publication

- [ ] Verify safe variables, paused editing, and `BREAK` in iPhone Safari.
- [ ] Run `python tools\run_all_checks.py` in the user's normal Windows PowerShell and obtain
  `ALL CHECKS PASSED`.
- [ ] Complete the release allowlist audit with zero issues.
- [ ] Pass focused documentation and release-tool tests.
- [ ] Produce byte-identical ZIP files in two independent directories.

The Codex sandbox rejects child `ruby.exe` processes with exit code `3221225506`. Final Ruby-inclusive Gate A
therefore runs in the user's normal PowerShell and is recorded separately from product-code failures.

## Gate B - evaluation pre-release publication

- [ ] Create annotated tag `v0.1.4-rc.3`.
- [ ] Publish as a pre-release, not as `Latest`.
- [ ] Attach the ZIP and `SHA256SUMS.txt` assets.
- [ ] Do not modify existing tags or assets.

## Gate C - after publication

- [ ] Fetch the published assets into a fresh directory.
- [ ] Match ZIP size, SHA-256, and every manifest entry to the candidate.
- [ ] Run the allowlist audit and focused Mobile tests from the extracted tree.
- [ ] Verify the Mobile Learning and Virtual Assembler Pages deployments.

Record final values in this document as each gate completes.
