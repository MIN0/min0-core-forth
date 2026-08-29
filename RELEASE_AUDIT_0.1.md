# MIN0 CORE FORTH 0.1 release audit

Status: Gate A PASS; Gate B PASS; Gate C PASS; final `v0.1.0` published and independently verified.

Audit date: 2026-08-30 (Asia/Tokyo)  
Audited candidate: `0.1.0-rc.1`
Final release: `0.1.0`
Scope: MIN0 CORE FORTH only; MSX0-FORTH was not modified.

## Current result

| Gate | Result | Meaning |
| --- | --- | --- |
| Gate A, source-tree preparation | PASS | allowlist, MIT License, notices, fixture warnings, launchers, and tests are present |
| Gate A, clean-staging validation | PASS | all suites passed from the allowlisted staging tree; deterministic packaging was reproduced |
| Gate B, repository preparation | PASS | public repository, private reporting, secret scanning, push protection, and Dependabot updates are enabled |
| Gate B, candidate assets | PASS | audited ZIP, checksum, notes, and `v0.1.0-rc.1` were published as a pre-release |
| Gate C, public source／artifact audit | PASS | downloaded artifact and GitHub source passed independent hashes, audits, tests, Viewer checks, and alert review |

The public `0.1.0-rc.1` candidate completed all three gates. That result authorizes the same source,
with release identity and records updated to `0.1.0`, for final publication. MIT permission remains
separate from security assurance; the final release is still educational and experimental.

## Test evidence from the development tree

- Python: 290 tests, all passed.
- Ruby: 46 test files, all passed.
- Python／Ruby cross-language checks: 49 files, all passed.

The outer-interpreter cross-check includes the exact UTF-8 `WORDS` listing and
its startup/user-definition separator in both implementations.
- Viewer tests are included in the Python total.
- User launchers agree: both `-z examples/hello.fth` paths emit exactly
  `Hello from MIN0 CORE FORTH` plus LF and no banner or final stack.

Tested host versions:

```text
Python 3.12.13
cryptography 50.0.0
Ruby 4.0.3
OpenSSL 3.6.2
```

The same counts passed from the real 356-file clean staging tree containing the approved MIT text.

## License and claim boundary

- `LICENSE` matches the approved MIT text and copyright line by exact SHA-256.
- `README.md` and `FIRST_READ.md` prominently route readers to `LICENSE_AND_SECURITY.md`.
- That guide separates copyright permission from security assurance and links the audit, limitations,
  threat model, official-build identification, and private-reporting policy.
- The release audit rejects a missing, placeholder, or altered license before packaging.
- MIT permission is not presented as security certification or fitness-for-purpose assurance.

## Non-publishable packaging rehearsal

The complete Gate A mechanics were rehearsed in separate work directories with a conspicuous
`RELEASE REHEARSAL ONLY` placeholder standing in for the unresolved license. This placeholder is not
a license and neither rehearsal archive is a release artifact.

- 354 allowlisted files (the 353 current files plus the temporary placeholder) passed the audit.
- Two independent builds produced identical manifests and ZIP SHA-256 values.
- Each `SHA256SUMS.txt` matched its archive.
- From clean staging: Python 289 tests, Ruby 46 test files, and 49 cross-language checks passed.

This established the packaging procedure before license selection. It was subsequently superseded by
the successful real-license clean-staging run recorded above.

## Allowlist and privacy evidence

The final Gate A audit selected 356 release files. It explicitly excluded:

```text
__pycache__/
document_work/
新FORTHシステム仕様を検討_会話記録.docx
```

The selected tree contains no detected personal Windows user path, `file:///.../Users/...` URI, Codex
internal reference, PEM private key, or common GitHub／OpenAI／AWS token form. The excluded DOCX and
`document_work/` contain conversation and local-workspace material and are not release inputs.

`.gitattributes` fixes release text to LF and marks binary vectors／archives as binary so a GitHub clone,
including a Windows clone, does not silently change the approved license bytes or reproducible inputs.

## Cryptographic fixture audit

- Every embedded seed or HMAC key is deterministic and public.
- Declarations use `TEST` names.
- Each declaring source file states that the keys must never be used in deployment.
- `FIRST_READ.md`, `SECURITY.md`, release notes, and known limitations repeat that fixture signatures
  provide no product or release security.
- No real release signing key has been created, requested, or stored in this workspace.

## Viewer audit

- `viewer/value-trace.html` is generated from measured traces.
- The selected Viewer files contain no HTTP／HTTPS URL, `fetch`, `XMLHttpRequest`, or `WebSocket` pattern.
- Trace-derived strings are inserted as text, not interpreted as commands or HTML.
- The editor copies or saves source but does not execute it inside the Viewer.

## Reproducible packaging audit

The release tool builds with sorted paths, fixed ZIP timestamps, fixed permissions, and identical
compression settings. Two independent real-candidate builds produced identical manifests and archive
SHA-256 values. Gate B published the candidate ZIP unchanged with its checksum file.

## Gate B publication evidence

- Candidate release: <https://github.com/MIN0/min0-core-forth/releases/tag/v0.1.0-rc.1>
- Published: 2026-08-30 08:26:35 (Asia/Tokyo).
- Target commit: `7fddb74c703cb2bf1a217a5d08ed3c93212a4e80`.
- Candidate ZIP SHA-256: `1b9bc5ddc5cc2626fff12d163a897d1d376f68ff40cf50754e1ae651b851b3d9`.
- GitHub reported the same SHA-256 digest for the uploaded ZIP.

## Gate C post-publication evidence

- The candidate ZIP and `SHA256SUMS.txt` were downloaded from the public release into a new directory.
- The downloaded ZIP matched the published checksum exactly.
- Its release audit selected 356 files and reported no issues.
- Python 290 tests, 46 Ruby test files, and 49 cross-language check files all passed from the downloaded ZIP.
- GitHub's tag-generated source archive was downloaded independently. All 356 manifest paths and hashes
  matched the release ZIP, with zero missing or different files.
- The same 290／46／49 suites passed again from the GitHub source archive.
- All 15 Viewer tests passed, including offline-only operation and text-node treatment of trace data.
- GitHub secret scanning and push protection were enabled. Dependabot security updates were enabled.
- Secret-scanning alerts: 0. Dependabot alerts: 0 at the review time.
- A normal `git clone` was not used because this Windows host's `git-remote-https.exe` crashed before
  transport. The GitHub-generated tagged source archive and Git database API were used instead; the
  archive-to-release 356-file hash comparison provides the content-equivalence check.

## Final publication evidence

- Final release: <https://github.com/MIN0/min0-core-forth/releases/tag/v0.1.0>
- Published: 2026-08-30 08:37:12 (Asia/Tokyo).
- Target commit: `abf47f7e0bbe5361784696efe7645cab75861b42`.
- Final ZIP SHA-256: `de98af5c074729d6b3e93758c6c2bbe5c5d0fa2279356e5a8ac04dfadced474d`.
- Two independent local builds produced that same ZIP digest and the same 357-file manifest.
- The final ZIP and checksum were downloaded again from GitHub; their SHA-256 values matched exactly.
- All 357 release-manifest paths matched GitHub's final tagged source archive, with zero differences.
- The downloaded final ZIP passed its audit, Python 290 tests, 46 Ruby test files, and 49 cross-language checks.
- `v0.1.0` is a normal release, not a pre-release. The earlier `v0.1.0-rc.1` remains as audit history.
- MSX0-FORTH was neither modified nor published by this release process.

Official repository: <https://github.com/MIN0/min0-core-forth>
