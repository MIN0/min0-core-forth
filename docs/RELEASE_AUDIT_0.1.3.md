# MIN0 CORE FORTH 0.1.3 compatibility release audit

[Read this page in Japanese](RELEASE_AUDIT_0.1.3_JP.md)

Candidate: `0.1.3-rc.1`

Status: local Gate A PASS. No tag, GitHub Release, or public asset has been created.

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

## Gate B and Gate C

Not performed. Only an explicit publication decision may authorize creation of a tag, Release, and assets,
followed by independent retrieval and verification. Passing local Gate A does not claim a published final
release.

This audit applies only to MIN0 CORE FORTH and does not modify or publish MSX0-FORTH.
