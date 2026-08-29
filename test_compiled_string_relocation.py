import unittest

from compiled_string_relocation_demo import run_demo


class CompiledStringRelocationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = run_demo()

    def test_string_address_is_typed_and_relocated(self) -> None:
        self.assertEqual(self.result["relocation"]["target"], "data")
        self.assertEqual(self.result["relocation"]["kind"], "string-address")
        self.assertEqual(self.result["address"], self.result["moved_data_base"])
        self.assertNotEqual(self.result["address"], self.result["source_data_base"])

    def test_relocated_string_executes_from_read_only_data(self) -> None:
        self.assertEqual(self.result["length"], 9)
        self.assertEqual(self.result["text_hex"], b"Relocated".hex())
        self.assertEqual(self.result["terminal_text"], "Relocated")
        self.assertEqual(self.result["data_permissions"], "r")
        self.assertTrue(self.result["read_only_sealed"])
        self.assertTrue(all(self.result["rejected"].values()))


if __name__ == "__main__":
    unittest.main(verbosity=2)
