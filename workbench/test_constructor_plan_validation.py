import unittest

from min0_core_forth_dictionary import (
    CONSTRUCTOR_ACTION_ALIGN,
    CONSTRUCTOR_ACTION_END,
    CONSTRUCTOR_PLAN_MAGIC,
    CONSTRUCTOR_PLAN_VERSION,
    InvalidDictionary,
)
from test_source_does import make_split_system
from min0_core_forth_vm import InvalidOpcode


class ConstructorPlanValidationTests(unittest.TestCase):
    def make_record_plan(self):
        vm, dictionary, outer = make_split_system()
        outer.interpret(": RECORD: CREATE C, ALLOT ALIGN ;")
        entry = dictionary.find("RECORD:")
        assert entry is not None
        descriptor = entry.payload
        plan = vm.read_cell(descriptor)
        count = vm.read_cell(plan + 8)
        return vm, dictionary, outer, entry, descriptor, plan, count

    def test_versioned_header_is_dictionary_resident(self) -> None:
        vm, dictionary, _outer, entry, descriptor, plan, count = (
            self.make_record_plan()
        )

        self.assertEqual(vm.read_cell(plan), CONSTRUCTOR_PLAN_MAGIC)
        self.assertEqual(vm.read_cell(plan + 4), CONSTRUCTOR_PLAN_VERSION)
        self.assertEqual(count, 4)
        self.assertLess(plan + 12 + count * 8, descriptor + 1)
        self.assertEqual(len(dictionary.read_constructor_plan(entry)), count)

    def test_rejects_bad_magic_and_unknown_version(self) -> None:
        for offset, value, message in (
            (0, 0, "magic"),
            (4, CONSTRUCTOR_PLAN_VERSION + 1, "version"),
        ):
            with self.subTest(message=message):
                vm, dictionary, _outer, entry, _descriptor, plan, _count = (
                    self.make_record_plan()
                )
                vm.write_cell(plan + offset, value)
                with self.assertRaisesRegex(InvalidDictionary, message):
                    dictionary.read_constructor_plan(entry)

    def test_rejects_zero_and_overlapping_length(self) -> None:
        for count in (0, 0xFFFFFFFF):
            with self.subTest(count=count):
                vm, dictionary, _outer, entry, _descriptor, plan, _old_count = (
                    self.make_record_plan()
                )
                vm.write_cell(plan + 8, count)
                with self.assertRaisesRegex(InvalidDictionary, "length"):
                    dictionary.read_constructor_plan(entry)

    def test_rejects_unknown_missing_and_early_end_actions(self) -> None:
        corruptions = (
            (0, 99, "unknown constructor action"),
            (0, CONSTRUCTOR_ACTION_END, "END must be the final"),
            (-1, CONSTRUCTOR_ACTION_ALIGN, "END must be the final"),
        )
        for step_index, action, message in corruptions:
            with self.subTest(step_index=step_index, action=action):
                vm, dictionary, _outer, entry, _descriptor, plan, count = (
                    self.make_record_plan()
                )
                index = count - 1 if step_index < 0 else step_index
                vm.write_cell(plan + 12 + index * 8 + 4, action)
                with self.assertRaisesRegex(InvalidDictionary, message):
                    dictionary.read_constructor_plan(entry)

    def test_rejects_plan_region_and_code_region_violations(self) -> None:
        vm, dictionary, _outer, entry, descriptor, _plan, _count = (
            self.make_record_plan()
        )
        vm.write_cell(descriptor, descriptor - 4)
        with self.assertRaisesRegex(InvalidDictionary, "plan address"):
            dictionary.read_constructor_plan(entry)

        vm, dictionary, _outer, entry, _descriptor, plan, _count = (
            self.make_record_plan()
        )
        vm.write_cell(plan + 12, 0x4000)
        with self.assertRaisesRegex(InvalidDictionary, "not executable"):
            dictionary.read_constructor_plan(entry)

    def test_rejects_unaligned_definer_descriptor(self) -> None:
        vm, dictionary, _outer, entry, descriptor, _plan, _count = (
            self.make_record_plan()
        )
        vm.write_cell(entry.xt + 4, descriptor + 1)
        with self.assertRaisesRegex(InvalidDictionary, "descriptor address"):
            dictionary.read_constructor_plan(entry)

    def test_set_definer_rejects_invalid_input_without_mutation(self) -> None:
        vm, dictionary, outer = make_split_system()
        outer.interpret(": CANDIDATE 1 ;")
        entry = dictionary.find("CANDIDATE")
        assert entry is not None
        code = entry.payload
        saved = (
            dictionary.here,
            dictionary.data_here,
            dictionary.latest,
            vm.read_bytes(dictionary.base, dictionary.here - dictionary.base),
        )
        invalid_plans = (
            [],
            [(code, 99)],
            [(code, CONSTRUCTOR_ACTION_ALIGN)],
            [(code, CONSTRUCTOR_ACTION_END), (code, CONSTRUCTOR_ACTION_END)],
            [(0x4000, CONSTRUCTOR_ACTION_END)],
            [(0x10000, CONSTRUCTOR_ACTION_END)],
        )
        for steps in invalid_plans:
            with self.subTest(steps=steps):
                with self.assertRaises(Exception):
                    dictionary.set_definer(entry, steps)
                self.assertEqual(
                    (
                        dictionary.here,
                        dictionary.data_here,
                        dictionary.latest,
                        vm.read_bytes(
                            dictionary.base, dictionary.here - dictionary.base
                        ),
                    ),
                    saved,
                )

    def test_corrupt_plan_cannot_create_or_publish_a_child(self) -> None:
        vm, dictionary, outer, _entry, _descriptor, plan, _count = (
            self.make_record_plan()
        )
        outer.interpret("2 0x1AB")
        saved = (dictionary.here, dictionary.data_here, dictionary.latest)
        vm.write_cell(plan + 4, CONSTRUCTOR_PLAN_VERSION + 1)

        with self.assertRaisesRegex(InvalidDictionary, "version"):
            outer.interpret("RECORD: BAD")

        self.assertEqual(vm.data_stack, [2, 0x1AB])
        self.assertEqual(
            (dictionary.here, dictionary.data_here, dictionary.latest), saved
        )
        self.assertIsNone(dictionary.find("BAD", include_hidden=True))

    def test_segment_failure_rolls_back_hidden_child_and_stacks(self) -> None:
        vm, dictionary, outer, _entry, _descriptor, plan, _count = (
            self.make_record_plan()
        )
        outer.interpret("2 0x1AB")
        saved = (dictionary.here, dictionary.data_here, dictionary.latest)
        first_code = vm.read_cell(plan + 12)
        vm.write_u8(first_code, 0xFF)

        with self.assertRaises(InvalidOpcode):
            outer.interpret("RECORD: BAD")

        self.assertEqual(vm.data_stack, [2, 0x1AB])
        self.assertEqual(vm.return_stack, [])
        self.assertEqual(vm.loop_stack, [])
        self.assertEqual(
            (dictionary.here, dictionary.data_here, dictionary.latest), saved
        )
        self.assertIsNone(dictionary.find("BAD", include_hidden=True))


if __name__ == "__main__":
    unittest.main(verbosity=2)
