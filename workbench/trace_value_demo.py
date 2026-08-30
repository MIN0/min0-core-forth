"""Build or emit the actual semantic trace used by the Guided Viewer."""

import json

from min0_core_forth_dictionary import RuntimeDictionary
from min0_core_forth_outer import OuterInterpreter, install_core_primitives
from min0_core_forth_trace import TraceRecorder
from min0_core_forth_vm import Min0CoreForthVM, MemoryRegion, RegionMemory


VALUE_SOURCE = ": VALUE: CREATE , DOES> @ ;\n123 VALUE: ANSWER\nANSWER"
ROLLBACK_SOURCE = ": VALUE: CREATE , DOES> @ ;\nVALUE: EMPTY"
RECORD_SOURCE = ": RECORD: CREATE C, ALLOT ALIGN ;\n2 0x1AB RECORD: ITEM\nITEM"
STACK_LATE_SOURCE = "2 3 4 * + ."
STACK_EARLY_SOURCE = "2 3 * 4 + ."
COMPILED_OUTPUT_SOURCE = ': GREET ." Hello from compiled Forth" ;\nGREET'


def _make_traced_system(
    implementation: str, *, include_source_words: bool
) -> tuple[TraceRecorder, OuterInterpreter]:
    bus = RegionMemory(
        0x10000,
        [
            MemoryRegion("CODE", 0, 0x4000, "rwx", programmable=True),
            MemoryRegion("DICTIONARY", 0x4000, 0x4000, "rw"),
            MemoryRegion("DATA", 0x8000, 0x8000, "rw"),
        ],
    )
    vm = Min0CoreForthVM(memory_bus=bus)
    dictionary = RuntimeDictionary(
        vm, base=0x4000, limit=0x8000, body_base=0x8000, body_limit=0x10000
    )
    install_core_primitives(dictionary)
    trace = TraceRecorder(
        implementation, include_source_words=include_source_words
    )
    return trace, OuterInterpreter(vm, dictionary, trace=trace)


def build_trace_document(
    implementation: str = "python", *, include_source_words: bool = False
) -> dict:
    """Execute VALUE_SOURCE and return its measured semantic trace."""

    trace, outer = _make_traced_system(
        implementation, include_source_words=include_source_words
    )
    outer.interpret(VALUE_SOURCE)
    return trace.document()


def build_stack_trace_document(
    source: str, implementation: str = "python", *, include_source_words: bool = True
) -> dict:
    """Execute one beginner stack example and return its measured trace and output."""

    trace, outer = _make_traced_system(
        implementation, include_source_words=include_source_words
    )
    outer.interpret(source)
    document = trace.document()
    document["terminal_output"] = list(outer.output)
    return document


def build_rollback_trace_document(
    implementation: str = "python", *, include_source_words: bool = False
) -> dict:
    """Execute the failing VALUE: example and return its post-rollback trace."""

    trace, outer = _make_traced_system(
        implementation, include_source_words=include_source_words
    )
    try:
        outer.interpret(ROLLBACK_SOURCE)
    except Exception as exc:
        document = trace.document()
        document["outcome"] = {
            "status": "rolled-back",
            "error": type(exc).__name__,
        }
        return document
    raise AssertionError("ROLLBACK_SOURCE unexpectedly completed")


def build_record_trace_document(
    implementation: str = "python", *, include_source_words: bool = False
) -> dict:
    """Execute RECORD_SOURCE and return its measured allocator trace."""

    trace, outer = _make_traced_system(
        implementation, include_source_words=include_source_words
    )
    outer.interpret(RECORD_SOURCE)
    return trace.document()


if __name__ == "__main__":
    print(json.dumps(build_trace_document(), ensure_ascii=True, sort_keys=True))
