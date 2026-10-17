# MIN0 CORE FORTH 0.1.4-rc.2 candidate audit

[Read this page in Japanese](RELEASE_AUDIT_0.1.4_RC2_JP.md)

Candidate: `0.1.4-rc.2`

Status: Gates A, B, and C passed for the `v0.1.4-rc.2` evaluation pre-release.

## Completed pre-Gate evidence

- Phase C Mobile input-control PC visual evaluation: PASS.
- Phase C iPhone Safari evaluation on GitHub Pages: PASS.
- Focused Mobile Python tests: 10 passed.
- Focused Mobile JavaScript test groups: passed.
- Generated Mobile HTML build identity refreshed after iPhone verification.
- `git diff --check`: PASS for the preparation changes.

## Gate A -- passed

- Date: 2026-10-17 (Asia/Tokyo).
- User's normal Windows PowerShell: `python tools\run_all_checks.py`.
- Python suite: passed.
- Ruby: all 50 test files passed.
- Python/Ruby cross-language checks: all 51 check files passed.
- Final result: `ALL CHECKS PASSED`.
- Release allowlist audit: 492 files, zero issues.
- Documentation/release-tool focused tests: 14/14 passed.
- Built the candidate into two independent directories and confirmed byte-identical ZIP files.
- Store the final ZIP byte size and SHA-256 beside the artifact in `SHA256SUMS.txt` and in the
  publication record, avoiding a self-referential digest inside the ZIP.

The restricted Codex sandbox denies the `ruby.exe` child process with exit code `3221225506`. The
five Python-suite failures seen there are all Ruby-launcher comparison tests. The user's normal
PowerShell environment does not reproduce that restriction and passed the complete test run.

## Gate B -- evaluation pre-release published

- Published: 2026-10-17 13:10 JST.
- Annotated tag: `v0.1.4-rc.2`, commit `60b6baa0067eed3211f03b4a2b1727656fced2e3`.
- Release: <https://github.com/MIN0/min0-core-forth/releases/tag/v0.1.4-rc.2>
- State: public evaluation pre-release, not final and not `Latest`.
- ZIP: `min0-core-forth-0.1.4-rc.2.zip`, 960281 bytes.
- ZIP SHA-256: `2f74f1d019876bb07aafc4a9950051748e5904c018474ed746baf3d08da7b161`.
- `SHA256SUMS.txt` is published as a separate asset.
- Existing tags and assets were not changed.

## Gate C -- independent post-publication verification

- Retrieved the public ZIP and checksum into a new directory.
- The retrieved ZIP byte count and SHA-256 match the Gate A candidate and published checksum.
- Verified existence and SHA-256 for all 492 manifest entries with zero missing or mismatched files.
- The extracted-tree release allowlist audit passed with 492 files and zero issues.
- Mobile Python tests and seven Mobile JavaScript test groups passed from the extracted artifact.
- The Mobile Learning and Virtual Assembler Pages URLs both returned HTTP 200. The Mobile page contains
  the evaluated build identity and screen-reset control; the Virtual Assembler page is also served.

The release asset necessarily contains the pre-publication state of this audit. This post-publication
appendix is recorded on `main` after verification of the immutable tagged artifact; the artifact, tag,
and checksum are not changed.
