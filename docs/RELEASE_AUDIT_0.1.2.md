# MIN0 CORE FORTH 0.1.2 documentation release audit

[Read this page in Japanese](RELEASE_AUDIT_0.1.2_JP.md)

Status: Gate A PASS; Gate B PASS; Gate C PASS; final `v0.1.2` published and independently verified.

## Scope

`0.1.2` preserves the FORTH semantics and executable security experiments of `0.1.1`. Its scope is the
bilingual navigation layer, English Guided Viewer, pocket word reference, learning references, and the
tests and release rules that keep those documents complete and separated by language. The `v0.1.0` and
`v0.1.1` tags and release assets remain unchanged.

## Gate A — pre-publication evidence

- Release allowlist audit: PASS, 380 selected files and no issues.
- Python suite: 298 tests passed.
- Ruby suite: 46 test files passed.
- Python/Ruby cross-language suite: 49 check files passed.
- Local Markdown links: 0 broken links.
- Language-route checks: English entry documents contained no Japanese text after README's required first
  line; English and Japanese README routes, reference-page pairs, and all 61 pocket-reference words matched.
- Reproducible ZIP: two independent `0.1.2` builds matched byte-for-byte. The final public artifact digest
  is stored beside the ZIP in `SHA256SUMS.txt` so this audit does not become self-referential.
- GitHub secret-scanning alerts: 0 open alerts.
- GitHub Dependabot alerts: 0 open alerts.
- GitHub Pages: `built`, with HTTPS enforced from the `main` branch.
- No `v0.1.2` tag or release existed before publication; `v0.1.1` remained the unchanged latest release.

## Gate B — publication evidence

- Final release: <https://github.com/MIN0/min0-core-forth/releases/tag/v0.1.2>.
- Published: 2026-08-30 22:36:50 (Asia/Tokyo).
- Tagged commit: `e34d203837ddc6bbd3ac1262d0b0c72d69c68af1`.
- Artifact: `min0-core-forth-0.1.2.zip`, 630759 bytes.
- Artifact SHA-256: `1fa73ed9278acda7dfa491fcf090e0f14175e13144727ad8c896e0ecd466f522`.
- `SHA256SUMS.txt`: 92 bytes; its listed ZIP digest matched the release asset digest.
- `v0.1.2` is a normal release, not a draft or pre-release, and became the latest release.

## Gate C — post-publication evidence

- The public ZIP and `SHA256SUMS.txt` were downloaded into a new directory. The downloaded ZIP's size and
  SHA-256 matched the locally verified artifact, checksum file, and GitHub asset metadata.
- The ZIP contained 380 audited source files plus `RELEASE_MANIFEST.txt`. Every manifest SHA-256 matched.
  There were zero missing or extra selected files.
- The remote `v0.1.2` tag contained exactly 380 blobs. Every path and Git blob identity matched the
  corresponding file extracted from the public ZIP, with zero missing, extra, or different files.
- The extracted public ZIP passed the release audit with 380 files and no issues, 298 Python tests,
  46 Ruby test files, and 49 Python/Ruby cross-language checks.
- GitHub Pages built commit `e34d203837ddc6bbd3ac1262d0b0c72d69c68af1` with HTTPS enforced. The public
  Japanese and English Guided Viewer SHA-256 values matched the tagged files exactly:
  `8994161f5d83f39b194d658698ba211283ceab839a6d9d539a5e5ca56d89f853` and
  `ed5f6a61b16b3f2bc86f11cc378f8547fb9c9dd8938fa61de6e56d54571b27c8`.
- GitHub secret-scanning alerts: 0 open alerts. Dependabot alerts: 0 open alerts.
- Remote `main` and `v0.1.2` both identified the tagged release commit before this final audit record was
  added to `main`; the tag and release assets remain immutable historical evidence.

This audit applies only to MIN0 CORE FORTH and does not modify or publish MSX0-FORTH.
