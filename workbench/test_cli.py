import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent


class HostCliTests(unittest.TestCase):
    def _source(self, directory: str, text: str) -> Path:
        path = Path(directory) / "program.fth"
        path.write_text(text, encoding="utf-8", newline="\n")
        return path

    def test_python_quiet_mode_emits_only_program_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = self._source(directory, ': GREET ." Hello" ; GREET')
            result = subprocess.run(
                [sys.executable, str(ROOT / "min0_forth.py"), "-z", str(source)],
                text=True, capture_output=True, check=False, encoding="utf-8",
            )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "Hello")
        self.assertEqual(result.stderr, "")

    def test_ruby_quiet_mode_matches_python_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = self._source(directory, ': GREET ." Hello" ; GREET')
            result = subprocess.run(
                ["ruby", str(ROOT / "min0_forth.rb"), "-z", str(source)],
                text=True, capture_output=True, check=False, encoding="utf-8",
            )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "Hello")
        self.assertEqual(result.stderr, "")

    def test_normal_mode_identifies_release_and_stack(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = self._source(directory, "2 3 +")
            result = subprocess.run(
                [sys.executable, str(ROOT / "min0_forth.py"), str(source)],
                text=True, capture_output=True, check=False, encoding="utf-8",
            )
        self.assertEqual(result.returncode, 0)
        version = (ROOT.parent / "VERSION").read_text(encoding="utf-8").strip()
        self.assertIn(f"MIN0 CORE FORTH {version}", result.stdout)
        self.assertIn("DATA stack: [5]", result.stdout)

    def test_quiet_failure_is_nonzero_and_has_no_normal_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = self._source(directory, "MISSING")
            result = subprocess.run(
                [sys.executable, str(ROOT / "min0_forth.py"), "-z", str(source)],
                text=True, capture_output=True, check=False, encoding="utf-8",
            )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertIn("ERROR UnknownWord", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
