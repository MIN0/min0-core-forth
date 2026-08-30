[日本語版を見るにはここをクリックしてください](README_JP.md)

# MIN0 CORE FORTH

> [!IMPORTANT]
> ## Please read this first
>
> `MIN0` is pronounced “Mino”; its final character is the digit zero, not the letter O.
> MIN0 CORE FORTH is an educational and experimental reference implementation for people who are
> meeting FORTH for the first time and for people who want to inspect its deeper mechanisms.
>
> **[Purpose, safety position, and identification of official releases](FIRST_READ.md)**
>
> **[MIT License and security assurance are different promises](docs/LICENSE_AND_SECURITY.md)**

**MIN0 CORE FORTH 0.1 — Educational and Experimental Reference Release**

Current release: `0.1.1`<br>
Official repository: <https://github.com/MIN0/min0-core-forth><br>
Release tag: `v0.1.1`

## Start here

1. Open the **[English Guided Viewer](https://min0.github.io/min0-core-forth/viewer/value-trace-en.html)**.
2. Follow the **[five-minute Quick Start](docs/QUICKSTART.md)** with Python or Ruby.
3. Keep the **[pocket word reference](docs/WORD_REFERENCE.md)** beside the terminal. It explains every
   word printed by `WORDS` and highlights dynamic switching with `DEFER`.
4. Use the **[FORTH design and learning references](docs/REFERENCES.md)** to find books, historical
   implementations, and material for studying small-system design.
5. Read **[why the project began with Ruby and Python](docs/PROJECT_ORIGIN.md)**.
6. Use the **[English documentation index](docs/README.md)** to explore the design and audits.

The Viewer is self-contained. It displays measured traces but does not execute edited source or send
trace data over the network.

## What this project is

MIN0 CORE FORTH began as an experiment in building a common mother system from which CPU-, MPU-,
FPGA-, and other target-specific FORTH systems can grow. It is independent of MSX0-FORTH and does not
modify the released MSX0-FORTH system.

The Python and Ruby implementations are executable specifications, not the final hardware targets.
Expressing the same FORTH behavior independently in two languages exposes ambiguity, assumptions, and
portability mistakes before a physical target and its memory limits are selected.

This project is independent of Forth standards organizations. It does not yet claim complete
conformance with a Forth standard. Here, “CORE” describes the common root of future implementations.

## Repository layout

| Location | Purpose |
| --- | --- |
| `viewer/` | Japanese and English self-contained Guided Viewer pages |
| `workbench/` | Python and Ruby implementations, tests, examples, and shared vectors |
| `docs/` | Language-specific entry documents, specifications, and audit records |
| `tools/` | Release auditing and deterministic packaging tools |

The repository root contains only the main entry documents, license, security policy, version,
dependency pin, and packaging controls.

## Fixed reference profile

- 32-bit cells with two's-complement signed interpretation
- 32-bit byte addresses
- little-endian cell encoding
- 8-bit opcodes and 32-bit immediate operands
- a unified 64 KiB virtual-memory reference profile, not a universal CORE limit
- separate logical data, return, and loop stacks
- absolute branch and call targets in the initial executable model
- Forth true as `0xFFFFFFFF` and false as `0`
- deterministic faults for invalid instructions, stack limits, and invalid memory access

## Included in release 0.1.1

- Independent Python and Ruby implementations of the same bytecode and dictionary behavior
- Data, return, and loop stacks with explicit overflow and underflow checks
- Runtime dictionary and interactive colon definitions
- Conditional control flow and counted loops
- `CONSTANT`, `VARIABLE`, `CREATE`, constructor plans, and source-level `DOES>`
- `WORDS`, including a visible boundary before definitions added by the user
- Character and string output through `EMIT`, `CR`, `TYPE`, `S"`, and `."`
- Split CODE, DICTIONARY, and DATA experiments with typed relocation
- Bytecode verification, read-only data, sealed CODE, and W^X publication models
- `DEFER` and authenticated Monitor switching experiments
- Signed-image, anti-rollback, A/B installation, recovery, trust rotation, and capability models
- A measured, word-by-word Guided Viewer with success, rollback, constructor, and output scenarios
- Interactive and quiet file launchers for both Python and Ruby

These security-related components are executable experiments. They are not a claim that a product or
physical device has been security-certified.

## Run the host implementations

From the extracted repository root:

```powershell
python workbench/min0_forth.py
ruby workbench/min0_forth.rb
```

Quiet file execution:

```powershell
python workbench/min0_forth.py -z workbench/examples/hello.fth
ruby workbench/min0_forth.rb -z workbench/examples/hello.fth
```

Both quiet commands print:

```text
Hello from MIN0 CORE FORTH
```

Try the following in either interactive launcher:

```forth
WORDS
2 3 +
2 3 4 * + .
2 3 * 4 + .
: SQUARE DUP * ;
5 SQUARE .
BYE
```

See the **[Quick Start](docs/QUICKSTART.md)** for Windows folder checks, requirements, Ruby and Python
commands, and troubleshooting. The **[pocket word reference](docs/WORD_REFERENCE.md)** gives the stack
effect, permitted use, and short meaning of every startup word.

## Verification

The `v0.1.1` public artifact and independently downloaded tagged source passed:

- 291 Python tests
- 46 Ruby test files
- 49 Python/Ruby cross-language check files
- a 360-file path-and-content comparison with no differences
- offline Viewer and text-only trace-data checks
- deterministic package reproduction and SHA-256 verification

The completed evidence is recorded in the **[0.1.1 release audit](docs/RELEASE_AUDIT_0.1.1.md)**.

## License and security boundary

Source and documentation are released under the **[MIT License](LICENSE)**. The license permits use,
modification, Forking, and redistribution when its notice is retained. It is not a security
certification, a proof that no vulnerability exists, or a guarantee of fitness for a particular use.

All embedded signing seeds and HMAC keys are deterministic public test fixtures. Never use them for a
real device, release, update, or deployment. Read **[License and security](docs/LICENSE_AND_SECURITY.md)**
and **[Known limitations](docs/KNOWN_LIMITATIONS_0.1.md)** before treating an experiment as an operational
security control.

Security reports should follow **[SECURITY.md](SECURITY.md)**. Do not place unpatched vulnerabilities,
exploit details, private keys, access tokens, or personal data in a public issue.

## Current boundary

No physical MPU, FPGA, Flash, EEPROM, UART, TPM, or hardware memory-protection target is included in
this release. APIs, image formats, and machine identifiers remain experimental 0.1 interfaces. Future
target implementations must re-evaluate memory limits, I/O contracts, persistence, key custody, and
hardware-specific protection.
