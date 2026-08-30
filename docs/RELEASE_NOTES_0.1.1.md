# MIN0 CORE FORTH 0.1.1 release notes

This maintenance release incorporates findings from the first user walkthrough of `0.1.0`.
It does not change the FORTH language semantics, VM instruction set, or security-model behavior.

## Easier first use

- The repository root now contains only the main entry, license, security, version, and packaging files.
- Python／Ruby implementations, examples, and tests are grouped in `workbench/`; design and audit material
  is grouped in `docs/`; release tooling is grouped in `tools/`.
- `docs/QUICKSTART.md` gives an exact Windows ZIP extraction and repository-root check. It explains how
  to recover when PowerShell was opened in `viewer/`, and shows both Python and Ruby requirements and commands.
- README links directly to the live GitHub Pages Guided Viewer. The local self-contained Viewer remains available.
- `docs/PROJECT_ORIGIN.md` explains why the executable specification is implemented independently in Ruby and Python.

## Publication hygiene

- An internal development checkpoint was removed from the current publication tree.
- The release audit now rejects conversation/checkpoint-style Markdown names, including timestamped local records,
  before packaging.
- Existing `v0.1.0` history is preserved; `v0.1.1` is the recommended download for new users.

## Verification

- 358 allowlisted files passed the release audit before the version update; this release adds only its two
  maintenance-release records.
- Python 291 tests, 46 Ruby test files, and 49 Python／Ruby cross-language checks passed.
- Two independent package builds were byte-for-byte identical.
- GitHub secret-scanning alerts and Dependabot alerts were both zero during the pre-publication review.

MIN0 CORE FORTH remains an educational and experimental reference implementation under the MIT License.
The license is not a security certification. See `LICENSE_AND_SECURITY.md` and `KNOWN_LIMITATIONS_0.1.md`.
