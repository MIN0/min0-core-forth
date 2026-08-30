# MIN0 CORE FORTH 0.1.2 release notes

[Read this page in Japanese](RELEASE_NOTES_0.1.2_JP.md)

This documentation maintenance release formally packages the beginner and advanced learning paths added
after `0.1.1`. It does not change FORTH language semantics, the VM instruction set, dictionary behavior,
image formats, or the security-model experiments.

## Bilingual entry paths

- The repository now has independent English and Japanese README, Quick Start, read-first, safety,
  project-origin, limitation, audit, and documentation-index paths.
- The Guided Viewer has separate English and Japanese pages generated from the same measured trace data.
- Automated checks reject Japanese text in the maintained English entry documents and verify that each
  README routes readers only to its matching language path.

## Learning material

- The new pocket word reference documents all 61 startup words printed by `WORDS`, including stack effects,
  permitted use, current limits, `CREATE ... DOES>`, and dynamic action selection with
  `DEFER ' ['] IS ACTION-OF`.
- README and Quick Start link prominently to the pocket reference.
- The new FORTH design and learning references page gives a purpose-oriented route to FIG-Forth, CF FORTH,
  RETRO FORTH, introductory books, implementation books, and small-MPU material in both languages.
- The reference page credits the Japanese and English source lists in `forth-in-motion` and does not bundle
  third-party books or implementations.

## Preserved boundaries

- `v0.1.0` and `v0.1.1`, their tags, and their release assets remain unchanged.
- MSX0-FORTH remains independent and is not modified by this release.
- The MIT License remains a permission grant, not a security certification.
- All signing seeds and HMAC keys in the repository remain public deterministic test fixtures.

## Verification target

- 298 Python tests
- 46 Ruby test files
- 49 Python/Ruby cross-language check files
- 380 allowlisted release files
- deterministic, byte-identical package builds

The completed pre-publication and post-publication evidence is recorded in
[`RELEASE_AUDIT_0.1.2.md`](RELEASE_AUDIT_0.1.2.md).
