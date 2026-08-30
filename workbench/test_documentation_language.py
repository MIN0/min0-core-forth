import re
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
JAPANESE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")


class DocumentationLanguageTests(unittest.TestCase):
    def test_english_readme_has_only_the_requested_japanese_first_line(self) -> None:
        lines = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8").splitlines()
        self.assertEqual(
            lines[0],
            "[日本語版を見るにはここをクリックしてください](README_JP.md)",
        )
        self.assertIsNone(JAPANESE.search("\n".join(lines[1:])))

    def test_direct_english_entry_documents_contain_no_japanese(self) -> None:
        paths = (
            "FIRST_READ.md",
            "SECURITY.md",
            "docs/README.md",
            "docs/QUICKSTART.md",
            "docs/PROJECT_ORIGIN.md",
            "docs/LICENSE_AND_SECURITY.md",
            "docs/KNOWN_LIMITATIONS_0.1.md",
            "docs/RELEASE_AUDIT_0.1.1.md",
        )
        for relative in paths:
            with self.subTest(relative=relative):
                text = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
                self.assertIsNone(JAPANESE.search(text))

    def test_japanese_readme_routes_to_japanese_entry_documents(self) -> None:
        text = (PROJECT_ROOT / "README_JP.md").read_text(encoding="utf-8")
        for target in (
            "FIRST_READ_JP.md",
            "docs/QUICKSTART_JP.md",
            "docs/PROJECT_ORIGIN_JP.md",
            "docs/README_JP.md",
            "docs/LICENSE_AND_SECURITY_JP.md",
            "docs/KNOWN_LIMITATIONS_0.1_JP.md",
            "docs/RELEASE_AUDIT_0.1.1_JP.md",
            "SECURITY_JP.md",
            "viewer/value-trace.html",
        ):
            with self.subTest(target=target):
                self.assertIn(target, text)
                if not target.startswith("viewer/"):
                    self.assertTrue((PROJECT_ROOT / target).is_file())

    def test_english_readme_routes_to_english_viewer_and_documents(self) -> None:
        text = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        for target in (
            "FIRST_READ.md",
            "docs/QUICKSTART.md",
            "docs/PROJECT_ORIGIN.md",
            "docs/README.md",
            "docs/LICENSE_AND_SECURITY.md",
            "docs/KNOWN_LIMITATIONS_0.1.md",
            "docs/RELEASE_AUDIT_0.1.1.md",
            "SECURITY.md",
            "viewer/value-trace-en.html",
        ):
            with self.subTest(target=target):
                self.assertIn(target, text)
                if not target.startswith("viewer/"):
                    self.assertTrue((PROJECT_ROOT / target).is_file())


if __name__ == "__main__":
    unittest.main(verbosity=2)
