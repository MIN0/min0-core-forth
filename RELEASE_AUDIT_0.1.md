# MIN0 CORE FORTH 0.1 release audit

Status: Gate A PASS; Gate B publication has not started.

Audit date: 2026-08-30 (Asia/Tokyo)  
Candidate: `0.1.0-rc.1`  
Scope: MIN0 CORE FORTH only; MSX0-FORTH was not modified.

## Current result

| Gate | Result | Meaning |
| --- | --- | --- |
| Gate A, source-tree preparation | PASS | allowlist, MIT License, notices, fixture warnings, launchers, and tests are present |
| Gate A, clean-staging validation | PASS | all suites passed from the allowlisted staging tree; deterministic packaging was reproduced |
| Gate B, GitHub publication | NOT STARTED | official repository URL and private reporting channel are not yet available |
| Gate C, public clone／artifact audit | NOT STARTED | runs only after Gate B |

Gate A authorizes the local `0.1.0-rc.1` candidate for Gate B preparation. It is not a completed public
release until the official repository, private vulnerability-reporting path, tag, uploaded checksum,
and post-publication Gate C audit exist.

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
SHA-256 values. The authoritative local value is written beside the candidate in `SHA256SUMS.txt`;
Gate B must publish that file unchanged with the archive.

## Remaining actions

1. Create and record the official repository URL.
2. Enable private vulnerability reporting before public release.
3. Publish only the audited archive, checksum, release notes, and final tag.
4. Clone and download from the public location, then complete every Gate C check.
