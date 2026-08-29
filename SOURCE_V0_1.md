# MIN0 CORE FORTH minimal source language v0.1

Status: executable compiler experiment. This syntax is deliberately smaller
than an ANS Forth system and does not yet define an interactive environment.

## Lexical rules

- Source is split on whitespace.
- Word matching is case-insensitive and canonicalized to uppercase.
- `\` starts a comment that continues to the end of the physical line.
- Integers may be decimal or use a `0x` hexadecimal prefix.

## Definitions

```forth
: SQUARE DUP * ;
```

`:` begins a colon definition, the next token is its name, and `;` ends it.
Nested definitions and primitive redefinition are errors in v0.1. Forward
references between user definitions are accepted because the whole source is
parsed before bytecode generation.

Tokens outside definitions form the main sequence, which is the raw image
entry point at address zero. The compiler appends `HALT` to main and `EXIT` to
every colon body.

## Initial dictionary

| Source word | Bytecode |
|---|---|
| `NOP` | `NOP` |
| `@` | `FETCH` |
| `!` | `STORE` |
| `DROP DUP SWAP OVER` | corresponding stack opcode |
| `+ - *` | `ADD SUB MUL` |
| `AND OR XOR` | corresponding logic opcode |
| `< =` | `LESS EQUAL` |

An integer compiles to `LIT` followed by one 32-bit cell. A user-defined word
compiles to `CALL` with its absolute bytecode address.

This dictionary exists only in each host compiler. Runtime dictionary headers,
name lookup inside the VM, `STATE`, `HERE`, immediate words, and interactive
interpretation remain future work.
