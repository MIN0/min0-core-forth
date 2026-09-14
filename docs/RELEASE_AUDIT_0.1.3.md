# MIN0 CORE FORTH 0.1.3 compatibility release audit

[Read this page in Japanese](RELEASE_AUDIT_0.1.3_JP.md)

Candidate: `0.1.3-rc.1`

Status: Gate A PASS; evaluation pre-release Gate B PASS; independently retrieved public-asset Gate C PASS.
Final `0.1.3` has not been published.

## Scope

This candidate covers comments, direct control structures, `FOR ... NEXT`, compilable `. EMIT CR TYPE`, and
the 65-word semantics and learning documentation. Published `v0.1.0` through `v0.1.2` tags and assets remain
unchanged. Basic division, double-cell arithmetic, rotates, byte-order conversion, and physical communication
targets are outside this candidate.

## Gate A -- local pre-publication verification

- VERSION: `0.1.3-rc.1`
- Release allowlist: 401 files, no issues
- Python: 336 tests passed
- Ruby: 48 test files passed
- Python/Ruby: 49 cross-language checks passed
- Startup vocabulary: all 65 words match both pocket references and semantics matrices
- Local Markdown links: 93 files checked, 0 broken links
- Release audit: PASS, with no personal-path, secret-material, internal-conversation, or other publication blocker
- Reproducible ZIP: two independent builds from identical source matched byte-for-byte

## Gate B -- evaluation pre-release publication

- Official [`v0.1.3-rc.1` pre-release](https://github.com/MIN0/min0-core-forth/releases/tag/v0.1.3-rc.1)
- Published: 2026-09-14 22:18:19 (Asia/Tokyo)
- Tagged commit: `43b0881643f76c1a1daa5c06810606d6e94415fa`
- The locally tested tree and tagged-commit tree share SHA-1 `98759e00d2416bde5f87cd0e5fe61ba6b86bf009`
- Artifact: `min0-core-forth-0.1.3-rc.1.zip`, 690780 bytes
- SHA-256: `4dca02ad18d18eab23d6f49032054556f3b0441ec6e5df8d54b3740d6018895a`
- `SHA256SUMS.txt`: 97 bytes and matches the ZIP digest
- Published as a non-draft pre-release without replacing final `v0.1.2`

## Gate C -- independent retrieval of public assets

- The public ZIP and `SHA256SUMS.txt` were downloaded into a new directory; size and SHA-256 match the
  pre-publication candidate.
- All 401 ZIP source files match `RELEASE_MANIFEST.txt`; every SHA-256 passes, with zero missing or extra files.
- The extracted public tree's release audit passes with 401 files, no issues, and VERSION=`0.1.3-rc.1`.
- The extracted public tree passes 336 Python tests, 48 Ruby test files, and 49 Python/Ruby checks.
- GitHub Release metadata reports `prerelease=true`, `draft=false`, and two assets.

This evidence makes the evaluation candidate suitable for sharing with FORTH2020 and other testers. It does
not claim publication of final `0.1.3`; feedback and any necessary fixes precede a fresh final-release audit.

This audit applies only to MIN0 CORE FORTH and does not modify or publish MSX0-FORTH.
