"""User-facing host launcher for MIN0 CORE FORTH."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from min0_core_forth_dictionary import RuntimeDictionary
from min0_core_forth_outer import OuterInterpreter, install_core_primitives
from min0_core_forth_vm import Min0CoreForthVM


ROOT = Path(__file__).resolve().parent
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
BANNER = f"MIN0 CORE FORTH {VERSION} - educational and experimental reference"


def make_host() -> OuterInterpreter:
    vm = Min0CoreForthVM()
    dictionary = RuntimeDictionary(vm)
    install_core_primitives(dictionary)
    return OuterInterpreter(vm, dictionary)


def execute_source(outer: OuterInterpreter, source: str) -> None:
    outer.interpret(source)


def _write_new_output(outer: OuterInterpreter, start: int) -> int:
    fragments = outer.output[start:]
    if fragments:
        sys.stdout.write("".join(fragments))
        sys.stdout.flush()
    return len(outer.output)


def run_file(path: Path, *, quiet: bool) -> int:
    outer = make_host()
    try:
        source = path.read_text(encoding="utf-8")
        execute_source(outer, source)
    except Exception as exc:
        print(f"ERROR {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    if not quiet:
        print(BANNER)
    _write_new_output(outer, 0)
    if not quiet:
        if outer.output and not outer.terminal_text.endswith("\n"):
            print()
        print(f"DATA stack: {outer.vm.data_stack}")
    return 0


def repl() -> int:
    outer = make_host()
    output_index = 0
    print(BANNER)
    print("Type BYE or EXIT to leave. Output bytes are emitted by the program.")
    while True:
        try:
            source = input("ok> ")
        except EOFError:
            print()
            return 0
        if source.strip().upper() in {"BYE", "EXIT"}:
            return 0
        try:
            execute_source(outer, source)
            output_index = _write_new_output(outer, output_index)
            if outer.output and not outer.terminal_text.endswith("\n"):
                print()
            print(f" ok {outer.vm.data_stack}")
        except Exception as exc:
            print(f"ERROR {type(exc).__name__}: {exc}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the MIN0 CORE FORTH Python host reference"
    )
    parser.add_argument("source", nargs="?", type=Path, help="FORTH source file")
    parser.add_argument(
        "-z", "--quiet-source", metavar="FILE", type=Path,
        help="run FILE without banner, prompt, or final stack",
    )
    parser.add_argument("--version", action="store_true")
    args = parser.parse_args(argv)
    if args.version:
        print(VERSION)
        return 0
    if args.source is not None and args.quiet_source is not None:
        parser.error("source and -z cannot be used together")
    if args.quiet_source is not None:
        return run_file(args.quiet_source, quiet=True)
    if args.source is not None:
        return run_file(args.source, quiet=False)
    return repl()


if __name__ == "__main__":
    raise SystemExit(main())
