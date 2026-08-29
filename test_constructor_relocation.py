import unittest

from constructor_relocation_demo import run_demo


class ConstructorRelocationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = run_demo()

    def test_all_three_logical_regions_move(self) -> None:
        self.assertEqual(self.result["source_bases"], [0x1000, 0x4000, 0x8000])
        self.assertEqual(self.result["moved_bases"], [0x2000, 0x5000, 0x9000])
        self.assertEqual(self.result["deltas"], [0x1000, 0x1000, 0x1000])

    def test_typed_dictionary_manifest_is_deterministic(self) -> None:
        self.assertEqual(self.result["relocation_count"], 31)
        self.assertEqual(
            self.result["target_counts"],
            {"code": 4, "dictionary": 27, "data": 0},
        )
        self.assertEqual(
            self.result["manifest_sha256"],
            "bffe20da07aaba7b392fb6a299eafe3e5723a204dba547e43902151fe318a452",
        )

    def test_relocated_record_constructor_executes(self) -> None:
        self.assertEqual(self.result["actions"], [2, 3, 4, 0])
        self.assertEqual(self.result["stack"], [0x9000])
        self.assertEqual(self.result["item_body"], 0x9000)
        self.assertEqual(self.result["body_hex"], "ab000000")
        self.assertEqual(self.result["data_here"], 0x9004)


if __name__ == "__main__":
    unittest.main(verbosity=2)
