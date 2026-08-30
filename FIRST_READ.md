# Please read this first

[Read this page in Japanese](FIRST_READ_JP.md)

## Name

The official project name is **MIN0 CORE FORTH**. `MIN0` ends with the digit zero and is pronounced
“Mino Core Forth.” The name comes from the developer's long-used nickname and from the idea of growing
a new common FORTH system from zero.

## Central design principle

> Preserve Forth's freedom while making people clearly aware when they use dangerous power.<br>
> Separate the safe path for ordinary use from the path deliberately opened by an informed developer.

MIN0 CORE FORTH does not try to remove Forth's expressive power. Ordinary use follows a path where a
mistake is less likely to become an immediate accident. Strong operations, such as modifying executable
memory or dynamically changing a call target, require explicit names, authority, validation, and audit.

## Purpose of this release

The Python and Ruby implementations are educational, research, and personal-experiment reference
systems. They allow people to:

- run FORTH and observe its stacks and dictionary;
- compare two independent executable specifications;
- inspect `CREATE`, constructor plans, and `DOES>` in the Guided Viewer;
- define and modify their own words;
- Fork the project for a CPU, MPU, FPGA, or another target; and
- share demonstrations, screenshots, and videos.

MIN0 CORE FORTH is independent of MSX0-FORTH. This release process does not modify or publish
MSX0-FORTH.

## Current position

**MIN0 CORE FORTH 0.1 is an official educational and experimental reference release. It is not a
product-security-certified runtime.**

- Python and Ruby are host executable specifications.
- A/B update, signature, recovery, and capability components are working models for future targets.
- Every included private signing seed or HMAC key is a public test fixture.
- A fixture signature does not prove the authenticity of a real product or release.
- Real Flash, EEPROM, CPUs, protection modes, TPMs, and physical attacks have not been validated.
- APIs, stored formats, and the word set may change in later experimental releases.
- The Viewer is offline and does not send trace data to a network or an AI service.

## License and security

The project uses the MIT License. It broadly permits use, modification, Forking, and redistribution,
but it is not a security certification or a guarantee that no defect exists.

Start with **[License and security](docs/LICENSE_AND_SECURITY.md)** for links to the exact license,
completed release audits, known limitations, threat model, and private vulnerability reporting method.

## Relationship to Forth standards

This is an independent project, not an official implementation from a Forth standards organization.
“CORE” means a common mother system for future target-specific implementations. Complete conformance
with a Forth standard is not claimed at this stage.

## Official releases and Forks

Forks and modified builds are welcome. Modified distributions should use a distinct build name or
version suffix and should not present the original release audit as proof for changed code.

The official repository is <https://github.com/MIN0/min0-core-forth>. The first release is `v0.1.0`;
the recommended maintenance release is `v0.1.1`. Releases provide a tag, ZIP, SHA-256 list, notes,
known limitations, and audit records.

## Recommended order

1. Open the [English Guided Viewer](https://min0.github.io/min0-core-forth/viewer/value-trace-en.html).
2. Follow the [English Quick Start](docs/QUICKSTART.md).
3. Read the [English documentation index](docs/README.md).
4. Explore security demonstrations only if their explicit limitations are acceptable for your experiment.
