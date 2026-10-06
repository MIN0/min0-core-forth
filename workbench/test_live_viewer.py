import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "run_live_viewer", ROOT / "tools" / "run_live_viewer.py"
)
assert SPEC is not None and SPEC.loader is not None
LIVE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LIVE)


class LiveViewerTests(unittest.TestCase):
    def test_executes_fresh_vm_and_returns_word_stacks(self) -> None:
        result = LIVE.execute_for_viewer(": SQUARE DUP * ; 5 SQUARE .")
        self.assertTrue(result["ok"])
        self.assertEqual(result["terminal"], "25")
        self.assertEqual(result["data_stack"], [])
        square = next(word for word in result["words"] if word["token"] == "SQUARE")
        self.assertEqual(square["data_before"], [5])
        self.assertEqual(square["data_after"], [25])

    def test_error_is_data_and_does_not_escape(self) -> None:
        result = LIVE.execute_for_viewer("<script> 1")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["name"], "UnknownWord")
        html = (ROOT / "viewer" / "live-viewer.html").read_text(encoding="utf-8")
        self.assertNotIn("innerHTML", html)
        self.assertIn("textContent", html)
        self.assertIn("location.protocol === 'file:'", html)
        self.assertIn("HTMLは直接開かず", html)

    def test_rejects_oversized_source(self) -> None:
        with self.assertRaises(ValueError):
            LIVE.execute_for_viewer("X" * (LIVE.MAX_SOURCE_BYTES + 1))


if __name__ == "__main__":
    unittest.main(verbosity=2)
