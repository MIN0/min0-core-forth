# MIN0 CORE FORTH 0.1.4 local-candidate audit

[Read this page in Japanese](RELEASE_AUDIT_0.1.4_JP.md)

Candidate: `0.1.4-rc.1`

Status: integration audit in progress. The published 0.1.3 branch and the previous local virtual-
assembler branch have been combined, so pre-merge results are historical evidence only and do not
constitute a pass for this candidate.

## Scope

The candidate combines the 0.1.3 compatibility improvements with Mobile Learning, the browser virtual
assembler Viewer, portable virtual instructions, the RP2350 Thumb backend and publication host model,
and safe-failure learning and portability principles.

It excludes execution of generated machine code on Pico 2 W, physical MPU configuration, target-side
`rx` sealing, live patching, and installation of Viewer CODE in the normal dictionary.

## Gate A — local integration verification

Pending. It must include Python, Ruby in normal PowerShell, cross-language checks, JavaScript Viewer
tests, documentation checks, release allowlist audit, `git diff --check`, and two deterministic ZIP
builds from the integrated tree.

## Gate B — GitHub publication

Pending. No `v0.1.4-rc.1` tag, GitHub Release, asset, or Pages publication has been created.

## Gate C — independent post-publication verification

Pending. A published artifact must be downloaded into a fresh directory and checked against its digest,
manifest, tag contents, Pages behavior, representative browser examples, and the complete test commands.

This audit applies only to MIN0 CORE FORTH. It does not modify or publish MIN0 RASPI FORTH or
MSX0-FORTH.
