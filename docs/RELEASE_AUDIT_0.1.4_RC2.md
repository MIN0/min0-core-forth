# MIN0 CORE FORTH 0.1.4-rc.2 candidate audit

[Read this page in Japanese](RELEASE_AUDIT_0.1.4_RC2_JP.md)

Candidate: `0.1.4-rc.2`

Status: preparation in progress. No tag or release has been published.

## Completed pre-Gate evidence

- Phase C Mobile input-control PC visual evaluation: PASS.
- Phase C iPhone Safari evaluation on GitHub Pages: PASS.
- Focused Mobile Python tests: 10 passed.
- Focused Mobile JavaScript test groups: passed.
- Generated Mobile HTML build identity refreshed after iPhone verification.
- `git diff --check`: PASS for the preparation changes.

## Gate A -- pending

- Run `python tools/run_all_checks.py` in the user's normal Windows PowerShell environment.
- Require all Python suites, Ruby files, and cross-language checks to pass.
- Run the release allowlist audit and require zero issues.
- Build the candidate twice and require byte-identical ZIP files.
- Record the final commit, file count, byte size, and SHA-256 without placeholders.

## Gate B -- not authorized yet

Do not create `v0.1.4-rc.2` or publish assets until Gate A is complete and the user explicitly confirms
publication. Existing tags and assets remain immutable.

## Gate C -- pending

After publication, retrieve the public ZIP and checksum into a new directory, verify their hashes and
manifest, run the applicable checks from the extracted artifact, and confirm the public Pages build.
