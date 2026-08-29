"""Minimal FORTH source-to-bytecode compiler for MIN0 CORE FORTH v0.1."""

from __future__ import annotations

from dataclasses import dataclass

from min0_core_forth_vm import Assembler, Op


class CompileError(ValueError):
    pass


PRIMITIVES: dict[str, Op] = {
    "NOP": Op.NOP,
    "@": Op.FETCH,
    "!": Op.STORE,
    "DROP": Op.DROP,
    "DUP": Op.DUP,
    "SWAP": Op.SWAP,
    "OVER": Op.OVER,
    "+": Op.ADD,
    "-": Op.SUB,
    "*": Op.MUL,
    "AND": Op.AND,
    "OR": Op.OR,
    "XOR": Op.XOR,
    "<": Op.LESS,
    "=": Op.EQUAL,
    "I": Op.I,
    "J": Op.J,
    "UNLOOP": Op.UNLOOP,
    "CELL+": Op.CELL_PLUS,
    "CELLS": Op.CELLS,
    "ALIGNED": Op.ALIGNED,
    "C@": Op.C_FETCH,
    "C!": Op.C_STORE,
    "CHAR+": Op.CHAR_PLUS,
    "CHARS": Op.CHARS,
}


@dataclass(frozen=True)
class Definition:
    name: str
    body: tuple[str, ...]


@dataclass(frozen=True)
class ParsedSource:
    definitions: tuple[Definition, ...]
    main: tuple[str, ...]


@dataclass(frozen=True)
class QuotedText:
    """One S-quote or dot-quote source item with case-preserved text."""

    word: str
    text: str


def tokenize(source: str) -> list[str | QuotedText]:
    """Tokenize words/comments while preserving S-quote and dot-quote text."""

    tokens: list[str | QuotedText] = []
    index = 0
    while index < len(source):
        character = source[index]
        if character.isspace():
            index += 1
            continue
        if character == "\\":
            while index < len(source) and source[index] not in "\r\n":
                index += 1
            continue

        introducer = source[index : index + 2].upper()
        if introducer in {'S"', '."'}:
            index += 2
            if index < len(source) and source[index] in " \t":
                index += 1
            start = index
            while index < len(source) and source[index] != '"':
                if source[index] in "\r\n":
                    raise CompileError(f"{introducer} string is missing closing quote")
                index += 1
            if index >= len(source):
                raise CompileError(f"{introducer} string is missing closing quote")
            tokens.append(QuotedText(introducer, source[start:index]))
            index += 1
            continue

        start = index
        while (
            index < len(source)
            and not source[index].isspace()
            and source[index] != "\\"
        ):
            index += 1
        tokens.append(source[start:index].upper())
    return tokens


def parse(source: str) -> ParsedSource:
    tokens = tokenize(source)
    definitions: list[Definition] = []
    main: list[str] = []
    names: set[str] = set()
    index = 0

    while index < len(tokens):
        token = tokens[index]
        if isinstance(token, QuotedText):
            raise CompileError(
                f"{token.word} is supported by the runtime outer interpreter, "
                "not the raw v0.1 compiler"
            )
        if token == ":":
            if index + 1 >= len(tokens):
                raise CompileError("':' requires a word name")
            name = tokens[index + 1]
            if not isinstance(name, str):
                raise CompileError("':' requires an ordinary unquoted word name")
            if name in (":", ";"):
                raise CompileError(f"invalid word name {name!r}")
            if name in PRIMITIVES:
                raise CompileError(f"cannot redefine primitive {name!r} in v0.1")
            if name in names:
                raise CompileError(f"duplicate definition {name!r}")
            index += 2
            body: list[str] = []
            while index < len(tokens) and tokens[index] != ";":
                if isinstance(tokens[index], QuotedText):
                    quoted = tokens[index]
                    raise CompileError(
                        f"{quoted.word} is supported by the runtime outer "
                        "interpreter, not the raw v0.1 compiler"
                    )
                if tokens[index] == ":":
                    raise CompileError("nested ':' definition is not allowed")
                body.append(tokens[index])
                index += 1
            if index >= len(tokens):
                raise CompileError(f"definition {name!r} is missing ';'")
            definitions.append(Definition(name, tuple(body)))
            names.add(name)
            index += 1
            continue
        if token == ";":
            raise CompileError("';' outside a definition")
        main.append(token)
        index += 1

    return ParsedSource(tuple(definitions), tuple(main))


def parse_number(token: str) -> int | None:
    try:
        if token.startswith(("-0X", "+0X")):
            sign = -1 if token[0] == "-" else 1
            return sign * int(token[3:], 16)
        return int(token, 0)
    except ValueError:
        return None


def compile_source(source: str) -> bytes:
    """Compile source into one raw image loaded and entered at address zero."""

    parsed = parse(source)
    user_words = {definition.name for definition in parsed.definitions}
    assembler = Assembler()

    _compile_tokens(assembler, parsed.main, user_words, context="main")
    assembler.emit(Op.HALT)

    for definition in parsed.definitions:
        assembler.label(_word_label(definition.name))
        _compile_tokens(assembler, definition.body, user_words, context=definition.name)
        assembler.emit(Op.EXIT)

    return assembler.build()


def _compile_tokens(
    assembler: Assembler,
    tokens: tuple[str, ...],
    user_words: set[str],
    *,
    context: str,
) -> None:
    for token in tokens:
        number = parse_number(token)
        if number is not None:
            assembler.emit(Op.LIT, number)
        elif token in PRIMITIVES:
            assembler.emit(PRIMITIVES[token])
        elif token in user_words:
            assembler.emit(Op.CALL, _word_label(token))
        else:
            raise CompileError(f"unknown word {token!r} in {context!r}")


def _word_label(name: str) -> str:
    return f"word:{name}"
