# MIN0 CORE FORTH

> [!IMPORTANT]
> ## まずは必ず最初にお読みください！ / PLEASE READ FIRST
>
> `MIN0`は「ミノ」と読み、最後の文字は英字の`O`ではなく数字の`0`です。
> 本プロジェクトは、FORTHを初めて体験する方にも開かれた教育・実験用の
> 公式リファレンス実装を目指しています。
>
> **▶ [公開目的・安全上の位置付け・公式版の見分け方](FIRST_READ.md)**
>
> **▶ [ここを見てください：MIT Licenseと安全性は別の約束です](docs/LICENSE_AND_SECURITY.md)**

**MIN0 CORE FORTH 0.1 — Educational & Experimental Reference Release**

Current release: `0.1.0`. For the shortest path from Viewer to actual execution, see
**[QUICKSTART.md](docs/QUICKSTART.md)**.

## まず試してみる

- **[Guided Viewerをブラウザーで動かす](https://min0.github.io/min0-core-forth/viewer/value-trace.html)**
- **[5分間のQuick Start](docs/QUICKSTART.md)**
- **[なぜRubyとPythonで始めたのか](docs/PROJECT_ORIGIN.md)**
- **[設計・監査文書の一覧](docs/)**

## Repository案内

| 場所 | 内容 |
| --- | --- |
| [`viewer/`](viewer/) | Guided ViewerのHTML。通常は上の「ブラウザーで動かす」リンクを使用します |
| [`workbench/`](workbench/) | Python／Ruby実装、試験、相互確認、例題、test vector |
| [`docs/`](docs/) | 設計、解説、監査記録、リリース資料 |
| [`tools/`](tools/) | リリース監査・再現可能パッケージ作成工具 |

最上位には、最初に読む案内、ライセンス、安全性、versionなど、入口として必要なファイルだけを
置いています。

Official repository: **<https://github.com/MIN0/min0-core-forth>**  
Release tag: **`v0.1.0`**

Release status and public-safety preparation are recorded in
**[RELEASE_AUDIT_0.1.md](docs/RELEASE_AUDIT_0.1.md)**. Source and documentation are licensed under the
**[MIT License](LICENSE)**. The license permits reuse but is not a security certification; the exact
distinction and supporting audit links are collected in **[LICENSE_AND_SECURITY.md](docs/LICENSE_AND_SECURITY.md)**.

MIN0 CORE FORTH is an independent educational and research project. It is not
an official implementation issued by a Forth standards organization, and it
does not yet claim complete Forth-standard conformance. Here, “CORE” means the
common mother system from which CPU-, MPU-, and FPGA-specific descendants can
grow.

## なぜRubyとPythonなのか

MIN0 CORE FORTHは、実機のCPUやメモリ容量を決める前に、さまざまな実装の共通の根となる
FORTHを自由に実験するために始まりました。Ruby版とPython版は最終ターゲットではなく、同じ
FORTHの意味を二つの独立した言語で表し、結果を照合する「実行できる仕様」です。一方だけでは
見落としやすい曖昧さや移植上の問題を早く見つけ、将来のMPU、FPGA、そのほかの実装へ進む前に
設計を育てます。開発者自身の80386アセンブラ経験、Rubyで再び感じたプログラミングの楽しさ、
そして現在の実験に欠かせないPythonも、この二言語構成につながりました。

詳しい背景は **[なぜMIN0 CORE FORTHをRubyとPythonで始めたのか](docs/PROJECT_ORIGIN.md)** に
まとめています。FORTH2020などで紹介するときの説明資料にも展開できる内容です。

## Fixed for this experiment

- 32-bit cells with two's-complement signed interpretation
- 32-bit byte addresses
- little-endian cell encoding
- 8-bit opcodes and 32-bit immediate operands
- a unified 64 KiB virtual memory reference profile (not a CORE-wide limit)
- separate logical data, return, and loop stacks
- absolute branch and call targets
- Forth true is `0xFFFFFFFF`; false is `0`
- deterministic VM exceptions for invalid instructions, stack underflow, and
  invalid memory access

`IP`, data-stack, return-stack, and loop-stack state are implemented now.
`W`, `UP`, `HERE`, and `STATE` belong to the later dictionary/compiler layer
and are intentionally not fake registers in this minimal execution engine.

`MEMORY_PROFILE_V0_1.md` defines logical byte addresses and distinct
instruction-fetch, data-read, and data-write operations. Python and Ruby now
route VM execution through compatible `FlatMemory` backends. This preserves
the current flat image. Their matching `RegionMemory` backends additionally
enforce named-region read, write, execute, programming, boundary, and unmapped
address rules. `cross_region_memory_check.py` verifies the split CODE/RAM map.
The runtime dictionary and outer interpreter use VM byte/block APIs rather
than accessing a flat host-language byte array directly. A regression test
compiles and executes `: SQUARE DUP * ; 5 SQUARE` with CODE and DICTIONARY in
separate `RegionMemory` regions.

## Split dictionary and data space

`SPLIT_DICTIONARY_V0_1.md` defines the optional independent header and body
allocators. The legacy single-range layout remains the default. In split mode,
dictionary metadata can occupy one region while `CREATE` and `VARIABLE` bodies
occupy another; their stored payload addresses are authoritative. Python and
Ruby execute and compare the same CODE/DICTIONARY/DATA three-region program.

## DOES execution model

`DOES_DESCRIPTOR_V0_1.md` adds kind-5 XTs without changing the fixed XT size.
The XT points to a dictionary-space descriptor holding independent body and
behavior addresses. Python and Ruby execute such words both directly and from
compiled colon definitions with body in DATA and behavior in CODE. Source-level
`DOES>` parsing and `CREATE` inside defining words are implemented in
`SOURCE_DOES_V0_1.md`.
`CONSTRUCTOR_PLAN_V0_1.md` now supports `,` between `CREATE` and `DOES>` without
adding allocator-specific VM opcodes. Constructor-time `C,` is also implemented;
constructor-time `ALLOT` reserves an exact nonnegative byte count. `ALIGN`
is now an argument-free plan action, completing the initial constructor
allocator set without adding VM opcodes.
The constructor-plan v0.1 candidate is format-versioned and frozen for its
12-byte header, eight-byte steps, and action IDs 0-4. Readers reject corrupt or
unknown versions before child creation; `CONSTRUCTOR_PLAN_AUDIT_R0.md` records
the corruption, boundary, and rollback audit. This does not freeze the complete
persistent image format or any target ABI.
`CONSTRUCTOR_IMAGE_ROUNDTRIP_R0.md` then demonstrates Python-to-Ruby and
Ruby-to-Python reload and execution of a real RECORD: plan. The JSON envelope
used by that audit is deliberately a transport fixture, not the final
persistent-image format.
`IMAGE_ADDRESSING_R0.md` compares absolute, fully relocatable, and hybrid image
designs. Its Python/Ruby experiment moves typed dictionary metadata across new
CODE, DICTIONARY, and DATA bases and re-executes `RECORD:` successfully. The R0
recommendation is a resolved-absolute runtime with build/link-time relocation
records; typeless literal and raw data cells are never guessed to be addresses.
`CODE_RELOCATION_R0.md` implements the CODE side of that recommendation. The
interactive compiler emits typed records for calls, control flow, loops, and
address-producing words. A mixed image containing colon words, `VARIABLE`, and
`DOES>` is relocated across all three regions and executed identically by
Python and Ruby.
`RELOCATION_LINKER_R0.md` then combines all 68 CODE and DICTIONARY records in
one validated manifest. The copy-on-success linker rejects malformed records,
overlapping patches or regions, invalid pointers, and Reference32 overflow
before changing any component bytes.
`IMAGE_ENVELOPE_R0.md` binds those records to exact component digests and
allocator metadata. A different image, altered manifest, or altered allocator
state is rejected before linking. Authentication is explicitly `none`; a
fail-closed policy can already reject all unauthenticated images without
mistaking SHA-256 integrity for a signature.
`THREAT_MODEL_R0.md` now separates current controls from security claims that
are not implemented. Its executable Python/Ruby audit proves corruption,
manifest tampering, bounded infinite execution, and rollback below a trusted
minimum generation are blocked. A maliciously rebuilt unsigned image remains
an explicit Development Profile gap.
`AUTH_COMPARISON_R0.md` applies HMAC-SHA256 and Ed25519 to the same real image
identity. Python and Ruby produce identical tags, public keys, and signatures.
The experiment keeps HMAC optional for tightly controlled per-device use and
selects Ed25519 as the leading distributed-image candidate.
`ANTI_ROLLBACK_R0.md` adds an unsigned 64-bit generation in image-envelope v2.
`SIGNED_IMAGE_R0.md` advances the signed envelope to v3, binding the Ed25519
scheme and key ID into the signed identity. The current v4 additionally binds
normal/recovery image roles. A trusted minimum rejects correctly
signed older images; the in-memory prototype advances that minimum only after
a successful install commit. Target-specific persistent power-loss safety
remains future work.
`TRANSACTIONAL_INSTALL_R0.md` adds a power-loss-injectable A/B host model.
Incomplete slot markers and trusted-generation records remain invisible until
checksum sealing. Boot scans both slots instead of trusting a mutable active
pointer, and the minimum generation advances only after a successful candidate
boot. Corruption of the only current-generation image after that commit still
requires an independent recovery path.
`RECOVERY_PATH_R0.md` provides that host path with a protected recovery image,
separate recovery key and generation domain, and power-loss-safe repair of a
current-generation normal slot. Recovery-media provisioning and restricted
recovery-runtime capabilities remain target work.
`TRUST_ROTATION_R0.md` adds a root-signed, epoch-versioned trust bundle with
role-scoped active/revoked image keys. Bundle slots and the minimum trust epoch
are separately journaled. Rotation uses an overlap window: add new keys, boot
newly signed normal/recovery images, then revoke old keys. Revoking the old
recovery key before that boot is tested as an unsafe ordering.
`ROOT_ROTATION_R0.md` rotates the pinned offline root through a hash-linked,
cross-signed policy chain. Adding or retiring a root requires signatures from
all roots active before or after the transition. The new-root-signed trust
bundle is verified during the overlap before the old root is retired. A/B root
state, a separately sealed minimum epoch, power cuts, chain tampering, key
replacement, reactivation, and rollback are exercised in both languages.
`PERSISTENT_PACKAGE_R0.md` adds the bounded external-file boundary. A fixed
little-endian header and directory reject length/count bombs, duplicate or
overlapping sections, truncation, trailing data, and unknown versions before
metadata interpretation. Canonical JSON has explicit depth, string, integer,
node, and byte limits. Root policy, trust bundle, and signed image packages are
round-tripped through real files and produce identical bytes in Python/Ruby.
Container checksums detect corruption but are not treated as authentication;
a re-checksummed CODE modification is rejected by the image signature layer.
`LOADER_STATE_MACHINE_R0.md` integrates that parser with root/trust state and
normal/recovery A/B stores. Its phase is derived from sealed persistent state,
not supplied by a package or mutable pointer. Before writing a root candidate,
the current trust bundle must remain valid; before writing a trust candidate,
both current images must remain bootable. The complete old-to-new rotation,
unsafe ordering rejection, recovery fallback, and root power cuts agree in
Python and Ruby.
`CAPABILITY_BOUNDARY_R0.md` then separates ordinary runtime inspection,
normal-image Monitor updates, recovery-only normal repair, and privileged
root/trust/recovery provisioning. Issued sessions are revocable and bind a
staged transaction to its initiating session and slot. An authorized session
can explicitly adopt a persistent pending phase after restart; an ordinary
runtime cannot. A dedicated repair path restores a newer normal image when no
normal A/B slot can boot.
`MONITOR_CONTROL_R0.md` adds the execution-side control boundary. A trusted,
opaque Monitor session can request a pause that is accepted only between
complete VM instructions. Per-slice instruction budgets and a latched watchdog
stop execution without discarding IP or any of the three stacks; observer
sessions can inspect copies of state but cannot pause or resume the VM. The
Python and Ruby demonstrations agree across requested pause, budget exhaustion,
watchdog acknowledgement, resume, and final HALT.
`MONITOR_PATCH_R0.md` builds the first deliberately dynamic call path on that
boundary. Dictionary kind 7 stores a colon-code target, while compiled callers
use `ICALL` to read its slot at each invocation. Only an acknowledged paused
Monitor may switch it; observers receive copied snapshots and audit records.
Before every resume, a seal over IP, all stacks, and the live dictionary rejects
out-of-band mutation. Existing ordinary `CALL` sites remain unchanged.
`DEFER_SOURCE_R0.md` adds interpret-state `DEFER`, tick (`'`), `IS`, and
`ACTION-OF`. DEFER slots contain real dictionary XT addresses rather than raw
code pointers. Build-time source may initialize a slot; once the Monitor owns
the dictionary, ordinary source mutation is locked and only the authenticated
four-token control form `' target IS defer` can change it. `ACTION-OF` remains
a read-only query for observers.
`COMPILED_DEFER_R0.md` separates compile-state semantics by profile. The
default `safe-runtime` profile permits read-only `[']` and `ACTION-OF` but
rejects compiled `IS`. The explicit `standard-build` experiment enables a
validated `DSET` opcode only on an image-build VM. Monitor attachment disables
that opcode, locks the permission bit into the resume seal, and leaves the
authenticated four-token control transaction as the only runtime mutation path.
`IMAGE_EXECUTION_PROFILES_R0.md` carries this distinction into signed image
envelope v5. A `defer-store-slot` relocation automatically marks an image
`standard-build`; the default safe-runtime loader rejects it before touching
the inactive slot. Recovery images are always restricted to `safe-runtime`.
`BYTECODE_VERIFIER_R0.md` then decodes the real CODE component at instruction
boundaries and cross-checks each typed relocation. Literal byte `0x25` is not
mistaken for `DSET`; a real `DSET` and its `defer-store-slot` record must agree
before the signed execution profile is accepted.
`SEALED_EXECUTION_R0.md` carries those boundaries into runtime. Verified CODE
is sealed one-way to runtime `rx`; ordinary `!`, reload, and clear cannot alter
it. Every resume, direct/indirect call, branch, and return must land on a
verified instruction boundary. Interpret-state primitives use fixed two-byte
dispatch slots, so `2 3 +` continues to work after sealing without rewriting
CODE.
`W_X_PUBLICATION_R0.md` separates writable non-executable staging from the
executable runtime memory. The validated artifact is privileged-programmed
into a distinct `rx` CODE region and immediately sealed. Mutating staging after
publication cannot change runtime bytes; staging execution, runtime writes,
runtime reprogramming, and pre-publication image tampering are rejected in both
languages.
`DICTIONARY_CAPABILITY_R0.md` closes the corresponding runtime dictionary
write path. Published headers and allocators are structurally frozen, while
DATA remains ordinarily writable. Raw `!`, host write, loader program, source
`IS`, and forged capabilities cannot change DICTIONARY. Only an authenticated
paused Monitor can open a narrow checked scope for one DEFER payload update,
and the resulting four-byte-range change is audited.

## Semantic trace

`TRACE_V0_1.md` defines the optional, versioned observer for the future Guided
Viewer. Python and Ruby emit the same 13 semantic events for `VALUE:` creation
and execution, including stack and allocator snapshots plus deterministic basic
explanations. Observer failures are isolated from FORTH execution, and all
source-derived fields are explicitly marked as observed data, not instructions.

`VIEWER_GUIDE_V0_1.md` and `viewer/value-trace.html` provide the first Guided
Viewer. The self-contained offline HTML is generated from an actual Python VM
run. Its source-word view advances by completed source-word operation and shows
the data stack before and after each word. A focused construction view keeps
only child creation, allocator actions, publication, and rollback. The internal
view exposes every semantic event. All views include source focus, three memory regions,
three stacks, allocator state, deterministic explanations, and optional raw
event data. It performs no network or AI calls and inserts trace-derived strings
only as text.
DOES-word calls can be stepped into: the Viewer shows dictionary-word entry,
body-address push, mapped behavior word execution, and return. For `ANSWER`, the
inner `@` visibly changes the data stack from `[0x8000]` to `[123]` while the
return address remains observable on the return stack.
The same offline Viewer also contains an actual failing `VALUE: EMPTY` run.
Its final screen proves rollback by comparing saved and restored header HERE,
data HERE, and LATEST, while showing all three stacks restored and empty.
The third scenario executes `: RECORD: CREATE C, ALLOT ALIGN ;` and makes the
DATA allocator progression `0x8000 -> 0x8001 -> 0x8003 -> 0x8004` directly
observable. It opens in the focused construction view so `C,`, `ALLOT`, and
`ALIGN` can be stepped through without the surrounding segment events.
Two beginner scenarios compare `2 3 4 * + .` (14) with `2 3 * 4 + .` (10)
using six measured source-word steps. The interpret-state `.` word records
signed decimal terminal output without adding a VM opcode. A further measured
scenario compiles `: GREET ." Hello from compiled Forth" ;`, shows the DATA
placement and terminal-type SERVICE call at the source-word boundary, and then
shows the text produced by executing `GREET`. The Viewer also
provides an explicitly non-executing editor whose contents can be copied or
saved as `.fth` for testing in the Python/Ruby hosts or a future target.

## Run

For normal use, start with the full host launcher:

```powershell
python workbench/min0_forth.py
ruby workbench/min0_forth.rb
python workbench/min0_forth.py -z workbench/examples/hello.fth
ruby workbench/min0_forth.rb -z workbench/examples/hello.fth
```

The longer list below contains development and cross-language commands. Run it after changing to the
workbench directory with `Set-Location workbench`.

```powershell
python demo.py
python -m unittest -v
python generate_test_vectors.py
ruby test_ruby_vm.rb
python cross_check.py
python cross_cli_check.py
python run_source.py examples/basic.fth
ruby run_source.rb examples/basic.fth
python cross_compile_check.py
python cross_dictionary_check.py
python cross_outer_check.py
python cross_control_check.py
python cross_loop_check.py
python cross_counted_loop_check.py
python cross_extended_counted_loop_check.py
ruby test_ruby_extended_counted_loops.rb
python cross_data_definition_check.py
ruby test_ruby_data_definitions.rb
python cross_create_check.py
ruby test_ruby_address_create.rb
python cross_character_check.py
ruby test_ruby_character_data.rb
ruby test_ruby_string_output.rb
python cross_compiled_string_relocation_check.py
ruby test_ruby_compiled_string_relocation.rb
python cross_service_output_check.py
ruby test_ruby_service_boundary.rb
python cross_region_memory_check.py
python cross_split_dictionary_check.py
python cross_does_descriptor_check.py
ruby test_ruby_does_descriptor.rb
python cross_source_does_check.py
ruby test_ruby_source_does.rb
python cross_value_constructor_check.py
python cross_byte_constructor_check.py
python cross_allot_constructor_check.py
python cross_align_constructor_check.py
python cross_constructor_image_check.py
python cross_constructor_relocation_check.py
python cross_code_relocation_check.py
python cross_full_image_relocation_check.py
python cross_linker_check.py
python cross_image_envelope_check.py
python cross_security_boundary_check.py
python cross_auth_comparison_check.py
python cross_anti_rollback_check.py
python cross_signed_image_check.py
python cross_transactional_install_check.py
python cross_recovery_path_check.py
python cross_trust_rotation_check.py
python cross_root_rotation_check.py
python cross_persistent_package_check.py
python cross_loader_state_check.py
python cross_capability_boundary_check.py
python cross_monitor_control_check.py
ruby test_ruby_monitor_control.rb
python cross_monitor_patch_check.py
ruby test_ruby_monitor_patch.rb
python cross_defer_source_check.py
ruby test_ruby_defer_source.rb
python cross_compiled_defer_check.py
ruby test_ruby_compiled_defer.rb
python cross_image_execution_profile_check.py
ruby test_ruby_image_execution_profile.rb
python cross_bytecode_verifier_check.py
ruby test_ruby_bytecode_verifier.rb
python cross_sealed_execution_check.py
ruby test_ruby_sealed_execution.rb
python cross_w_x_publish_check.py
ruby test_ruby_w_x_publish.rb
python cross_dictionary_capability_check.py
ruby test_ruby_dictionary_capability.rb
python cross_trace_check.py
ruby test_ruby_trace.rb
python build_trace_viewer.py
```

The demo executes bytecode equivalent to:

```forth
: SQUARE DUP * ;
: DOUBLE DUP + ;

5 SQUARE 7 DOUBLE
```

The expected final data stack is `[25, 14]`.

`cross_check.py` runs every `.fcb` vector through both `run_image.py` and
`run_image.rb`. A vector passes only when both implementations return the same
stack and step count, and that stack matches `test_vectors/manifest.json`.

## Minimal source language

- whitespace-separated, case-insensitive tokens
- `\` line comments
- decimal and `0x` hexadecimal integer literals
- `: NAME ... ;` colon definitions
- forward references between colon definitions
- primitives: `NOP @ ! C@ C! DROP DUP SWAP OVER + - * AND OR XOR < = I J UNLOOP CELL+ CELLS ALIGNED CHAR+ CHARS`

The compiler emits the executable main token sequence first, followed by
`HALT`, then each colon body ending in `EXIT`. This is a compiler dictionary,
not yet a runtime Forth dictionary with headers and searchable names.

## Runtime dictionary experiment

`min0_core_forth_dictionary.py` and `min0_core_forth_dictionary.rb` independently build
the linked memory layout in `DICTIONARY_V0_1.md`. `cross_dictionary_check.py`
requires their raw bytes, addresses, flags, and decoded entries to agree.

## Interpret-state outer interpreter

`min0_core_forth_outer.py` and `min0_core_forth_outer.rb` implement the token decision in
`OUTER_INTERPRETER_V0_1.md`. They parse numbers, search the runtime dictionary,
and execute primitive or colon XTs while preserving the data stack. Compile
state and interactive `:`/`;` are defined in `INTERACTIVE_COMPILER_V0_1.md`.
Incomplete definitions are hidden, successful definitions become searchable,
and failed definitions roll back both dictionary and compiled code. Interpret-only
`WORDS` lists the active visible vocabulary alphabetically, separating words that
existed when the outer interpreter started from definitions added by the user.
When a name is redefined, only its newest searchable definition is listed.
`TERMINAL_OUTPUT_V0_1.md` defines the host/device boundary for output. The
interpret-state `EMIT` consumes the low eight bits of one cell, `CR` emits a
logical LF, and `TYPE` emits a validated complete byte range. Python/Ruby retain
the same exact output stream without adding target-specific VM opcodes or
automatically printing control characters. `TYPE` faults atomically before any
partial output and can read preloaded read-only Flash／EEPROM-like memory.
`STRING_LITERALS_V0_1.md` adds a quote-aware source path: interpret-state `S"`
stores exact byte text in dictionary DATA and returns `c-addr u`, while `."`
outputs exact quoted text without allocation. Quoted case, spaces, and backslashes
are preserved; characters above U+00FF and unterminated strings are rejected before
state changes. Interactive colon definitions compile `S"` into a typed
`string-address` DATA relocation followed by its byte length. A measured image
moves the literal to a new DATA base, seals that region read-only, and still
emits it through `TYPE`; write, reprogram, and clear attempts are rejected.
Compiled `."` now emits the same relocated address and length followed by generic
`SERVICE 1` (`terminal-type-v0.1`). The verifier derives required IDs from actual
CODE and protects the four-byte service operand from relocation or branch entry.
Before CODE is sealed, every required ID must exist in the trusted target registry;
after seal, both the exact image allowlist and registry are immutable. The nested
example emits `Hello Service` with CODE=`rx` and DATA=`r`, identically in Python
and Ruby. Image data can never register or replace an arbitrary callback. The
authority boundary and its deliberate limits are in `OUTPUT_SERVICE_BOUNDARY_R0.md`.

## Conditional control flow

The interactive compiler implements nested `IF ELSE THEN` using the patch
stack defined in `CONTROL_FLOW_V0_1.md`. The language-pair check compares the
patched bytecode, dictionary image digest, final stack, instruction count,
compiler state, and empty control-stack depth.

## Loop control

`BEGIN UNTIL`, `BEGIN AGAIN`, and `BEGIN WHILE REPEAT` use the same structural
stack as conditional control flow. Their matching, patching, nesting, error
rollback, and cross-language checks are defined in `LOOP_CONTROL_V0_1.md`.

## Counted loops and stack limits

The VM adds a logical loop stack and `DO ?DO LOOP +LOOP I J UNLOOP LEAVE` as
specified by `COUNTED_LOOPS_V0_1.md`. Configurable data, return, and loop
capacities, overflow/underflow errors, and XT-level stack recovery are
specified by `STACK_LIMITS_V0_1.md`.

## Data definitions

The interactive layer implements `HERE , C, ALLOT ALIGN CONSTANT VARIABLE CREATE`
as specified by `DATA_DEFINITIONS_V0_1.md`. Dictionary headers and data share
the upper memory region; compiled code retains its separate lower-region
`CODE-HERE`. Constants, variables, and created words compile to ordinary `LIT`
bytecode. `CELL+`, `CELLS`, and `ALIGNED` provide cell-size-aware addressing,
while `C@`, `C!`, `CHAR+`, and `CHARS` provide an explicit unsigned 8-bit
character model. Allocation failures preserve arguments and roll back partial
definitions.

## Still to decide or implement

- target-specific streaming persistent reader and fixed-buffer profile
- host I/O interface
- configurable 16/32/64-bit profiles
- persistent relocation-manifest validation and transactional linker
