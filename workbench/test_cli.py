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

    def test_quiet_direct_for_matches_in_both_launchers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = self._source(directory, "3 FOR I . NEXT")
            python_result = subprocess.run(
                [sys.executable, str(ROOT / "min0_forth.py"), "-z", str(source)],
                text=True, capture_output=True, check=False, encoding="utf-8",
            )
            ruby_result = subprocess.run(
                ["ruby", str(ROOT / "min0_forth.rb"), "-z", str(source)],
                text=True, capture_output=True, check=False, encoding="utf-8",
            )
        self.assertEqual(python_result.returncode, 0)
        self.assertEqual(ruby_result.returncode, 0)
        self.assertEqual(python_result.stdout, "012")
        self.assertEqual(ruby_result.stdout, "012")

    def test_quiet_compiled_output_words_match_in_both_launchers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = self._source(
                directory,
                ': CORE-OUT 65 EMIT CR -42 . S" ABC" TYPE ; CORE-OUT',
            )
            python_result = subprocess.run(
                [sys.executable, str(ROOT / "min0_forth.py"), "-z", str(source)],
                text=True, capture_output=True, check=False, encoding="utf-8",
            )
            ruby_result = subprocess.run(
                ["ruby", str(ROOT / "min0_forth.rb"), "-z", str(source)],
                text=True, capture_output=True, check=False, encoding="utf-8",
            )
        self.assertEqual(python_result.returncode, 0)
        self.assertEqual(ruby_result.returncode, 0)
        self.assertEqual(python_result.stdout, "A\n-42ABC")
        self.assertEqual(ruby_result.stdout, "A\n-42ABC")

    def test_quiet_direct_mixed_control_matches_in_both_launchers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = self._source(
                directory,
                "1 IF\n5 2 DO I . LOOP\nELSE 99 . THEN",
            )
            python_result = subprocess.run(
                [sys.executable, str(ROOT / "min0_forth.py"), "-z", str(source)],
                text=True, capture_output=True, check=False, encoding="utf-8",
            )
            ruby_result = subprocess.run(
                ["ruby", str(ROOT / "min0_forth.rb"), "-z", str(source)],
                text=True, capture_output=True, check=False, encoding="utf-8",
            )
        self.assertEqual(python_result.returncode, 0)
        self.assertEqual(ruby_result.returncode, 0)
        self.assertEqual(python_result.stdout, "234")
        self.assertEqual(ruby_result.stdout, "234")

    def test_quiet_unfinished_for_is_an_error_in_both_launchers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = self._source(directory, "3 FOR I")
            results = (
                subprocess.run(
                    [sys.executable, str(ROOT / "min0_forth.py"), "-z", str(source)],
                    text=True, capture_output=True, check=False, encoding="utf-8",
                ),
                subprocess.run(
                    ["ruby", str(ROOT / "min0_forth.rb"), "-z", str(source)],
                    text=True, capture_output=True, check=False, encoding="utf-8",
                ),
            )
        for result in results:
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertIn("matching NEXT", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
