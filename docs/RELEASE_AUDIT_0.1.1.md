# MIN0 CORE FORTH 0.1.1 maintenance release audit

Status: Gate A PASS; publication and post-publication verification pending.

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

Pending.

## Gate C — post-publication evidence

Pending. The public ZIP, checksum, tagged source, Viewer, and security alerts will be checked again.

This audit applies only to MIN0 CORE FORTH and does not modify or publish MSX0-FORTH.
