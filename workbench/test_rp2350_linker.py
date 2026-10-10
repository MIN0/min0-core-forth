import unittest

from min0_rp2350_linker import NOP, bind_helper_symbols, link_literal_constants
from min0_rp2350_thumb_emitter import emit_thumb_fragment
from min0_virtual_assembler import compile_code
from min0_virtual_assembler_rp2350 import lower_rp2350


class Rp2350LinkerTests(unittest.TestCase):
    def test_literal_linker_resolves_32_bit_constant(self) -> None:
        definition = compile_code("""CODE: CONST ( -- value )
        LIT V0, 0x12345678
        OUT value, V0
        ;CODE""")
        fragment = emit_thumb_fragment(lower_rp2350(definition))
        relocation = next(item for item in fragment.relocations if item.opcode == "MOV_IMM32")
        linked = link_literal_constants(fragment)
        self.assertFalse(any(item.opcode == "MOV_IMM32" for item in linked.relocations))
        ldr = int.from_bytes(linked.code[relocation.offset:relocation.offset + 2], "little")
        self.assertEqual(ldr & 0xF800, 0x4800)
        self.assertEqual((ldr >> 8) & 7, 4)
        self.assertEqual(
            int.from_bytes(linked.code[relocation.offset + 2:relocation.offset + 4], "little"),
            NOP,
        )
        self.assertEqual(linked.code[-4:], bytes.fromhex("78563412"))

    def test_equal_literals_share_one_pool_cell(self) -> None:
        definition = compile_code("""CODE: TWO-CONSTS ( -- a b )
        LIT V0, 99
        LIT V1, 99
        OUT a, V0
        OUT b, V1
        ;CODE""")
        fragment = emit_thumb_fragment(lower_rp2350(definition))
        linked = link_literal_constants(fragment)
        self.assertEqual(len(linked.code) - ((len(fragment.code) + 3) & ~3), 4)
        self.assertEqual(linked.code[-4:], (99).to_bytes(4, "little"))

    def test_helper_actions_bind_to_private_abi_symbols(self) -> None:
        definition = compile_code("""CODE: LOAD ( address -- value )
        IN V1, address
        LD32 V0, [DATA: V1]
        OUT value, V0
        ;CODE""")
        fragment = emit_thumb_fragment(lower_rp2350(definition))
        bound = bind_helper_symbols(fragment)
        helpers = {
            item.opcode: item for item in bound.relocations
            if item.kind == "RP2350_HELPER_THUNK_CALL"
        }
        self.assertEqual(helpers["CHECKED_LD32"].symbol, "min0_checked_ld32")
        self.assertEqual(helpers["FRAME_COMMIT"].symbol, "min0_frame_commit")

    def test_linked_fragment_stays_non_executable_while_relocations_remain(self) -> None:
        definition = compile_code("""CODE: CONST ( -- value )
        LIT V0, 7
        OUT value, V0
        ;CODE""")
        linked = link_literal_constants(emit_thumb_fragment(lower_rp2350(definition)))
        self.assertGreater(len(linked.relocations), 0)
        self.assertFalse(linked.executable)


if __name__ == "__main__":
    unittest.main(verbosity=2)
