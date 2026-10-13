# MIN0 CORE FORTH 0.1.4 local-candidate audit

[Read this page in Japanese](RELEASE_AUDIT_0.1.4_JP.md)

Candidate: `0.1.4-rc.1`

Status: Gates A, B, and C PASS for the `v0.1.4-rc.1` evaluation pre-release. The published 0.1.3
branch and the previous local virtual-assembler branch were combined and then verified again;
pre-merge results are retained only as historical evidence.

## Scope

The candidate combines the 0.1.3 compatibility improvements with Mobile Learning, the browser virtual
assembler Viewer, portable virtual instructions, the RP2350 Thumb backend and publication host model,
and safe-failure learning and portability principles.

It excludes execution of generated machine code on Pico 2 W, physical MPU configuration, target-side
`rx` sealing, live patching, and installation of Viewer CODE in the normal dictionary.

## Gate A — local integration verification

- Executed: 2026-10-13 (Asia/Tokyo).
- Command in the user's normal Windows PowerShell: `python tools\run_all_checks.py`.
- Python suite: PASS.
- Ruby: all 50 test files passed.
- Python/Ruby cross-language checks: all 51 check files passed.
- Final result: `ALL CHECKS PASSED`.
- Mobile Learning JavaScript test: PASS.
- Virtual assembler browser JavaScript test: PASS.
- Release allowlist audit: 465 selected files, no issues.
- `git diff --check`: no issues.
- Two independent ZIP builds from the final Gate A commit are byte-for-byte identical. Their digest is
  stored beside the candidate artifact so this document does not make the package hash self-referential.

The restricted Codex sandbox still rejects child `ruby.exe` launches with `0xC0000022`; this did not
reproduce in normal PowerShell, where the complete product gate passed.

## Gate B — GitHub publication

- Published: 2026-10-13 21:07 JST.
- Tag: `v0.1.4-rc.1` at commit `c8ff554aa9b8a129ca6f4746a899954c50ed47c9`.
- Release: <https://github.com/MIN0/min0-core-forth/releases/tag/v0.1.4-rc.1>
- Status: public evaluation pre-release, not a final release.
- ZIP: `min0-core-forth-0.1.4-rc.1.zip`, 861703 bytes.
- ZIP SHA-256: `1215eaabc5d32b0cb16b03c4782d46d77710b31938cda8fd1542ffe6c51dd0d3`.
- `SHA256SUMS.txt` was published as a separate asset.
- GitHub Pages built commit `c8ff554` successfully with HTTPS enforced.

## Gate C — independent post-publication verification

- The two release assets were downloaded from GitHub into a new directory.
- The downloaded ZIP size and SHA-256 match Gate B and the published checksum file.
- All 465 manifest entries exist and match their recorded SHA-256 values.
- The extracted tree passes the release allowlist audit with 465 selected files and no issues.
- Mobile Learning and virtual assembler JavaScript tests pass from the extracted public artifact.
- The two Pages URLs return HTTP 200. The published virtual-assembler HTML matches the tagged local file;
  both pages contain their required executable scripts and controls.
- iPhone hardware display remains a recommended user observation, not a claim of automated Gate C.

The release asset necessarily contains the pre-publication form of this audit. This post-publication
section is recorded on `main` after verifying the immutable tagged artifact and does not alter that
artifact, tag, or checksum.

This audit applies only to MIN0 CORE FORTH. It does not modify or publish MIN0 RASPI FORTH or
MSX0-FORTH.
