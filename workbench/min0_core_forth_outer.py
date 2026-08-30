"""Interpret-state outer interpreter for MIN0 CORE FORTH (draft v0.1)."""

from __future__ import annotations

from min0_core_forth_compiler import PRIMITIVES, QuotedText, parse_number, tokenize
from min0_core_forth_dictionary import (
    CONSTRUCTOR_ACTION_ALIGN,
    CONSTRUCTOR_ACTION_ALLOT,
    CONSTRUCTOR_ACTION_C_COMMA,
    CONSTRUCTOR_ACTION_COMMA,
    CONSTRUCTOR_ACTION_END,
    KIND_COLON,
    KIND_CONSTANT,
    KIND_CREATED,
    KIND_DEFER,
    KIND_DEFINER,
    KIND_DOES,
    KIND_PRIMITIVE,
    KIND_VARIABLE,
    DictionaryEntry,
    RuntimeDictionary,
)
from min0_core_forth_relocation import (
    REFERENCE32_WIDTH,
    SECTION_CODE,
    TARGET_CODE,
    TARGET_DATA,
    TARGET_DICTIONARY,
    RelocationRecord,
)
from min0_core_forth_vm import (
    DataStackOverflow,
    Min0CoreForthVM,
    Op,
    StackUnderflow,
    UnassignedDefer,
    signed,
)


STATE_INTERPRET = 0
STATE_COMPILE = 1
SOURCE_PROFILE_SAFE_RUNTIME = "safe-runtime"
SOURCE_PROFILE_STANDARD_BUILD = "standard-build"
DEFAULT_CODE_BASE = 0x1000
PRIMITIVE_DISPATCH_SLOT_BYTES = 2
TERMINAL_TYPE_SERVICE_ID = 1
CONTROL_WORDS = frozenset(
    {
        "IF", "ELSE", "THEN", "BEGIN", "UNTIL", "AGAIN", "WHILE", "REPEAT",
        "DO", "?DO", "LOOP", "+LOOP", "LEAVE", "DOES>", "[']",
    }
)
DATA_WORDS = frozenset(
    {
        "HERE", ",", "C,", "ALLOT", "ALIGN", "CONSTANT", "VARIABLE",
        "CREATE", "DEFER", "'", "IS", "ACTION-OF",
    }
)
HOST_WORDS = frozenset({".", "EMIT", "CR", "TYPE", "WORDS", 'S"', '."'})
WORD_LIST_STARTUP_WORDS = frozenset({":", ";"}) | CONTROL_WORDS | DATA_WORDS | HOST_WORDS
WORD_LIST_USER_HEADING = (
    "--- ここから先はユーザーが : で定義したワードなどです ---"
)
WORD_LIST_LINE_WIDTH = 72


class OuterInterpreterError(ValueError):
    pass


class UnknownWord(OuterInterpreterError):
    pass


class InvalidExecutionToken(OuterInterpreterError):
    pass


class CompileStateError(OuterInterpreterError):
    pass


class OuterInterpreter:
    """Host prototype that consumes the VM-resident runtime dictionary."""

    def __init__(
        self,
        vm: Min0CoreForthVM,
        dictionary: RuntimeDictionary,
        *,
        code_base: int = DEFAULT_CODE_BASE,
        trace: object | None = None,
        source_profile: str = SOURCE_PROFILE_SAFE_RUNTIME,
    ) -> None:
        self.vm = vm
        self.dictionary = dictionary
        self.trace = trace
        self.trace_failures: list[str] = []
        self.output: list[str] = []
        self._startup_dictionary_entries = frozenset(
            entry.header_address
            for entry in dictionary.entries(include_hidden=False)
        )
        if source_profile not in (
            SOURCE_PROFILE_SAFE_RUNTIME, SOURCE_PROFILE_STANDARD_BUILD
        ):
            raise OuterInterpreterError(f"unknown source profile {source_profile!r}")
        if source_profile == SOURCE_PROFILE_STANDARD_BUILD and not vm.allow_defer_store:
            raise OuterInterpreterError(
                "standard-build profile requires a build VM with DEFER store enabled"
            )
        self.source_profile = source_profile
        primitive_opcodes = tuple(sorted({int(opcode) for opcode in PRIMITIVES.values()}))
        operand_opcodes = {
            int(Op.LIT), int(Op.CALL), int(Op.ICALL), int(Op.DSET),
            int(Op.BRANCH), int(Op.ZBRANCH), int(Op.LOOP), int(Op.PLOOP),
            int(Op.QDO), int(Op.LEAVE), int(Op.SERVICE),
        }
        if operand_opcodes.intersection(primitive_opcodes):
            raise OuterInterpreterError(
                "fixed primitive dispatch only supports operand-free opcodes"
            )
        dispatch_size = len(primitive_opcodes) * PRIMITIVE_DISPATCH_SLOT_BYTES
        if dictionary.base <= dispatch_size:
            raise OuterInterpreterError("dictionary base leaves no dispatch-table space")
        self.return_trampoline = dictionary.base - 1
        self.primitive_trampoline = self.return_trampoline - dispatch_size
        self._primitive_dispatch = {
            opcode: self.primitive_trampoline
            + index * PRIMITIVE_DISPATCH_SLOT_BYTES
            for index, opcode in enumerate(primitive_opcodes)
        }
        if code_base < 0 or code_base >= self.primitive_trampoline:
            raise OuterInterpreterError("code base is outside the executable region")
        self.code_base = code_base
        self.code_here = code_base
        self.code_limit = self.primitive_trampoline
        self.state = STATE_INTERPRET
        self.current_definition: DictionaryEntry | None = None
        self.control_stack: list[tuple] = []
        self._saved_dictionary_here = dictionary.here
        self._saved_data_here = dictionary.data_here
        self._saved_latest = dictionary.latest
        self._saved_code_here = code_base
        self._saved_relocation_count = 0
        self._definer_create_seen = False
        self._definer_behavior_address: int | None = None
        self._definer_steps: list[tuple[int, int]] = []
        self._definer_segment_start: int | None = None
        self._code_source_words: dict[int, tuple[int, str]] = {}
        self._relocation_records: list[RelocationRecord] = []
        dispatch = bytearray()
        for opcode in primitive_opcodes:
            dispatch.extend((opcode, int(Op.HALT)))
        dispatch.append(int(Op.HALT))
        self.vm.memory.program(self.primitive_trampoline, bytes(dispatch))
        self.vm.register_service(TERMINAL_TYPE_SERVICE_ID, self._service_type)

    def relocation_manifest(self) -> list[dict[str, str | int]]:
        """Return a stable copy of compiler-emitted typed references."""

        return [record.to_dict() for record in self._relocation_records]

    @property
    def terminal_text(self) -> str:
        """Return the exact host-side output stream accumulated so far."""

        return "".join(self.output)

    def execution_extra_entries(self) -> list[int]:
        """Validate and return fixed dispatch/HALT boundaries outside image CODE."""

        entries: list[int] = []
        for opcode, address in sorted(self._primitive_dispatch.items()):
            expected = bytes((opcode, int(Op.HALT)))
            if self.vm.read_bytes(address, 2) != expected:
                raise OuterInterpreterError("fixed primitive dispatch was modified")
            entries.extend((address, address + 1))
        if self.vm.read_u8(self.return_trampoline) != int(Op.HALT):
            raise OuterInterpreterError("return trampoline was modified")
        entries.append(self.return_trampoline)
        return entries

    def interpret(self, source: str) -> list[int]:
        tokens = tokenize(source)
        index = 0
        try:
            while index < len(tokens):
                token = tokens[index]
                data_before = list(self.vm.data_stack)
                state_before = self.state
                code_here_before = self.code_here
                if isinstance(token, QuotedText):
                    if self.state == STATE_COMPILE:
                        byte_count = self._compile_quoted_text(token)
                        action = (
                            "compile-string-literal"
                            if token.word == 'S"'
                            else "compile-output-literal"
                        )
                        self._trace_source_word(
                            token.word,
                            index,
                            index,
                            action,
                            [str(byte_count)],
                            data_before,
                            state_before,
                            code_here_before,
                        )
                        index += 1
                        continue
                    if self.state != STATE_INTERPRET:
                        raise CompileStateError(
                            f"{token.word!r} is interpret-only in v0.1"
                        )
                    byte_count = self._interpret_quoted_text(token)
                    action = (
                        "push-string-literal"
                        if token.word == 'S"'
                        else "emit-string-literal"
                    )
                    self._trace_source_word(
                        token.word,
                        index,
                        index,
                        action,
                        [str(byte_count)],
                        data_before,
                        state_before,
                        code_here_before,
                    )
                    index += 1
                    continue
                if self.state == STATE_INTERPRET and token in (
                    "DEFER", "'", "IS", "ACTION-OF"
                ):
                    if index + 1 >= len(tokens):
                        raise CompileStateError(
                            f"{token!r} requires a word name in the same input"
                        )
                    name = tokens[index + 1]
                    if not isinstance(name, str):
                        raise CompileStateError(
                            f"{token!r} requires an ordinary unquoted word name"
                        )
                    self._interpret_defer_word(token, name)
                    self._trace_source_word(
                        token, index, index + 1, "defer-source-operation",
                        [name], data_before, state_before, code_here_before,
                    )
                    index += 2
                    continue
                if self.state == STATE_INTERPRET and token in (
                    "CONSTANT", "VARIABLE", "CREATE"
                ):
                    if index + 1 >= len(tokens):
                        raise CompileStateError(
                            f"{token!r} requires a name in the same input"
                        )
                    name = tokens[index + 1]
                    if not isinstance(name, str):
                        raise CompileStateError(
                            f"{token!r} requires an ordinary unquoted word name"
                        )
                    if token == "CONSTANT":
                        self._define_constant(name)
                    elif token == "VARIABLE":
                        self._define_variable(name)
                    else:
                        self._define_created(name)
                    self._trace_source_word(
                        token,
                        index,
                        index + 1,
                        "define-data-word",
                        [name],
                        data_before,
                        state_before,
                        code_here_before,
                    )
                    index += 2
                    continue
                if self.state == STATE_INTERPRET and token == ":":
                    if index + 1 >= len(tokens):
                        raise CompileStateError("':' requires a word name in the same input")
                    name = tokens[index + 1]
                    if not isinstance(name, str):
                        raise CompileStateError(
                            "':' requires an ordinary unquoted word name"
                        )
                    self._begin_definition(name)
                    self._trace_source_word(
                        token,
                        index,
                        index + 1,
                        "begin-definition",
                        [name],
                        data_before,
                        state_before,
                        code_here_before,
                    )
                    index += 2
                    continue
                if self.state == STATE_COMPILE:
                    if token == ":":
                        raise CompileStateError("nested ':' definition is not allowed")
                    if token in ("[']", "ACTION-OF", "IS"):
                        if index + 1 >= len(tokens):
                            raise CompileStateError(
                                f"{token!r} requires a word name in the same input"
                            )
                        name = tokens[index + 1]
                        if not isinstance(name, str):
                            raise CompileStateError(
                                f"{token!r} requires an ordinary unquoted word name"
                            )
                        self._compile_defer_source_word(token, name)
                        self._trace_source_word(
                            token, index, index + 1, "compile-defer-source-operation",
                            [name], data_before, state_before, code_here_before,
                        )
                        index += 2
                        continue
                    if token == ";":
                        self._finish_definition()
                        action = "finish-definition"
                    else:
                        self._compile_token(token)
                        action = "compile-token"
                    self._trace_source_word(
                        token,
                        index,
                        index,
                        action,
                        [],
                        data_before,
                        state_before,
                        code_here_before,
                    )
                    index += 1
                    continue
                if token == ";":
                    raise CompileStateError("';' outside a definition")
                if token in CONTROL_WORDS:
                    raise CompileStateError(f"{token!r} is compile-only")
                if parse_number(token) is None:
                    entry = self.dictionary.find(token)
                    if entry is not None and entry.kind == KIND_DEFINER:
                        if index + 1 >= len(tokens):
                            raise CompileStateError(
                                f"defining word {token!r} requires a child name "
                                "in the same input"
                            )
                        child_name = tokens[index + 1]
                        if not isinstance(child_name, str):
                            raise CompileStateError(
                                f"defining word {token!r} requires an ordinary "
                                "unquoted child name"
                            )
                        self._trace(
                            "word.execute.enter",
                            word=entry.name,
                            kind=entry.kind,
                            depth=0,
                            token_index=index,
                            token_end=index + 1,
                            data_stack_before=data_before,
                        )
                        try:
                            self._execute_definer(entry, child_name)
                        except Exception as exc:
                            self._trace_source_word_error(
                                token,
                                index,
                                index + 1,
                                [child_name],
                                data_before,
                                state_before,
                                code_here_before,
                                exc,
                            )
                            raise
                        self._trace_source_word(
                            token,
                            index,
                            index + 1,
                            "execute-definer",
                            [tokens[index + 1]],
                            data_before,
                            state_before,
                            code_here_before,
                        )
                        index += 2
                        continue
                self._interpret_token(token)
                if token in {".", "EMIT", "CR", "TYPE", "WORDS"}:
                    action = {
                        ".": "emit-number",
                        "EMIT": "emit-character",
                        "CR": "emit-newline",
                        "TYPE": "emit-string",
                        "WORDS": "list-words",
                    }[token]
                elif parse_number(token) is not None:
                    action = "push-number"
                else:
                    action = "execute-word"
                self._trace_source_word(
                    token,
                    index,
                    index,
                    action,
                    [],
                    data_before,
                    state_before,
                    code_here_before,
                )
                index += 1
        except Exception:
            if self.state == STATE_COMPILE:
                self._abort_definition()
            raise
        return list(self.vm.data_stack)

    def _interpret_token(self, token: str) -> None:
        if token == ".":
            value = self._peek_data(".")
            self.output.append(str(signed(value)))
            self.vm.pop()
            return
        if token == "EMIT":
            value = self._peek_data("EMIT")
            self.output.append(chr(value & 0xFF))
            self.vm.pop()
            return
        if token == "CR":
            self.output.append("\n")
            return
        if token == "TYPE":
            self._service_type()
            return
        if token == "WORDS":
            self.output.append(self._word_listing())
            return
        if token == "HERE":
            self.vm.push(self.dictionary.data_here)
            return
        if token == ",":
            value = self._peek_data(",")
            self.dictionary.comma(value)
            self.vm.pop()
            return
        if token == "C,":
            value = self._peek_data("C,")
            self.dictionary.c_comma(value)
            self.vm.pop()
            return
        if token == "ALLOT":
            count = signed(self._peek_data("ALLOT"))
            self.dictionary.allot(count)
            self.vm.pop()
            return
        if token == "ALIGN":
            self.dictionary.align_here()
            return
        number = parse_number(token)
        if number is not None:
            self.vm.push(number)
            return
        entry = self.dictionary.find(token)
        if entry is None:
            raise UnknownWord(f"unknown word {token!r}")
        self.execute(entry)

    def _word_listing(self) -> str:
        """Return visible active words split at the interpreter startup boundary."""

        active_entries: dict[str, DictionaryEntry] = {}
        for entry in self.dictionary.entries(include_hidden=False):
            active_entries.setdefault(entry.name, entry)

        startup_names = set(WORD_LIST_STARTUP_WORDS)
        user_names: set[str] = set()
        for name, entry in active_entries.items():
            if name in WORD_LIST_STARTUP_WORDS:
                continue
            if entry.header_address in self._startup_dictionary_entries:
                startup_names.add(name)
            else:
                user_names.add(name)

        return "\n".join(
            (
                "起動時から使えるワード",
                self._format_word_names(startup_names),
                "",
                WORD_LIST_USER_HEADING,
                self._format_word_names(user_names) if user_names else "（まだありません）",
                "",
            )
        )

    @staticmethod
    def _format_word_names(names: set[str]) -> str:
        lines: list[str] = []
        current = ""
        for name in sorted(names):
            candidate = name if not current else f"{current} {name}"
            if current and len(candidate) > WORD_LIST_LINE_WIDTH:
                lines.append(current)
                current = name
            else:
                current = candidate
        if current:
            lines.append(current)
        return "\n".join(lines)

    def _interpret_quoted_text(self, token: QuotedText) -> int:
        raw = self._encode_quoted_text(token)
        if token.word == '."':
            self.output.append(token.text)
            return len(raw)
        if token.word != 'S"':
            raise AssertionError(token.word)
        if len(self.vm.data_stack) + 2 > self.vm.max_data_depth:
            raise DataStackOverflow(
                f"data stack limit {self.vm.max_data_depth} cell(s) exceeded"
            )
        address = self.dictionary.data_here
        if raw:
            self.vm.memory.check_write(address, len(raw))
        allocated = self.dictionary.allot(len(raw))
        if raw:
            self.vm.write_bytes(allocated, raw)
        self.vm.push(allocated)
        self.vm.push(len(raw))
        return len(raw)

    def _compile_quoted_text(self, token: QuotedText) -> int:
        raw = self._encode_quoted_text(token)
        if token.word not in ('S"', '."'):
            raise AssertionError(token.word)
        if raw:
            address = self.dictionary.data_here
            self.vm.memory.check_write(address, len(raw))
            address = self.dictionary.allot(len(raw))
            self.vm.write_bytes(address, raw)
        else:
            address = self.dictionary.body_base
        start = self.code_here
        self._emit_opcode(Op.LIT)
        self._emit_reference(address, TARGET_DATA, "string-address")
        self._emit_opcode(Op.LIT)
        self._emit_cell(len(raw))
        if token.word == '."':
            self._emit_opcode(Op.SERVICE)
            self._emit_cell(TERMINAL_TYPE_SERVICE_ID)
        self._code_source_words[start] = (self.code_here, token.word)
        return len(raw)

    def _service_type(self) -> None:
        if len(self.vm.data_stack) < 2:
            raise StackUnderflow(
                "data stack needs 2 cell(s) for TYPE, "
                f"has {len(self.vm.data_stack)}"
            )
        address = self.vm.data_stack[-2]
        length = self.vm.data_stack[-1]
        if length == 0:
            del self.vm.data_stack[-2:]
            return
        raw = self.vm.read_bytes(address, length)
        text = "".join(chr(byte) for byte in raw)
        self.output.append(text)
        del self.vm.data_stack[-2:]

    @staticmethod
    def _encode_quoted_text(token: QuotedText) -> bytes:
        try:
            return bytes(ord(character) for character in token.text)
        except ValueError as exc:
            raise CompileStateError(
                f"{token.word} supports only byte characters U+0000..U+00FF"
            ) from exc

    def _begin_definition(self, name: str) -> None:
        if name in (":", ";") or name in DATA_WORDS or name in HOST_WORDS:
            raise CompileStateError(f"invalid definition name {name!r}")
        self._saved_dictionary_here = self.dictionary.here
        self._saved_data_here = self.dictionary.data_here
        self._saved_latest = self.dictionary.latest
        self._saved_code_here = self.code_here
        self._saved_relocation_count = len(self._relocation_records)
        try:
            self.current_definition = self.dictionary.add_colon(
                name, self.code_here, hidden=True
            )
        except Exception:
            self.current_definition = None
            raise
        self.state = STATE_COMPILE
        self.control_stack.clear()
        self._definer_create_seen = False
        self._definer_behavior_address = None
        self._definer_steps.clear()
        self._definer_segment_start = None

    def _finish_definition(self) -> None:
        if self.current_definition is None:
            raise CompileStateError("no current definition")
        if self.control_stack:
            kind = self.control_stack[-1][0]
            raise CompileStateError(f"unresolved {kind!r} before ';'")
        if self._definer_create_seen:
            if self._definer_behavior_address is None:
                self._finish_constructor_plan()
            else:
                self._emit_opcode(Op.EXIT)
            self.current_definition = self.dictionary.set_definer(
                self.current_definition,
                self._definer_steps,
                self._definer_behavior_address or 0,
            )
        else:
            self._emit_opcode(Op.EXIT)
        self.current_definition = self.dictionary.set_hidden(
            self.current_definition, False
        )
        if self._definer_create_seen:
            plan_address, behavior_address = self.dictionary.read_definer_descriptor(
                self.current_definition
            )
            self._trace(
                "definer.compile.complete",
                word=self.current_definition.name,
                plan=plan_address,
                behavior=behavior_address,
                step_count=len(self._definer_steps),
            )
        self.current_definition = None
        self.control_stack.clear()
        self._definer_create_seen = False
        self._definer_behavior_address = None
        self._definer_steps.clear()
        self._definer_segment_start = None
        self.state = STATE_INTERPRET

    def _abort_definition(self) -> None:
        self.vm.fill_bytes(
            self._saved_code_here, self.code_here - self._saved_code_here
        )
        self.code_here = self._saved_code_here
        del self._relocation_records[self._saved_relocation_count :]
        self.dictionary.restore(
            here=self._saved_dictionary_here,
            latest=self._saved_latest,
            data_here=self._saved_data_here,
        )
        self.current_definition = None
        self.control_stack.clear()
        self._definer_create_seen = False
        self._definer_behavior_address = None
        self._definer_steps.clear()
        self._definer_segment_start = None
        self._code_source_words = {
            address: source_word
            for address, source_word in self._code_source_words.items()
            if address < self._saved_code_here
        }
        self.state = STATE_INTERPRET

    def _compile_token(self, token: str) -> None:
        start = self.code_here
        self._compile_token_unmapped(token)
        if self.code_here > start:
            self._code_source_words[start] = (self.code_here, token)

    def _compile_defer_source_word(self, token: str, name: str) -> None:
        entry = self.dictionary.find(name)
        if entry is None:
            raise UnknownWord(f"unknown word {name!r} while compiling {token}")
        start = self.code_here
        if token == "[']":
            self._emit_opcode(Op.LIT)
            self._emit_reference(entry.xt, TARGET_DICTIONARY, "xt-literal")
        else:
            if entry.kind != KIND_DEFER:
                raise CompileStateError(f"{token} requires a DEFER word")
            if token == "ACTION-OF":
                self._emit_opcode(Op.LIT)
                self._emit_reference(
                    entry.xt + 4, TARGET_DICTIONARY, "action-of-slot"
                )
                self._emit_opcode(Op.FETCH)
            elif token == "IS":
                if self.source_profile != SOURCE_PROFILE_STANDARD_BUILD:
                    raise CompileStateError(
                        "compiled IS is disabled in the safe-runtime profile"
                    )
                self._emit_opcode(Op.DSET)
                self._emit_reference(
                    entry.xt + 4, TARGET_DICTIONARY, "defer-store-slot"
                )
            else:
                raise AssertionError(token)
        if self.code_here > start:
            self._code_source_words[start] = (self.code_here, f"{token} {name}")

    def _compile_token_unmapped(self, token: str) -> None:
        if token == "CREATE":
            self._compile_create()
            return
        if token == "DOES>":
            self._compile_does()
            return
        if self._definer_create_seen and self._definer_behavior_address is None:
            if token == ",":
                self._compile_constructor_action(CONSTRUCTOR_ACTION_COMMA)
                return
            if token == "C,":
                self._compile_constructor_action(CONSTRUCTOR_ACTION_C_COMMA)
                return
            if token == "ALLOT":
                self._compile_constructor_action(CONSTRUCTOR_ACTION_ALLOT)
                return
            if token == "ALIGN":
                self._compile_constructor_action(CONSTRUCTOR_ACTION_ALIGN)
                return
        if token in DATA_WORDS:
            raise CompileStateError(f"{token!r} is interpret-only in v0.1")
        if token == "IF":
            self._compile_if()
            return
        if token == "ELSE":
            self._compile_else()
            return
        if token == "THEN":
            self._compile_then()
            return
        if token == "BEGIN":
            self._compile_begin()
            return
        if token == "UNTIL":
            self._compile_until()
            return
        if token == "AGAIN":
            self._compile_again()
            return
        if token == "WHILE":
            self._compile_while()
            return
        if token == "REPEAT":
            self._compile_repeat()
            return
        if token == "DO":
            self._compile_do()
            return
        if token == "?DO":
            self._compile_do(conditional=True)
            return
        if token == "LOOP":
            self._compile_loop()
            return
        if token == "+LOOP":
            self._compile_loop(plus=True)
            return
        if token == "LEAVE":
            self._compile_leave()
            return
        number = parse_number(token)
        if number is not None:
            self._emit_opcode(Op.LIT)
            self._emit_cell(number)
            return
        entry = self.dictionary.find(token)
        if entry is None:
            raise UnknownWord(f"unknown word {token!r} while compiling")
        if entry.immediate:
            self.execute(entry)
        elif entry.kind == KIND_PRIMITIVE:
            self._emit_opcode(entry.payload)
        elif entry.kind == KIND_COLON:
            self._emit_opcode(Op.CALL)
            self._emit_reference(entry.payload, TARGET_CODE, "call")
        elif entry.kind == KIND_CONSTANT:
            self._emit_opcode(Op.LIT)
            self._emit_cell(entry.payload)
        elif entry.kind in (KIND_VARIABLE, KIND_CREATED):
            self._emit_opcode(Op.LIT)
            self._emit_reference(entry.payload, TARGET_DATA, "data-literal")
        elif entry.kind == KIND_DOES:
            body_address, code_address = self.dictionary.read_does_descriptor(entry)
            self._emit_opcode(Op.LIT)
            self._emit_reference(body_address, TARGET_DATA, "does-body")
            self._emit_opcode(Op.CALL)
            self._emit_reference(code_address, TARGET_CODE, "does-call")
        elif entry.kind == KIND_DEFER:
            self._emit_opcode(Op.ICALL)
            self._emit_reference(
                entry.xt + 4, TARGET_DICTIONARY, "defer-slot"
            )
        elif entry.kind == KIND_DEFINER:
            raise CompileStateError(
                f"defining word {token!r} is interpret-only in v0.1"
            )
        else:
            raise InvalidExecutionToken(f"unknown XT kind {entry.kind}")

    def _emit_opcode(self, opcode: Op | int) -> None:
        self._reserve_code(1)
        self.vm.write_u8(self.code_here, int(opcode))
        self.code_here += 1

    def _emit_cell(self, value: int) -> None:
        self._reserve_code(4)
        self.vm.write_cell(self.code_here, value)
        self.code_here += 4

    def _emit_reference(self, value: int, target: str, kind: str) -> None:
        patch_address = self.code_here
        self._emit_cell(value)
        self._relocation_records.append(
            RelocationRecord(
                section=SECTION_CODE,
                offset=patch_address - self.code_base,
                target=target,
                width=REFERENCE32_WIDTH,
                kind=kind,
            )
        )

    def _reserve_code(self, size: int) -> None:
        if self.code_here + size > self.code_limit:
            raise CompileStateError("compiled code region is full")

    def _compile_if(self) -> None:
        self._emit_opcode(Op.ZBRANCH)
        patch_address = self.code_here
        self._emit_reference(0, TARGET_CODE, "zbranch")
        self.control_stack.append(("IF", patch_address))

    def _compile_else(self) -> None:
        if not self.control_stack or self.control_stack[-1][0] != "IF":
            raise CompileStateError("ELSE requires an unmatched IF")
        _kind, if_patch = self.control_stack.pop()
        self._emit_opcode(Op.BRANCH)
        else_patch = self.code_here
        self._emit_reference(0, TARGET_CODE, "branch")
        self.vm.write_cell(if_patch, self.code_here)
        self.control_stack.append(("ELSE", else_patch))

    def _compile_then(self) -> None:
        if not self.control_stack or self.control_stack[-1][0] not in ("IF", "ELSE"):
            raise CompileStateError("THEN requires an unmatched IF or ELSE")
        _kind, patch_address = self.control_stack.pop()
        self.vm.write_cell(patch_address, self.code_here)

    def _compile_begin(self) -> None:
        self.control_stack.append(("BEGIN", self.code_here))

    def _compile_until(self) -> None:
        begin_address = self._pop_begin("UNTIL")
        self._emit_opcode(Op.ZBRANCH)
        self._emit_reference(begin_address, TARGET_CODE, "zbranch")

    def _compile_again(self) -> None:
        begin_address = self._pop_begin("AGAIN")
        self._emit_opcode(Op.BRANCH)
        self._emit_reference(begin_address, TARGET_CODE, "branch")

    def _compile_while(self) -> None:
        if not self.control_stack or self.control_stack[-1][0] != "BEGIN":
            raise CompileStateError("WHILE requires an unmatched BEGIN")
        self._emit_opcode(Op.ZBRANCH)
        patch_address = self.code_here
        self._emit_reference(0, TARGET_CODE, "zbranch")
        self.control_stack.append(("WHILE", patch_address))

    def _compile_repeat(self) -> None:
        if (
            len(self.control_stack) < 2
            or self.control_stack[-1][0] != "WHILE"
            or self.control_stack[-2][0] != "BEGIN"
        ):
            raise CompileStateError("REPEAT requires matching BEGIN and WHILE")
        _while_kind, while_patch = self.control_stack.pop()
        _begin_kind, begin_address = self.control_stack.pop()
        self._emit_opcode(Op.BRANCH)
        self._emit_reference(begin_address, TARGET_CODE, "branch")
        self.vm.write_cell(while_patch, self.code_here)

    def _pop_begin(self, word: str) -> int:
        if not self.control_stack or self.control_stack[-1][0] != "BEGIN":
            raise CompileStateError(f"{word} requires an unmatched BEGIN")
        _kind, begin_address = self.control_stack.pop()
        return begin_address

    def _compile_do(self, *, conditional: bool = False) -> None:
        exit_patches: list[int] = []
        if conditional:
            self._emit_opcode(Op.QDO)
            exit_patches.append(self.code_here)
            self._emit_reference(0, TARGET_CODE, "qdo")
        else:
            self._emit_opcode(Op.DO)
        self.control_stack.append(("DO", self.code_here, exit_patches))

    def _compile_loop(self, *, plus: bool = False) -> None:
        if not self.control_stack or self.control_stack[-1][0] != "DO":
            word = "+LOOP" if plus else "LOOP"
            raise CompileStateError(f"{word} requires an unmatched DO or ?DO")
        _kind, loop_address, exit_patches = self.control_stack.pop()
        self._emit_opcode(Op.PLOOP if plus else Op.LOOP)
        self._emit_reference(
            loop_address, TARGET_CODE, "ploop" if plus else "loop"
        )
        for patch_address in exit_patches:
            self.vm.write_cell(patch_address, self.code_here)

    def _compile_leave(self) -> None:
        for mark in reversed(self.control_stack):
            if mark[0] == "DO":
                self._emit_opcode(Op.LEAVE)
                patch_address = self.code_here
                self._emit_reference(0, TARGET_CODE, "leave")
                mark[2].append(patch_address)
                return
        raise CompileStateError("LEAVE requires an unmatched DO or ?DO")

    def _compile_create(self) -> None:
        if self.current_definition is None:
            raise CompileStateError("CREATE requires a current definition")
        if self._definer_create_seen:
            raise CompileStateError("only one CREATE is allowed in a defining word")
        if self.code_here != self.current_definition.payload or self.control_stack:
            raise CompileStateError(
                "v0.1 defining words require CREATE as the first body token"
            )
        self._definer_create_seen = True
        self._definer_segment_start = self.current_definition.payload

    def _compile_does(self) -> None:
        if not self._definer_create_seen:
            raise CompileStateError("DOES> requires an earlier CREATE")
        if self._definer_behavior_address is not None:
            raise CompileStateError("only one DOES> is allowed in a defining word")
        if self.control_stack:
            kind = self.control_stack[-1][0]
            raise CompileStateError(f"unresolved {kind!r} before 'DOES>'")
        self._finish_constructor_plan()
        self._definer_behavior_address = self.code_here

    def _compile_constructor_action(self, action: int) -> None:
        if self.control_stack:
            kind = self.control_stack[-1][0]
            raise CompileStateError(
                f"constructor action inside unresolved {kind!r} is not supported"
            )
        if self._definer_segment_start is None:
            raise CompileStateError("constructor plan has no active code segment")
        self._emit_opcode(Op.EXIT)
        self._definer_steps.append((self._definer_segment_start, action))
        self._definer_segment_start = self.code_here

    def _finish_constructor_plan(self) -> None:
        if self._definer_segment_start is None:
            raise CompileStateError("constructor plan has no active code segment")
        self._emit_opcode(Op.EXIT)
        self._definer_steps.append(
            (self._definer_segment_start, CONSTRUCTOR_ACTION_END)
        )
        self._definer_segment_start = None

    def execute(self, entry: DictionaryEntry) -> list[int]:
        data_before = list(self.vm.data_stack)
        return_depth = len(self.vm.return_stack)
        loop_depth = len(self.vm.loop_stack)
        try:
            self._trace(
                "word.execute.enter",
                word=entry.name,
                kind=entry.kind,
                depth=0,
                data_stack_before=data_before,
            )
            if entry.kind == KIND_PRIMITIVE:
                try:
                    address = self._primitive_dispatch[entry.payload]
                except KeyError as error:
                    raise InvalidExecutionToken(
                        f"primitive opcode 0x{entry.payload:02X} has no fixed dispatch entry"
                    ) from error
                return self.vm.resume(address)
            if entry.kind == KIND_COLON:
                return self.vm.resume(entry.payload, return_to=self.return_trampoline)
            if entry.kind in (KIND_CONSTANT, KIND_VARIABLE, KIND_CREATED):
                self.vm.push(entry.payload)
                return list(self.vm.data_stack)
            if entry.kind == KIND_DOES:
                body_address, code_address = self.dictionary.read_does_descriptor(entry)
                self._trace(
                    "does.execute.begin",
                    word=entry.name,
                    body=body_address,
                    behavior=code_address,
                )
                body_stack_before = list(self.vm.data_stack)
                self.vm.push(body_address)
                self._trace(
                    "does.body.push",
                    word=entry.name,
                    body=body_address,
                    behavior=code_address,
                    depth=1,
                    data_stack_before=body_stack_before,
                )

                def trace_behavior_step(
                    opcode_address: int, step_data_before: list[int]
                ) -> None:
                    source_word = self._code_source_words.get(opcode_address)
                    if source_word is None:
                        return
                    _code_end, token = source_word
                    self._trace(
                        "word.execute.nested.complete",
                        word=token,
                        parent=entry.name,
                        code_address=opcode_address,
                        depth=1,
                        data_stack_before=step_data_before,
                    )

                result = self.vm.resume(
                    code_address,
                    return_to=self.return_trampoline,
                    on_step=trace_behavior_step,
                )
                self._trace(
                    "does.execute.end",
                    word=entry.name,
                    body=body_address,
                    behavior=code_address,
                )
                return result
            if entry.kind == KIND_DEFER:
                target_xt = self.dictionary.read_defer_target(entry)
                if target_xt == 0:
                    raise UnassignedDefer(f"DEFER word {entry.name!r} is unassigned")
                target = self.dictionary.entry_for_xt(target_xt)
                return self.vm.resume(
                    target.payload, return_to=self.return_trampoline
                )
            if entry.kind == KIND_DEFINER:
                raise InvalidExecutionToken(
                    "a defining word requires a child name from the outer interpreter"
                )
            raise InvalidExecutionToken(f"unknown XT kind {entry.kind}")
        except Exception:
            self.vm.data_stack[:] = data_before
            del self.vm.return_stack[return_depth:]
            del self.vm.loop_stack[loop_depth:]
            raise

    def _interpret_defer_word(self, token: str, name: str) -> None:
        if token == "DEFER":
            self._validate_data_name(name)
            self.dictionary.add_defer(name)
            return
        entry = self.dictionary.find(name)
        if entry is None:
            raise UnknownWord(f"unknown word {name!r}")
        if token == "'":
            self.vm.push(entry.xt)
            return
        if token == "ACTION-OF":
            target_xt = self.dictionary.read_defer_target(entry)
            if target_xt == 0:
                raise UnassignedDefer(f"DEFER word {entry.name!r} is unassigned")
            self.vm.push(target_xt)
            return
        if token == "IS":
            target_xt = self._peek_data("IS")
            target = self.dictionary.entry_for_xt(target_xt)
            self.dictionary.set_defer(entry, target)
            self.vm.pop()
            return
        raise AssertionError(token)

    def _execute_definer(
        self, entry: DictionaryEntry, child_name: str
    ) -> list[int]:
        self._validate_data_name(child_name)
        _plan_address, behavior_address = (
            self.dictionary.read_definer_descriptor(entry)
        )
        constructor_steps = self.dictionary.read_constructor_plan(entry)
        saved_here = self.dictionary.here
        saved_data_here = self.dictionary.data_here
        saved_latest = self.dictionary.latest
        data_before = list(self.vm.data_stack)
        return_depth = len(self.vm.return_stack)
        loop_depth = len(self.vm.loop_stack)
        self._trace(
            "definer.execute.begin", word=entry.name, child=child_name
        )
        try:
            child = self.dictionary.add_created(child_name, hidden=True)
            self._trace(
                "child.create.hidden",
                word=entry.name,
                child=child.name,
                body=child.payload,
                header=child.header_address,
            )
            for code_address, action in constructor_steps:
                self._trace(
                    "constructor.segment.begin",
                    word=entry.name,
                    child=child.name,
                    code_address=code_address,
                    action=action,
                )
                self.vm.resume(code_address, return_to=self.return_trampoline)
                self._trace(
                    "constructor.segment.end",
                    word=entry.name,
                    child=child.name,
                    code_address=code_address,
                    action=action,
                )
                if action == CONSTRUCTOR_ACTION_COMMA:
                    value = self._peek_data(",")
                    address = self.dictionary.comma(value)
                    self.vm.pop()
                    self._trace(
                        "constructor.comma",
                        word=entry.name,
                        child=child.name,
                        address=address,
                        value=value,
                        data_here_after=self.dictionary.data_here,
                    )
                elif action == CONSTRUCTOR_ACTION_C_COMMA:
                    value = self._peek_data("C,")
                    address = self.dictionary.c_comma(value)
                    self.vm.pop()
                    self._trace(
                        "constructor.c_comma",
                        word=entry.name,
                        child=child.name,
                        address=address,
                        value=value & 0xFF,
                        data_here_after=self.dictionary.data_here,
                    )
                elif action == CONSTRUCTOR_ACTION_ALLOT:
                    count = signed(self._peek_data("ALLOT"))
                    address = self.dictionary.allot(count)
                    self.vm.pop()
                    self._trace(
                        "constructor.allot",
                        word=entry.name,
                        child=child.name,
                        address=address,
                        count=count,
                        data_here_after=self.dictionary.data_here,
                    )
                elif action == CONSTRUCTOR_ACTION_ALIGN:
                    address_before = self.dictionary.data_here
                    address_after = self.dictionary.align_here()
                    self._trace(
                        "constructor.align",
                        word=entry.name,
                        child=child.name,
                        address_before=address_before,
                        padding=address_after - address_before,
                        data_here_after=address_after,
                    )
                elif action != CONSTRUCTOR_ACTION_END:
                    raise InvalidExecutionToken(
                        f"unknown constructor action {action}"
                    )
            if behavior_address:
                child = self.dictionary.set_does(child, behavior_address)
                body_address, code_address = self.dictionary.read_does_descriptor(child)
                self._trace(
                    "child.does.attach",
                    word=entry.name,
                    child=child.name,
                    body=body_address,
                    behavior=code_address,
                    descriptor=child.payload,
                )
            child = self.dictionary.set_hidden(child, False)
            self._trace(
                "child.publish",
                word=entry.name,
                child=child.name,
                header=child.header_address,
                kind=child.kind,
            )
            self._trace(
                "definer.execute.end", word=entry.name, child=child.name
            )
            return list(self.vm.data_stack)
        except Exception as exc:
            self.vm.data_stack[:] = data_before
            del self.vm.return_stack[return_depth:]
            del self.vm.loop_stack[loop_depth:]
            self.dictionary.restore(
                here=saved_here,
                latest=saved_latest,
                data_here=saved_data_here,
            )
            self._trace(
                "definer.execute.rollback",
                word=entry.name,
                child=child_name,
                error=type(exc).__name__,
                saved_header_here=saved_here,
                saved_data_here=saved_data_here,
                saved_latest=saved_latest,
            )
            raise

    def _trace(self, event: str, **details: object) -> None:
        if self.trace is None:
            return
        try:
            emit = getattr(self.trace, "emit")
            emit(self.vm, self.dictionary, event, **details)
        except Exception as exc:
            self.trace_failures.append(f"{type(exc).__name__}: {exc}")

    def _trace_source_word(
        self,
        token: str,
        token_index: int,
        token_end: int,
        action: str,
        operands: list[str],
        data_stack_before: list[int],
        state_before: int,
        code_here_before: int,
    ) -> None:
        """Record one completed source operation without controlling execution."""

        self._trace(
            "source.word.complete",
            token=token,
            token_index=token_index,
            token_end=token_end,
            operands=operands,
            action=action,
            data_stack_before=data_stack_before,
            interpreter_state_before=(
                "compile" if state_before == STATE_COMPILE else "interpret"
            ),
            interpreter_state_after=(
                "compile" if self.state == STATE_COMPILE else "interpret"
            ),
            code_here_before=code_here_before,
            code_here_after=self.code_here,
            terminal_output=list(self.output),
        )

    def _trace_source_word_error(
        self,
        token: str,
        token_index: int,
        token_end: int,
        operands: list[str],
        data_stack_before: list[int],
        state_before: int,
        code_here_before: int,
        error: Exception,
    ) -> None:
        """Record a failed source operation after its rollback has completed."""

        self._trace(
            "source.word.error",
            token=token,
            token_index=token_index,
            token_end=token_end,
            operands=operands,
            action="execute-definer",
            error=type(error).__name__,
            data_stack_before=data_stack_before,
            interpreter_state_before=(
                "compile" if state_before == STATE_COMPILE else "interpret"
            ),
            interpreter_state_after=(
                "compile" if self.state == STATE_COMPILE else "interpret"
            ),
            code_here_before=code_here_before,
            code_here_after=self.code_here,
        )

    def _define_constant(self, name: str) -> None:
        self._validate_data_name(name)
        value = self._peek_data("CONSTANT")
        self.dictionary.add_constant(name, value)
        self.vm.pop()

    def _define_variable(self, name: str) -> None:
        self._validate_data_name(name)
        self.dictionary.add_variable(name)

    def _define_created(self, name: str) -> None:
        self._validate_data_name(name)
        self.dictionary.add_created(name)

    def _validate_data_name(self, name: str) -> None:
        if name in (":", ";") or name in DATA_WORDS:
            raise CompileStateError(f"invalid data definition name {name!r}")

    def _peek_data(self, word: str) -> int:
        if not self.vm.data_stack:
            raise StackUnderflow(f"data stack underflow in {word}")
        return self.vm.data_stack[-1]


def install_core_primitives(dictionary: RuntimeDictionary) -> None:
    """Install the v0.1 source primitive vocabulary in stable order."""

    for name, opcode in PRIMITIVES.items():
        dictionary.add_primitive(name, opcode)
