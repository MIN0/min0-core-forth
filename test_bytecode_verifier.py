import unittest

from bytecode_verifier_demo import run_demo


class BytecodeVerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = run_demo()

    def test_literal_byte_is_not_mistaken_for_an_opcode(self) -> None:
        self.assertEqual(self.result["literal_0x25_capabilities"], [])
        self.assertEqual(self.result["literal_instruction_count"], 2)

    def test_real_dset_derives_a_capability(self) -> None:
        self.assertEqual(
            self.result["dset_capabilities"], ["compiled-defer-store"]
        )
        self.assertEqual(self.result["dset_addresses"], [0x1000])

    def test_structural_and_typed_reference_failures_are_rejected(self) -> None:
        self.assertTrue(all(self.result["rejected"].values()))


if __name__ == "__main__":
    unittest.main(verbosity=2)
