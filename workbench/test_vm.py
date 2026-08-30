import unittest

from demo import make_demo_program
from min0_core_forth_vm import (
    Assembler,
    FlatMemory,
    Min0CoreForthVM,
    InvalidOpcode,
    MemoryFault,
    MemoryRegion,
    Op,
    RegionMemory,
    StackUnderflow,
)


class RecordingMemory(FlatMemory):
    def __init__(self, size: int) -> None:
        super().__init__(size)
        self.fetches: list[tuple[int, int]] = []
        self.reads: list[tuple[int, int]] = []

    def fetch(self, address: int, size: int) -> bytes:
        self.fetches.append((address, size))
        return super().fetch(address, size)

    def fetch_u8(self, address: int) -> int:
        self.fetches.append((address, 1))
        return super().fetch_u8(address)

    def read(self, address: int, size: int) -> bytes:
        self.reads.append((address, size))
        return super().read(address, size)


def run_program(build) -> Min0CoreForthVM:
    asm = Assembler()
    build(asm)
    vm = Min0CoreForthVM()
    vm.load(asm.build())
    vm.run()
    return vm


class Min0CoreForthVMTests(unittest.TestCase):
    def test_square_and_double_words(self) -> None:
        vm = Min0CoreForthVM()
        vm.load(make_demo_program())
        self.assertEqual(vm.run(), [25, 14])
        self.assertEqual(vm.return_stack, [])

    def test_32_bit_cell_wraparound(self) -> None:
        def program(asm: Assembler) -> None:
            asm.emit(Op.LIT, 0xFFFFFFFF)
            asm.emit(Op.LIT, 1)
            asm.emit(Op.ADD)
            asm.emit(Op.HALT)

        self.assertEqual(run_program(program).data_stack, [0])

    def test_signed_less_and_forth_true(self) -> None:
        def program(asm: Assembler) -> None:
            asm.emit(Op.LIT, -1)
            asm.emit(Op.LIT, 0)
            asm.emit(Op.LESS)
            asm.emit(Op.HALT)

        self.assertEqual(run_program(program).data_stack, [0xFFFFFFFF])

    def test_store_and_fetch_are_little_endian_cells(self) -> None:
        data_address = 0x1000

        def program(asm: Assembler) -> None:
            asm.emit(Op.LIT, 0x12345678)
            asm.emit(Op.LIT, data_address)
            asm.emit(Op.STORE)
            asm.emit(Op.LIT, data_address)
            asm.emit(Op.FETCH)
            asm.emit(Op.HALT)

        vm = run_program(program)
        self.assertEqual(vm.data_stack, [0x12345678])
        self.assertEqual(vm.memory[data_address : data_address + 4], b"\x78\x56\x34\x12")

    def test_zero_branch(self) -> None:
        asm = Assembler()
        asm.emit(Op.LIT, 0)
        asm.emit(Op.ZBRANCH, "zero")
        asm.emit(Op.LIT, 99)
        asm.emit(Op.BRANCH, "done")
        asm.label("zero")
        asm.emit(Op.LIT, 42)
        asm.label("done")
        asm.emit(Op.HALT)
        vm = Min0CoreForthVM()
        vm.load(asm.build())
        self.assertEqual(vm.run(), [42])

    def test_data_stack_underflow_is_reported(self) -> None:
        vm = Min0CoreForthVM()
        vm.load(bytes([Op.DROP]))
        with self.assertRaises(StackUnderflow):
            vm.run()

    def test_invalid_opcode_is_reported(self) -> None:
        vm = Min0CoreForthVM()
        vm.load(b"\xFF")
        with self.assertRaises(InvalidOpcode):
            vm.run()

    def test_memory_fault_is_reported(self) -> None:
        vm = Min0CoreForthVM(memory_size=64)
        with self.assertRaises(MemoryFault):
            vm.write_cell(62, 1)

    def test_instruction_fetch_and_data_read_use_separate_bus_operations(self) -> None:
        data_address = 48
        bus = RecordingMemory(64)
        vm = Min0CoreForthVM(memory_size=64, memory_bus=bus)
        asm = Assembler()
        asm.emit(Op.LIT, data_address)
        asm.emit(Op.FETCH)
        asm.emit(Op.HALT)
        vm.load(asm.build())
        vm.write_cell(data_address, 0x12345678)

        self.assertEqual(vm.run(), [0x12345678])
        self.assertIn((1, 4), bus.fetches)
        self.assertEqual(bus.reads, [(data_address, 4)])

    def test_region_memory_enforces_code_data_and_boundary_permissions(self) -> None:
        bus = RegionMemory(
            80,
            [
                MemoryRegion("CODE", 0, 32, "rx", programmable=True),
                MemoryRegion("DATA", 32, 32, "rw"),
            ],
        )
        vm = Min0CoreForthVM(memory_size=80, memory_bus=bus)
        asm = Assembler()
        asm.emit(Op.LIT, 0x12345678)
        asm.emit(Op.LIT, 32)
        asm.emit(Op.STORE)
        asm.emit(Op.LIT, 32)
        asm.emit(Op.FETCH)
        asm.emit(Op.HALT)
        vm.load(asm.build())

        self.assertEqual(vm.run(), [0x12345678])
        self.assertEqual(bus.region_bytes("DATA")[:4], b"\x78\x56\x34\x12")
        with self.assertRaises(MemoryFault):
            bus.write_u8(0, 0)
        with self.assertRaises(MemoryFault):
            bus.fetch_u8(32)
        with self.assertRaises(MemoryFault):
            bus.read(30, 4)
        with self.assertRaises(MemoryFault):
            bus.read_u8(64)

    def test_read_only_seal_is_one_way_and_blocks_clear(self) -> None:
        data = MemoryRegion("DATA", 0, 16, "rw", programmable=True)
        bus = RegionMemory(16, [data])
        bus.write(0, b"AB")
        bus.seal_read_only_region("DATA")
        bus.seal_read_only_region("DATA")
        self.assertEqual(bus.read(0, 2), b"AB")
        self.assertEqual(data.permissions, "r")
        self.assertTrue(data.read_only_sealed)
        with self.assertRaises(MemoryFault):
            bus.write_u8(0, 0)
        with self.assertRaises(MemoryFault):
            bus.program(0, b"Z")
        with self.assertRaises(MemoryFault):
            bus.clear()


if __name__ == "__main__":
    unittest.main(verbosity=2)
