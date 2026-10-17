# MIN0 CORE FORTH 0.1.4-rc.4 evaluation notes

[日本語版はこちらです](RELEASE_NOTES_0.1.4_RC4_JP.md)

Candidate: `0.1.4-rc.4` (local and unpublished)

This candidate preserves the safe one-cell variables and explicit Monitor break point prepared for
`0.1.4-rc.3`. It corrects the user-facing Windows Ruby baseline before publication and adds a device-
availability guide and the next Capability Tour direction.

## Safe VARIABLE and BREAK

- `VARIABLE` registers one zero-initialized cell in a dedicated logical region.
- Checked `@` and `!` accept only registered logical addresses.
- A confirmed Pause supports inspection and checked 32-bit editing with Abort rollback.
- `BREAK ( -- )` pauses at a confirmed instruction boundary and supports Continue, Step, Stop, and Abort.

## Windows Ruby baseline

- The release baseline is Ruby 3.4.x with OpenSSL 3.x.
- The Windows Gate A environment uses Ruby 3.4.11 x64-mingw-ucrt.
- Ruby 4.0 with JSON 3.0 is not claimed as the release baseline because the persistent-metadata parser
  still needs a compatibility update for one `JSON.parse` option.
- The Ruby launcher requires no `bundle install` or additional Gem installation for this candidate.

## First-use guidance

- The Japanese read-first guide distinguishes public availability from hardware actually evaluated.
- Windows PC and iPhone Safari are confirmed; Mac, Linux, Raspberry Pi 5 browsers, Android, and tablets
  remain browser-compatible but unevaluated.
- Pico 2 W cannot run Mobile Learning directly because it has no browser environment.
- The next priority is a single Capability Tour for safe variables, `CREATE DOES>`, and the virtual assembler.

## Explicit exclusions

- Arbitrary memory addresses, arrays and structures, persistent variables, and general I/O are not provided.
- Generated RP2350 machine code is not executed on Pico 2 W.
- This is an evaluation candidate, not the final `0.1.4` release.

Existing published tags and assets remain immutable. The unpublished `v0.1.4-rc.3` tag is not moved.
