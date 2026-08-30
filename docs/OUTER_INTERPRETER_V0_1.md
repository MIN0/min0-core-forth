# MIN0 CORE FORTH outer interpreter v0.1

Status: interpret-state and interactive runtime-compiler executable experiment.

## Token decision

For each whitespace-separated, case-insensitive token after removal of `\`
line comments:

1. Handle reserved interpret-state data and defining words.
2. If it is a decimal or `0x` hexadecimal integer, push one 32-bit cell.
3. Otherwise search the VM-resident dictionary from `LATEST` through `LINK`.
4. If found, execute its XT according to `KIND`.
5. If not found, report `UnknownWord` without guessing or creating a word.

Numbers are handled by the host outer interpreter and therefore consume no VM
instructions in this experiment.

## Minimal terminal output

`.` is an interpret-state host word in v0.1. It removes the top DATA-stack cell,
converts it to a signed decimal number, and appends that text to the outer
interpreter's deterministic output sequence. It is not a VM opcode and therefore
does not make the minimal VM depend on a console device.

An empty stack raises `StackUnderflow` without adding output. The name `.` is
reserved and cannot be redefined. Compiling `.` inside a colon definition is not
yet supported.

`EMIT`, `CR`, and `TYPE` are now implemented with the host-side byte-character boundary defined in
`TERMINAL_OUTPUT_V0_1.md`. `TYPE` validates and reads the complete byte range before changing output or
consuming either stack argument; zero length does not dereference its address. Interpret-state `S"` and
`."` use the quote-aware parser and byte policy in `STRING_LITERALS_V0_1.md`. Interactive definitions
compile `S"` as relocated DATA address plus byte length. Compiled `."` adds generic `SERVICE 1`; the
trusted target registers its terminal adapter before verified execution is sealed.

## XT execution bridge

- Primitive XT: place its opcode followed by `HALT` in a two-byte host
  trampoline immediately below the dictionary and resume the VM there.
- Colon XT: resume at its payload address after pushing the address of a host
  `HALT` trampoline on the return stack. Its final `EXIT` returns to `HALT`.
- Constant XT: push its payload cell.
- Variable XT: push its payload data address.
- Created-word XT: push its payload data-field address.

Data-stack contents persist across tokens and across calls to the outer
interpreter. A normally completed colon word restores the return stack to its
prior depth.

The trampolines are a reference-host mechanism, not part of the persistent
bytecode or target ABI. A later VM may provide a native XT dispatch path.

## Still outside this stage

- compiled `.`, `EMIT`, `CR`, `TYPE`, and output services other than terminal-type v0.1
- a self-hosted parser and dictionary allocator
- `CATCH`/`THROW` and transactional memory recovery
