import unittest

from min0_core_forth_dictionary import RuntimeDictionary
from min0_core_forth_outer import OuterInterpreter, install_core_primitives
from min0_core_forth_trace import PAYLOAD_ROLE, TRACE_FORMAT, TraceRecorder
from min0_core_forth_vm import Min0CoreForthVM, MemoryRegion, RegionMemory, StackUnderflow


def make_traced_system(trace=None):
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
    return vm, dictionary, OuterInterpreter(vm, dictionary, trace=trace)


class TraceTests(unittest.TestCase):
    def test_value_trace_contains_semantic_boundaries_and_snapshots(self) -> None:
        trace = TraceRecorder("python")
        vm, dictionary, outer = make_traced_system(trace)
        self.assertEqual(
            outer.interpret(": VALUE: CREATE , DOES> @ ; 123 VALUE: ANSWER ANSWER"),
            [123],
        )
        expected = [
            "definer.compile.complete",
            "definer.execute.begin",
            "child.create.hidden",
            "constructor.segment.begin",
            "constructor.segment.end",
            "constructor.comma",
            "constructor.segment.begin",
            "constructor.segment.end",
            "child.does.attach",
            "child.publish",
            "definer.execute.end",
            "does.execute.begin",
            "does.execute.end",
        ]
        self.assertEqual([event["event"] for event in trace.events], expected)
        comma = trace.events[5]
        self.assertEqual(comma["details"]["address"], 0x8000)
        self.assertEqual(comma["details"]["value"], 123)
        self.assertEqual(comma["state"]["data_here"], 0x8004)
        self.assertEqual(comma["state"]["data_stack"], [])
        self.assertEqual(comma["payload_role"], PAYLOAD_ROLE)
        self.assertIn("0x00008000", comma["basic_explanation"])
        self.assertEqual(trace.document()["trace_format"], TRACE_FORMAT)
        self.assertEqual(vm.read_cell(0x8000), 123)
        self.assertEqual(dictionary.data_here, 0x8004)

    def test_rollback_event_is_recorded_after_state_restoration(self) -> None:
        trace = TraceRecorder("python")
        vm, dictionary, outer = make_traced_system(trace)
        outer.interpret(": VALUE: CREATE , DOES> @ ;")
        trace.events.clear()
        saved = (dictionary.here, dictionary.data_here, dictionary.latest)

        with self.assertRaises(StackUnderflow):
            outer.interpret("VALUE: EMPTY")

        rollback = trace.events[-1]
        self.assertEqual(rollback["event"], "definer.execute.rollback")
        self.assertEqual(rollback["details"]["error"], "StackUnderflow")
        self.assertEqual(rollback["details"]["saved_header_here"], saved[0])
        self.assertEqual(rollback["details"]["saved_data_here"], saved[1])
        self.assertEqual(rollback["details"]["saved_latest"], saved[2])
        self.assertEqual(
            (
                rollback["state"]["header_here"],
                rollback["state"]["data_here"],
                rollback["state"]["latest"],
            ),
            saved,
        )
        self.assertEqual(vm.data_stack, [])
        self.assertIsNone(dictionary.find("EMPTY", include_hidden=True))

    def test_broken_observer_never_changes_forth_execution(self) -> None:
        class BrokenObserver:
            def emit(self, *_args, **_kwargs):
                raise RuntimeError("observer failed")

        vm, dictionary, outer = make_traced_system(BrokenObserver())
        stack = outer.interpret(": VALUE: CREATE , DOES> @ ; 123 VALUE: ANSWER ANSWER")
        answer = dictionary.find("ANSWER")
        assert answer is not None

        self.assertEqual(stack, [123])
        self.assertEqual(vm.read_cell(0x8000), 123)
        self.assertGreater(len(outer.trace_failures), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
