import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "build_iphone_reading_pack", ROOT / "tools" / "build_iphone_reading_pack.py"
)
assert SPEC is not None and SPEC.loader is not None
PACK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PACK)


class IPhoneReadingPackTests(unittest.TestCase):
    def test_pack_is_private_portable_and_complete(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "reading.zip"
            result = PACK.build_pack(output, revision="test-revision")
            self.assertTrue(output.is_file())
            self.assertTrue(output.with_suffix(".zip.sha256").is_file())
            with zipfile.ZipFile(output) as archive:
                names = set(archive.namelist())
                self.assertIn("START_HERE_JP.txt", names)
                self.assertIn("MIN0_CORE_FORTH_READER_JP.html", names)
                self.assertIn("MIN0_FORTH_MOBILE.html", names)
                self.assertIn("guided-viewer.html", names)
                self.assertIn("documents/04_WORD_REFERENCE_JP.txt", names)
                self.assertIn("examples/basic.fth.txt", names)
                self.assertIn("source/min0_core_forth_vm.py.txt", names)
                self.assertNotIn(".git/config", names)
                manifest = json.loads(archive.read("MANIFEST.json"))
                self.assertEqual(manifest["revision"], "test-revision")
                combined = b"".join(archive.read(name) for name in names)
                personal_path_marker = b"C:" + b"\\Users\\"
                personal_uri_marker = b"file:///" + b"C:/" + b"Users/"
                self.assertNotIn(personal_path_marker, combined)
                self.assertNotIn(personal_uri_marker, combined)
                mobile = archive.read("MIN0_FORTH_MOBILE.html")
                self.assertIn(b"class MobileForth", mobile)
                self.assertNotIn(b"fetch(", mobile)
            self.assertEqual(result["file_count"], len(names))

    def test_reader_uses_escaped_text_without_network(self) -> None:
        rendered = PACK._reader_html("abc123", [("title", "<script>alert(1)</script>")])
        self.assertIn("&lt;script&gt;", rendered)
        self.assertNotIn("<script>", rendered)
        self.assertNotIn("fetch(", rendered)
        self.assertNotIn("http://", rendered)
        self.assertNotIn("https://", rendered)


if __name__ == "__main__":
    unittest.main(verbosity=2)
