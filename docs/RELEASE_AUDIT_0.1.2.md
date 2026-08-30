# MIN0 CORE FORTH 0.1.2 documentation release audit

[Read this page in Japanese](RELEASE_AUDIT_0.1.2_JP.md)

Status: Gate A PASS; publication and post-publication verification pending.

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

Pending.

## Gate C — post-publication evidence

Pending. The public ZIP, checksum, tagged source, language routes, Viewer, and security alerts will be
downloaded or queried again after publication.

This audit applies only to MIN0 CORE FORTH and does not modify or publish MSX0-FORTH.
