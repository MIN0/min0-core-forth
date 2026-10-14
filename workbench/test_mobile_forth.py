import importlib.util
import shutil
import subprocess
import tempfile
import unittest
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "build_mobile_forth", ROOT / "tools" / "build_mobile_forth.py"
)
assert SPEC is not None and SPEC.loader is not None
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)


class MobileForthTests(unittest.TestCase):
    def test_build_is_self_contained_and_offline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "mobile.html"
            BUILDER.build(output, root=ROOT, revision="test-revision")
            text = output.read_text(encoding="utf-8")
            self.assertIn("MIN0 CORE FORTH", text)
            self.assertIn("test-revision", text)
            self.assertIn("class MobileForth", text)
            self.assertIn('id="trace-word"', text)
            self.assertIn('id="trace-invocation"', text)
            self.assertIn('id="trace-all-loops"', text)
            self.assertIn("function foldLoops(events)", text)
            self.assertIn('id="word-search"', text)
            self.assertIn('id="word-catalog"', text)
            self.assertIn("function renderWordCatalog()", text)
            self.assertIn('id="stack-before"', text)
            self.assertIn('id="stack-stopped"', text)
            self.assertIn('id="stack-final-label"', text)
            self.assertIn('id="recovery-note"', text)
            self.assertNotIn(BUILDER.CORE_MARKER, text)
            self.assertNotIn(BUILDER.REVISION_MARKER, text)
            self.assertNotIn("fetch(", text)
            self.assertNotIn("http://", text)
            self.assertNotIn("https://", text)
            self.assertNotIn("<script src=", text.lower())

    def test_committed_html_is_current(self) -> None:
        committed = (ROOT / "viewer" / "mobile-forth.html").read_text(encoding="utf-8")
        match = re.search(r'<span id="revision">([^<]+)</span>', committed)
        self.assertIsNotNone(match)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "mobile.html"
            BUILDER.build(output, root=ROOT, revision=match.group(1))
            self.assertEqual(
                output.read_bytes(),
                committed.encode("utf-8"),
            )

    @unittest.skipUnless(shutil.which("node"), "Node.js is not installed")
    def test_javascript_vm(self) -> None:
        result = subprocess.run(
            ["node", "workbench/test_mobile_forth.js"],
            cwd=ROOT, text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
