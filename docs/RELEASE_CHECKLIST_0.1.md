# MIN0 CORE FORTH 0.1 release checklist

The public `0.1.0-rc.1` candidate completed Gate A, Gate B, and Gate C. Those results authorize the
final `0.1.0` release; the final publication record is completed after its assets are uploaded.

## Freeze and identity

- [x] Feature work for the 1st release is frozen.
- [x] Canonical name is `MIN0 CORE FORTH`; `MIN0` ends with numeric zero.
- [x] Final version `0.1.0` is stored in `VERSION`.
- [x] Known limitations and release notes are present.
- [x] MIT License is selected and stored as `LICENSE`; its security boundary is explained separately.
- [x] Official repository URL, candidate tag `v0.1.0-rc.1`, and final tag `v0.1.0` are defined.

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

- [x] Publish only the audited clean staging directory.
- [x] Enable GitHub secret scanning／push protection where available.
- [x] Enable private vulnerability reporting or an equivalent private channel.
- [x] Add candidate tag, release notes, ZIP, and `SHA256SUMS.txt`.
- [x] Record candidate repository URL, tag, artifact URL, and publication time.

## Gate C — after publication

- [x] Obtain GitHub's tagged source archive in a new clean directory and compare all release paths and hashes.
- [x] Repeat tests without referring to the development workspace.
- [x] Download and rescan the public archive.
- [x] Match downloaded artifact hashes against the published checksum file.
- [x] Confirm Viewer remains offline and trace strings remain observed data.
- [x] Review GitHub security and dependency alerts.
- [x] Save Gate C results and authorize final `v0.1.0`.

## Final `v0.1.0` publication

- [x] Update release identity and final release notes only after Gate C passes.
- [x] Publish final tag, ZIP, `SHA256SUMS.txt`, and release notes.
- [x] Record the final public URL and publication time on the default branch.

This checklist applies only to MIN0 CORE FORTH. It must not modify or publish MSX0-FORTH.
