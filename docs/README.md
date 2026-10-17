# MIN0 CORE FORTH documentation

[Read this page in Japanese](README_JP.md)

## Entry documents

- [Pocket word reference — all 78 next-candidate words](WORD_REFERENCE.md)
- [localhost Live Viewer setup and safety boundary (Japanese)](LIVE_VIEWER_JP.md)
- [iPhone offline reading pack (Japanese)](IPHONE_READING_PACK_JP.md)
- [Mobile Learning guide (Japanese)](MOBILE_FORTH_JP.md)
- [Mobile Learning and virtual-assembler observation/Monitor plan (Japanese)](MOBILE_VIEWER_MONITOR_PLAN_JP.md)
- [Run Mobile Learning on GitHub Pages](https://min0.github.io/min0-core-forth/viewer/mobile-forth.html)
- [Run the virtual assembler Viewer on GitHub Pages](https://min0.github.io/min0-core-forth/viewer/virtual-assembler.html)
- [Understanding FORTH interpretation, compilation, and execution](FORTH_EXECUTION_PHASES.md)
- [CORE word compilation-compatibility plan](CORE_WORD_COMPILATION_PLAN.md)
- [Semantics audit for all 65 startup words](CORE_WORD_SEMANTICS_MATRIX.md)
- [Direct control-structure design](DIRECT_CONTROL_V0_3.md)
- [FOR/NEXT direct-loop design](FOR_NEXT_DIRECT_V0_2.md)
- [FORTH design and learning references](REFERENCES.md)
- [Quick Start](QUICKSTART.md)
- [Project origin](PROJECT_ORIGIN.md)
- [License and security](LICENSE_AND_SECURITY.md)
- [Known limitations](KNOWN_LIMITATIONS_0.1.md)
- [0.1.4-rc.2 Mobile Monitor candidate notes](RELEASE_NOTES_0.1.4_RC2.md)
- [0.1.4-rc.2 candidate audit](RELEASE_AUDIT_0.1.4_RC2.md)
- [0.1.4-rc.3 safe variables and BREAK candidate notes](RELEASE_NOTES_0.1.4_RC3.md)
- [0.1.4-rc.3 candidate audit](RELEASE_AUDIT_0.1.4_RC3.md)
- [0.1.4-rc.4 Ruby-baseline candidate notes](RELEASE_NOTES_0.1.4_RC4.md)
- [0.1.4-rc.4 candidate audit](RELEASE_AUDIT_0.1.4_RC4.md)
- [0.1.4 local-candidate notes](RELEASE_NOTES_0.1.4.md)
- [0.1.4 local-candidate audit](RELEASE_AUDIT_0.1.4.md)
- [0.1.3 compatibility release notes](RELEASE_NOTES_0.1.3.md)
- [0.1.3 release audit](RELEASE_AUDIT_0.1.3.md)
- [0.1.2 release notes](RELEASE_NOTES_0.1.2.md)
- [0.1.2 release audit](RELEASE_AUDIT_0.1.2.md)
- [0.1.1 release audit](RELEASE_AUDIT_0.1.1.md)
- [Repository read-first notice](../FIRST_READ.md)
- [English Guided Viewer](https://min0.github.io/min0-core-forth/viewer/value-trace-en.html)

## Design-document groups

The remaining files in this directory are the detailed executable-specification records. Their file
names remain stable so tests, discussions, and future target ports can cite them precisely.

- VM and language: `BYTECODE_V0_1.md`, `SOURCE_V0_1.md`, `DICTIONARY_V0_1.md`,
  `INTERACTIVE_COMPILER_V0_1.md`, `CONTROL_FLOW_V0_1.md`, `DIRECT_CONTROL_V0_3.md`, and loop/data/string documents
- Defining words: `DOES_DESCRIPTOR_V0_1.md`, `SOURCE_DOES_V0_1.md`, and constructor-plan documents
- Memory and relocation: memory-profile, split-dictionary, relocation, linker, and envelope documents
- Runtime boundaries: output service, execution profile, verifier, sealed execution, W^X, and capability documents
- Update and trust: signed image, anti-rollback, transactional installation, recovery, trust/root rotation,
  persistent package, and loader state documents
- Observation and control: trace, Viewer, Monitor, and `DEFER` documents
- Publication: release notes, checklists, audit plan, audits, threat model, and limitations

Many detailed records preserve the language used while the experiment was developed. The entry documents
above are the maintained English navigation layer; code, identifiers, stack effects, and file names are
language-neutral technical material.
