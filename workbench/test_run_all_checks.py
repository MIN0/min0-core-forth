import sys
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

import run_all_checks


class RunAllChecksTests(unittest.TestCase):
    def test_run_uses_the_requested_working_directory(self) -> None:
        requested = PROJECT_ROOT / "workbench"
        with patch("run_all_checks.subprocess.run") as subprocess_run:
            subprocess_run.return_value.returncode = 0
            self.assertTrue(
                run_all_checks.run("fixture", ["fixture"], cwd=requested)
            )
        subprocess_run.assert_called_once_with(
            ["fixture"], cwd=requested, check=False
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
