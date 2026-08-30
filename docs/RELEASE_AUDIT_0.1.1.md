# MIN0 CORE FORTH 0.1.1 maintenance release audit

Status: Gate A PASS; Gate B PASS; Gate C PASS; final `v0.1.1` published and independently verified.

## Scope

`0.1.1` preserves the FORTH semantics of `0.1.0`. Its scope is repository organization, beginner-facing
instructions, live Viewer navigation, publication hygiene, and the corresponding release-tool test.
The `v0.1.0` tag and release assets remain unchanged as historical evidence.

## Gate A — pre-publication evidence

- Release allowlist audit: PASS, 360 selected files and no issues.
- Python suite: 291 tests passed.
- Ruby suite: 46 test files passed.
- Python／Ruby cross-language suite: 49 check files passed.
- Reproducible ZIP: two independent `0.1.1` builds matched byte-for-byte. The exact public artifact
  digest is stored beside the ZIP in `SHA256SUMS.txt` so the release record does not become self-referential.
- GitHub secret-scanning alerts: 0.
- GitHub Dependabot alerts: 0.
- GitHub Pages: built with HTTPS enforced.

## Gate B — publication evidence

- Final release: <https://github.com/MIN0/min0-core-forth/releases/tag/v0.1.1>.
- Published: 2026-08-30 19:32:47 (Asia/Tokyo).
- Tagged commit: `d7647492bc4071d4543e9547f84b485d79462706`.
- Artifact: `min0-core-forth-0.1.1.zip`, 583705 bytes.
- Artifact SHA-256: `7ccfcbafe09d88d92759eae7cdaa031b03e3b0816f7882016316707f802b43eb`.
- `v0.1.1` is a normal release, not a draft or pre-release.

## Gate C — post-publication evidence

- The ZIP and `SHA256SUMS.txt` were downloaded from the public release into a new directory; their
  SHA-256 values matched exactly.
- The release contained 360 audited source files plus `RELEASE_MANIFEST.txt`. All 360 paths and hashes
  matched the independently downloaded `v0.1.1` tagged source, with zero missing, extra, or different files.
- The downloaded release ZIP and tagged source each passed the release audit, Python 291 tests,
  46 Ruby test files, and 49 Python／Ruby cross-language checks.
- GitHub Pages reported `built` with HTTPS enforced. The public Guided Viewer SHA-256 matched the
  tagged local Viewer exactly: `8994161f5d83f39b194d658698ba211283ceab839a6d9d539a5e5ca56d89f853`.
- GitHub secret-scanning alerts: 0. Dependabot alerts: 0.
- Windows system HTTPS clients again failed in their local credential／TLS layer; Python's independent
  OpenSSL path downloaded the same public tagged archive successfully. This was a host transport issue,
  not a release-content failure.

This audit applies only to MIN0 CORE FORTH and does not modify or publish MSX0-FORTH.
