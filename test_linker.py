import unittest

from full_image_relocation_demo import run_demo as run_full_image_demo
from linker_validation_demo import run_demo as run_validation_demo


class LinkerTests(unittest.TestCase):
    def test_successful_link_returns_patched_copies(self) -> None:
        result = run_validation_demo()
        self.assertTrue(result["source_unchanged"])
        self.assertEqual(result["record_count"], 3)
        self.assertEqual(result["code_hex"], "0440000000600000efbeadde")
        self.assertEqual(result["dictionary_hex"], "00400000")
        self.assertEqual(result["data_hex"], "44332211")

    def test_all_corruptions_are_rejected_transactionally(self) -> None:
        result = run_validation_demo()
        self.assertEqual(
            result["rejected"],
            [
                "version",
                "section",
                "width",
                "offset",
                "overlap",
                "pointer",
                "target-overlap",
                "overflow",
                "kind",
            ],
        )

    def test_real_image_uses_one_unified_manifest(self) -> None:
        result = run_full_image_demo()
        self.assertEqual(result["manifest_records"], 68)
        self.assertEqual(result["code_relocations"], 15)
        self.assertEqual(result["dictionary_relocations"], 53)
        self.assertEqual(result["stack"], [99, 2, 3, 3, 0, 2, 7, 0x9000])


if __name__ == "__main__":
    unittest.main(verbosity=2)
