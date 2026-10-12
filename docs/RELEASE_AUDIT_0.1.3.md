# MIN0 CORE FORTH 0.1.3 compatibility release audit

[Read this page in Japanese](RELEASE_AUDIT_0.1.3_JP.md)

Candidate: `0.1.3-rc.1`

Status: Gate A PASS; evaluation pre-release Gate B PASS; independently retrieved public-asset Gate C PASS.
Final `0.1.3` has not been published.

## Scope

This candidate covers comments, direct control structures, `FOR ... NEXT`, compilable `. EMIT CR TYPE`, and
the 65-word semantics and learning documentation. Published `v0.1.0` through `v0.1.2` tags and assets remain
unchanged.

## Gate A -- local pre-publication verification

- VERSION: `0.1.3-rc.1`
- Release allowlist: 401 files, no issues
- Python: 336 tests passed
- Ruby: 48 test files passed
- Python/Ruby: 49 cross-language checks passed
- Startup vocabulary: all 65 words match both pocket references and semantics matrices
- Local Markdown links: 93 files checked, 0 broken links
- Reproducible ZIP: two independent builds from identical source matched byte-for-byte

## Gate B -- evaluation pre-release publication

- Official [`v0.1.3-rc.1` pre-release](https://github.com/MIN0/min0-core-forth/releases/tag/v0.1.3-rc.1)
- Published: 2026-09-14 22:18:19 (Asia/Tokyo)
- Tagged commit: `43b0881643f76c1a1daa5c06810606d6e94415fa`
- Artifact: `min0-core-forth-0.1.3-rc.1.zip`, 690780 bytes
- SHA-256: `4dca02ad18d18eab23d6f49032054556f3b0441ec6e5df8d54b3740d6018895a`
- Published as a non-draft pre-release without replacing final `v0.1.2`

## Gate C -- independent retrieval of public assets

- The public ZIP and checksum were downloaded into a new directory and matched the pre-publication candidate.
- All 401 ZIP source files match `RELEASE_MANIFEST.txt`, with zero missing or extra files.
- The extracted public tree passes 336 Python tests, 48 Ruby test files, and 49 Python/Ruby checks.

This evidence makes the evaluation candidate suitable for sharing with testers. It does not claim publication
of final `0.1.3`.

This audit applies only to MIN0 CORE FORTH and does not modify or publish MSX0-FORTH.
