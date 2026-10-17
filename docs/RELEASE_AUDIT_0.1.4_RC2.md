# MIN0 CORE FORTH 0.1.4-rc.2 candidate audit

[Read this page in Japanese](RELEASE_AUDIT_0.1.4_RC2_JP.md)

Candidate: `0.1.4-rc.2`

Status: Gate A passed. No tag or release has been published.

## Completed pre-Gate evidence

- Phase C Mobile input-control PC visual evaluation: PASS.
- Phase C iPhone Safari evaluation on GitHub Pages: PASS.
- Focused Mobile Python tests: 10 passed.
- Focused Mobile JavaScript test groups: passed.
- Generated Mobile HTML build identity refreshed after iPhone verification.
- `git diff --check`: PASS for the preparation changes.

## Gate A -- passed

- Date: 2026-10-17 (Asia/Tokyo).
- User's normal Windows PowerShell: `python tools\run_all_checks.py`.
- Python suite: passed.
- Ruby: all 50 test files passed.
- Python/Ruby cross-language checks: all 51 check files passed.
- Final result: `ALL CHECKS PASSED`.
- Release allowlist audit: 492 files, zero issues.
- Documentation/release-tool focused tests: 14/14 passed.
- Build the candidate into two independent directories and require byte-identical ZIP files.
- Store the final ZIP byte size and SHA-256 beside the artifact in `SHA256SUMS.txt` and in the
  publication record, avoiding a self-referential digest inside the ZIP.

The restricted Codex sandbox denies the `ruby.exe` child process with exit code `3221225506`. The
five Python-suite failures seen there are all Ruby-launcher comparison tests. The user's normal
PowerShell environment does not reproduce that restriction and passed the complete test run.

## Gate B -- not authorized yet

Do not create `v0.1.4-rc.2` or publish assets until the user explicitly confirms
publication. Existing tags and assets remain immutable.

## Gate C -- pending

After publication, retrieve the public ZIP and checksum into a new directory, verify their hashes and
manifest, run the applicable checks from the extracted artifact, and confirm the public Pages build.
