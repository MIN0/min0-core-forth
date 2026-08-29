# MIN0 CORE FORTH 0.1 release checklist

The final release is not complete until every required box is checked. `0.1.0-rc.1` is the current
candidate identity; the final tag is expected to be chosen only after Gate A succeeds.

## Freeze and identity

- [x] Feature work for the 1st release is frozen.
- [x] Canonical name is `MIN0 CORE FORTH`; `MIN0` ends with numeric zero.
- [x] Candidate version is stored in `VERSION`.
- [x] Known limitations and release notes are present.
- [x] MIT License is selected and stored as `LICENSE`; its security boundary is explained separately.
- [ ] Official repository URL and final tag are recorded.

## Gate A — before publication

- [x] Release content is selected by an allowlist; work files are not copied wholesale.
- [x] `document_work/`, DOCX conversation records, `__pycache__/`, and release work directories are excluded.
- [x] Public fixture keys have `TEST` names and explicit deployment warnings.
- [x] `SECURITY.md` defines the private-reporting gate and scope.
- [x] README and `FIRST_READ.md` prominently link `LICENSE_AND_SECURITY.md`.
- [x] `python release_tool.py audit` reports no blockers.
- [x] Clean staging passes all Python, Ruby, cross-language, and Viewer tests.
- [x] Deterministic ZIP and `SHA256SUMS.txt` are generated twice with identical hashes.
- [x] Gate A results are saved in `RELEASE_AUDIT_0.1.md`.

## Gate B — publication

- [ ] Publish only the audited clean staging directory.
- [ ] Enable GitHub secret scanning／push protection where available.
- [ ] Enable private vulnerability reporting or an equivalent private channel.
- [ ] Add final tag, release notes, ZIP, and `SHA256SUMS.txt`.
- [ ] Record repository URL, tag, artifact URL, and publication time.

## Gate C — after publication

- [ ] Clone the public repository into a new clean directory.
- [ ] Repeat tests without referring to the development workspace.
- [ ] Download and rescan the public archive.
- [ ] Match downloaded artifact hashes against the published checksum file.
- [ ] Confirm Viewer remains offline and trace strings remain observed data.
- [ ] Review GitHub security and dependency alerts.
- [ ] Save Gate C results and declare the release complete.

This checklist applies only to MIN0 CORE FORTH. It must not modify or publish MSX0-FORTH.
