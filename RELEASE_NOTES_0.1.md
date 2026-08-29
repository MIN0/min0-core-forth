# MIN0 CORE FORTH 0.1.0 release notes

This is the first release of the CPU-independent MIN0 CORE FORTH educational and experimental
reference system. It is independent of MSX0-FORTH.

## What to try first

1. Read `FIRST_READ.md` and `LICENSE_AND_SECURITY.md`.
2. Open `viewer/value-trace.html` in a browser.
3. Run `python min0_forth.py -z examples/hello.fth` or `ruby min0_forth.rb -z examples/hello.fth`.
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
- User-facing Python/Ruby REPL and quiet `-z FILE` launchers.
- `WORDS`, with a visible boundary between startup vocabulary and user definitions.

## Verification

The public `v0.1.0-rc.1` candidate was downloaded into a clean directory before this final release was
authorized. Its 356-file manifest matched GitHub's tagged source archive with zero differences. Python
290 tests, 46 Ruby test files, and 49 Python／Ruby cross-language checks passed independently from both
the downloaded release ZIP and the GitHub source archive. Viewer-specific tests confirmed offline-only
operation and text-only handling of observed trace strings. GitHub secret-scanning and Dependabot alerts
were both zero at the Gate C review.

## License and security claims

Source and documentation are available under the MIT License. The license permits use, modification,
Fork, and redistribution subject to retaining its notice; it is not a security certification or a
promise that no vulnerability exists. Start with `LICENSE_AND_SECURITY.md`, which links the exact
license, audit evidence, known limitations, threat model, and private-reporting policy.

All cryptographic keys in the examples are public deterministic test fixtures. Never use them for a
real device or release. This educational and experimental release is not a product-security guarantee.
