# MIN0 CORE FORTH 0.1.4 local-candidate audit

[Read this page in Japanese](RELEASE_AUDIT_0.1.4_JP.md)

Candidate: `0.1.4-rc.1`

Status: local Gate A PASS. GitHub publication Gate B and independent post-publication Gate C are
pending. The published 0.1.3 branch and the previous local virtual-assembler branch were combined and
then verified again; pre-merge results are retained only as historical evidence.

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

Pending. No `v0.1.4-rc.1` tag, GitHub Release, asset, or Pages publication has been created.

## Gate C — independent post-publication verification

Pending. A published artifact must be downloaded into a fresh directory and checked against its digest,
manifest, tag contents, Pages behavior, representative browser examples, and the complete test commands.

This audit applies only to MIN0 CORE FORTH. It does not modify or publish MIN0 RASPI FORTH or
MSX0-FORTH.
