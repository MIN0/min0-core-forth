# MIN0 CORE FORTH 0.1.3 release candidate audit

[Read this page in Japanese](RELEASE_AUDIT_0.1.3_JP.md)

Status: local Gate A PASS. GitHub publication Gate B and post-publication Gate C are pending. The
audited version is `0.1.3-rc.1`; it is not yet an official release.

## Scope

The 0.1.3 candidate adds Mobile Learning for PC and iPhone, the browser virtual assembler Viewer, a
portable virtual instruction specification, the RP2350 Thumb backend and publication host model, and
learning and portability principles for safe failure.

It excludes Pico 2 W execution of generated machine code, physical MPU configuration, target-side
`rx` sealing, live patching, and installation of virtual assembler CODE in the normal FORTH dictionary.
The recommended official release remains `v0.1.2` until Gates B and C are complete.

## Gate A — local pre-publication evidence

- Executed: 2026-10-13 (Asia/Tokyo).
- Commit: `048ee06 Fix Windows cross-check working directory`.
- Command: `python tools\run_all_checks.py` in the user's normal Windows 11 PowerShell.
- Python unittest suite: PASS.
- Ruby: all 48 test files passed.
- Python/Ruby cross-language checks: all 50 check files passed.
- Final result: `ALL CHECKS PASSED`.
- The runner launched cross-checks from `workbench`, including the two checks that use relative demo paths.
- Documentation, release-tool, and virtual-assembler Viewer target tests: 15/15 passed.
- JavaScript virtual-assembler Viewer test: PASS.
- Release allowlist audit before adding this audit pair: 442 selected files and no issues.
- `git diff --check`: no issues.
- The restricted Codex sandbox's `ruby.exe` denial did not reproduce in normal PowerShell; the product
  test gate passed.

The final candidate containing this audit pair must repeat the allowlist audit and two independent
deterministic ZIP builds. The ZIP digest is stored in the adjacent `SHA256SUMS.txt` to avoid making this
audit self-referential.

## Gate B — GitHub publication

Pending. Publication records will include the `v0.1.3` tag and commit, GitHub Release URL and time,
artifact name, size and SHA-256, release status, GitHub Pages build and HTTPS state, and open secret
scanning and Dependabot alert counts.

## Gate C — independent post-publication verification

Pending. The public ZIP and `SHA256SUMS.txt` will be downloaded into a fresh directory and checked
against size, SHA-256, manifest, tag blobs, and published Pages. Representative Mobile Learning and
virtual assembler Viewer examples will be checked on PC and iPhone, followed by the all-check and
release-audit commands from the downloaded artifact.

This audit applies only to MIN0 CORE FORTH. It does not modify or publish MIN0 RASPI FORTH or
MSX0-FORTH.
