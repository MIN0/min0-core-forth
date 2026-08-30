# Security policy

## Supported release

Security review currently applies to release `0.1.1`. MIN0 CORE FORTH is an
educational and experimental reference implementation, not a product-security-certified runtime.

The MIT License grants copyright permissions; it does not certify security or guarantee fitness for a
particular use. See `LICENSE_AND_SECURITY.md` for the short route from the license to the audit evidence,
known limitations, threat model, and official-release identification rules.

## Reporting a vulnerability

Do not include an unpatched vulnerability, exploit details, private key, access token, or personal data
in a public issue. Use the official repository's private vulnerability-reporting channel:
<https://github.com/MIN0/min0-core-forth/security/advisories/new>. It was enabled before the first
candidate release, together with secret scanning and push protection.

Ordinary usage questions, documentation errors, and already-public design discussions may use public
issues after the repository is available.

## Public test keys

Every Ed25519 seed and HMAC key included in this repository is a deterministic public test fixture.
They are intentionally known to everyone and must never be used to sign or authenticate a real device,
release, update, or deployment. A fixture signature proves only that the example code path works.

## Scope and limitations

The reference tests cover bytecode structure, typed relocation, signed-image experiments, anti-rollback,
transactional A/B installation, recovery, capability separation, W^X publication, immutable service
registration, stack limits, and failure rollback. They do not establish resistance to side channels,
fault injection, compromised hosts or compilers, physical attacks, denial of service, or bugs in a future
hardware port. See `KNOWN_LIMITATIONS_0.1.md` and `THREAT_MODEL_R0.md`.
