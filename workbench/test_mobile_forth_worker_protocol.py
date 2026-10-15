import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class MobileForthWorkerProtocolTests(unittest.TestCase):
    def test_javascript_worker_protocol(self) -> None:
        result = subprocess.run(
            ["node", "workbench/test_mobile_forth_worker_protocol.js"],
            cwd=ROOT, text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
