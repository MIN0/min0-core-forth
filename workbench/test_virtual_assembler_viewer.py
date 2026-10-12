import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class VirtualAssemblerViewerTests(unittest.TestCase):
    def test_page_exposes_reference_execution_and_safety_boundary(self):
        text = (ROOT / "viewer" / "virtual-assembler.html").read_text(encoding="utf-8")
        self.assertIn("仮想アセンブラ体験Viewer", text)
        self.assertIn("reference modelで実行", text)
        self.assertIn("RP2350 MACHINE EXECUTION", text)
        self.assertIn("virtual-assembler-core.js", text)
        self.assertNotIn("fetch(", text)

    @unittest.skipUnless(shutil.which("node"), "Node.js is not installed")
    def test_browser_reference_core(self):
        result = subprocess.run(["node", "workbench/test_virtual_assembler_browser.js"], cwd=ROOT, text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS", result.stdout)

if __name__ == "__main__": unittest.main(verbosity=2)
