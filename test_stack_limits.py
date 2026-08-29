import unittest

from min0_core_forth_vm import (
    DEFAULT_DATA_STACK_DEPTH,
    DEFAULT_LOOP_STACK_DEPTH,
    DEFAULT_RETURN_STACK_DEPTH,
    MINIMUM_CONFORMING_LOOP_DEPTH,
    Assembler,
    DataStackOverflow,
    Min0CoreForthVM,
    LoopStackOverflow,
    LoopStackUnderflow,
    Op,
    ReturnStackOverflow,
    StackUnderflow,
)


class StackLimitTests(unittest.TestCase):
    def test_reference_defaults(self) -> None:
        vm = Min0CoreForthVM()
        self.assertEqual(vm.max_data_depth, DEFAULT_DATA_STACK_DEPTH)
        self.assertEqual(vm.max_return_depth, DEFAULT_RETURN_STACK_DEPTH)
        self.assertEqual(vm.max_loop_depth, DEFAULT_LOOP_STACK_DEPTH)
        self.assertEqual(MINIMUM_CONFORMING_LOOP_DEPTH, 8)

    def test_data_stack_overflow(self) -> None:
        vm = Min0CoreForthVM(max_data_depth=2)
        vm.push(1)
        vm.push(2)
        with self.assertRaises(DataStackOverflow):
            vm.push(3)
        self.assertEqual(vm.data_stack, [1, 2])

    def test_return_stack_overflow(self) -> None:
        asm = Assembler()
        asm.emit(Op.CALL, "FIRST")
        asm.emit(Op.HALT)
        asm.label("FIRST")
        asm.emit(Op.CALL, "SECOND")
        asm.emit(Op.EXIT)
        asm.label("SECOND")
        asm.emit(Op.EXIT)
        vm = Min0CoreForthVM(max_return_depth=1)
        vm.load(asm.build())
        with self.assertRaises(ReturnStackOverflow):
            vm.run()

    def test_loop_stack_overflow(self) -> None:
        asm = Assembler()
        for _ in range(2):
            asm.emit(Op.LIT, 2)
            asm.emit(Op.LIT, 0)
            asm.emit(Op.DO)
        asm.emit(Op.HALT)
        vm = Min0CoreForthVM(max_loop_depth=1)
        vm.load(asm.build())
        with self.assertRaises(LoopStackOverflow):
            vm.run()
        self.assertEqual(vm.data_stack, [2, 0])
        self.assertEqual(len(vm.loop_stack), 1)

    def test_question_do_zero_trip_needs_no_free_loop_frame(self) -> None:
        asm = Assembler()
        asm.emit(Op.LIT, 2)
        asm.emit(Op.LIT, 0)
        asm.emit(Op.DO)
        asm.emit(Op.LIT, 0)
        asm.emit(Op.LIT, 0)
        asm.emit(Op.QDO, "done")
        asm.label("done")
        asm.emit(Op.HALT)
        vm = Min0CoreForthVM(max_loop_depth=1)
        vm.load(asm.build())
        self.assertEqual(vm.run(), [])
        self.assertEqual(len(vm.loop_stack), 1)

    def test_extended_loop_underflows_do_not_remove_available_state(self) -> None:
        asm = Assembler()
        asm.emit(Op.LIT, 1)
        asm.emit(Op.PLOOP, 0)
        vm = Min0CoreForthVM()
        vm.load(asm.build())
        with self.assertRaises(LoopStackUnderflow):
            vm.run()
        self.assertEqual(vm.data_stack, [1])

        asm = Assembler()
        asm.emit(Op.LIT, 2)
        asm.emit(Op.LIT, 0)
        asm.emit(Op.DO)
        asm.emit(Op.PLOOP, 0)
        vm = Min0CoreForthVM()
        vm.load(asm.build())
        with self.assertRaises(StackUnderflow):
            vm.run()
        self.assertEqual(len(vm.loop_stack), 1)

        for op in (Op.J, Op.LEAVE):
            with self.subTest(op=op):
                asm = Assembler()
                if op is Op.LEAVE:
                    asm.emit(op, 0)
                else:
                    asm.emit(op)
                vm = Min0CoreForthVM()
                vm.load(asm.build())
                with self.assertRaises(LoopStackUnderflow):
                    vm.run()

    def test_binary_underflow_preserves_existing_operand(self) -> None:
        asm = Assembler()
        asm.emit(Op.LIT, 7)
        asm.emit(Op.ADD)
        vm = Min0CoreForthVM()
        vm.load(asm.build())
        with self.assertRaises(StackUnderflow):
            vm.run()
        self.assertEqual(vm.data_stack, [7])

    def test_loop_stack_underflow(self) -> None:
        for program in (
            bytes([Op.I, Op.HALT]),
            bytes([Op.UNLOOP, Op.HALT]),
        ):
            with self.subTest(program=program.hex()):
                vm = Min0CoreForthVM()
                vm.load(program)
                with self.assertRaises(LoopStackUnderflow):
                    vm.run()

        asm = Assembler()
        asm.emit(Op.LOOP, 0)
        vm = Min0CoreForthVM()
        vm.load(asm.build())
        with self.assertRaises(LoopStackUnderflow):
            vm.run()

    def test_reset_clears_every_stack(self) -> None:
        vm = Min0CoreForthVM()
        vm.push(1)
        vm.return_stack.append(2)
        vm.loop_stack.append(object())  # reset must not depend on frame contents
        vm.reset()
        self.assertEqual(vm.data_stack, [])
        self.assertEqual(vm.return_stack, [])
        self.assertEqual(vm.loop_stack, [])

    def test_nonpositive_depth_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Min0CoreForthVM(max_loop_depth=0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
