# MIN0 CORE FORTH 0.1.0-rc.1 release notes

This is the first release candidate of the CPU-independent MIN0 CORE FORTH educational and experimental
reference system. It is independent of MSX0-FORTH.

## What to try first

1. Open `viewer/value-trace.html` in a browser.
2. Run `python min0_forth.py -z examples/hello.fth`.
3. Run `ruby min0_forth.rb -z examples/hello.fth`.
4. Compare `2 3 4 * + .` and `2 3 * 4 + .` in the Viewer.
5. Observe `CREATE`, `DOES>`, rollback, allocator actions, `DEFER`, and compiled `."` at increasing depth.

## Included

- Independent Python and Ruby implementations of the same 32-bit bytecode model.
- Data, return, and loop stacks with explicit overflow and underflow checks.
- Runtime dictionary, interactive colon compiler, control flow, counted loops, data definitions,
  `CREATE`, constructor plans, and source-level `DOES>`.
- Byte characters, `EMIT`, `CR`, `TYPE`, `S"`, and interpret／compiled `."`.
- Typed relocation across CODE, DICTIONARY, and DATA; bytecode verification; read-only DATA; W^X CODE.
- Safe-runtime versus standard-build separation, `DEFER`, and authenticated Monitor switching experiments.
- Signed-image, anti-rollback, A/B install, recovery, trust rotation, root rotation, and capability models.
- A self-contained offline Guided Viewer generated from measured semantic traces.
- User-facing Python/Ruby REPL and file launchers, including quiet `-z FILE` execution.
- `WORDS`, with a visible boundary between the startup vocabulary and definitions added by the user.

## License and security claims

Source and documentation are available under the MIT License. The license permits use, modification,
Fork, and redistribution subject to retaining its notice; it is not a security certification or a
promise that no vulnerability exists. Start with `LICENSE_AND_SECURITY.md`, which links the exact
license, audit evidence, known limitations, threat model, and private-reporting policy.

## Reproducibility

The release candidate is tested with Python 3.12.13, Ruby 4.0.3, Python `cryptography` 50.0.0, and Ruby
OpenSSL 3.6.2 on Windows. The final Gate A record will state the clean-staging Python test count, Ruby
test-file count, cross-language check count, artifact SHA-256, and secret/privacy scan result.

## Important safety notice

All cryptographic keys in the examples are public deterministic test fixtures. Do not use them for a
real device or release. This release is not a product-security guarantee. Read `FIRST_READ.md`,
`SECURITY.md`, `KNOWN_LIMITATIONS_0.1.md`, and `THREAT_MODEL_R0.md` first.

## Remaining release blockers

- Create the official GitHub repository and record its URL.
- Enable a private vulnerability-reporting path.
- Publish Gate B, then clone and complete Gate C.
