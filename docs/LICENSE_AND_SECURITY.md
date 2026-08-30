# License and security: read this first

[Read this page in Japanese](LICENSE_AND_SECURITY_JP.md)

> **The MIT License defines copyright permissions.**<br>
> **It is not a security certification, proof of no vulnerabilities, or fitness guarantee.**

MIN0 CORE FORTH keeps these two questions separate. Instead of claiming that everything is safe, the
project publishes what was checked, what remains unverified, and how to report a problem privately.

## What the MIT License permits

The source and accompanying documentation are released under the [MIT License](../LICENSE). When the
copyright and permission notice is retained, the license broadly permits use, copying, modification,
merging, publication, distribution, sublicensing, and sale. Its SPDX identifier is `MIT`.

This permission fits the project's purpose of allowing people to grow CPU-, MPU-, FPGA-, and other
target-specific child FORTH systems.

## What the license does not guarantee

The software is provided as-is. Selecting the MIT License does not mean:

- certification by a security-audit organization;
- proof that no vulnerability, design defect, or implementation defect exists;
- fitness for medical, transportation, industrial-control, financial, or safety-critical use;
- proof that a future hardware port preserves the current experimental controls; or
- authenticity of a product signed with the repository's public test-fixture keys.

## Evidence and limits

| Question | Evidence |
| --- | --- |
| What is checked before and after publication? | [Release security audit plan](RELEASE_SECURITY_AUDIT_PLAN.md) |
| What passed for 0.1.1? | [0.1.1 release audit](RELEASE_AUDIT_0.1.1.md) |
| What passed for the original 0.1.0 release? | [0.1.0 release audit](RELEASE_AUDIT_0.1.md) |
| What remains unsupported? | [Known limitations](KNOWN_LIMITATIONS_0.1.md) |
| Which attacks are in or out of scope? | [Threat model](THREAT_MODEL_R0.md) |
| How should a vulnerability be reported? | [Security policy](../SECURITY.md) |
| How is an official release identified? | [Read first](../FIRST_READ.md) |

Audit records include Python and Ruby test counts, cross-language agreement, the release allowlist,
checks for private material and personal paths, Viewer network checks, and deterministic ZIP hashes.
They are evidence for the tested scope, not proof that unknown problems do not exist.

## Reporting a problem

Do not place an unpatched vulnerability, exploit procedure, private key, access token, or personal data
in a public issue. Use the official repository's
[private vulnerability-reporting channel](https://github.com/MIN0/min0-core-forth/security/advisories/new).
Ordinary questions, documentation mistakes, and already-public design discussions may use public issues.

Reports are welcome. Discovering a problem in an experiment is valuable evidence that improves both
the implementation and its documentation.

## Forking and redistribution

- Retain the copyright and permission notices from `LICENSE`.
- Clearly identify modified builds and give them a distinct build name or version suffix.
- Do not claim that the original audit automatically covers modified code.
- Check the rights and notice requirements of any third-party material you add.
- Never place deployment keys in the repository, release ZIP, or test fixtures.

This page is a navigation aid, not legal advice for an individual case.
