# MIN0 CORE FORTH documentation

[Read this page in Japanese](README_JP.md)

## Entry documents

- [Quick Start](QUICKSTART.md)
- [Project origin](PROJECT_ORIGIN.md)
- [License and security](LICENSE_AND_SECURITY.md)
- [Known limitations](KNOWN_LIMITATIONS_0.1.md)
- [0.1.1 release audit](RELEASE_AUDIT_0.1.1.md)
- [Repository read-first notice](../FIRST_READ.md)
- [English Guided Viewer](https://min0.github.io/min0-core-forth/viewer/value-trace-en.html)

## Design-document groups

The remaining files in this directory are the detailed executable-specification records. Their file
names remain stable so tests, discussions, and future target ports can cite them precisely.

- VM and language: `BYTECODE_V0_1.md`, `SOURCE_V0_1.md`, `DICTIONARY_V0_1.md`,
  `INTERACTIVE_COMPILER_V0_1.md`, `CONTROL_FLOW_V0_1.md`, and loop/data/string documents
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
