import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "build_mobile_pwa", ROOT / "tools" / "build_mobile_pwa.py"
)
assert SPEC is not None and SPEC.loader is not None
PWA = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PWA)


class MobilePwaTests(unittest.TestCase):
    def test_package_is_installable_and_offline_capable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "mobile-pwa.zip"
            result = PWA.build(output, root=ROOT, revision="test-revision")
            with zipfile.ZipFile(output) as archive:
                self.assertEqual(
                    set(archive.namelist()),
                    {"index.html", "manifest.webmanifest", "sw.js", "README_JP.txt", "EVALUATION_JP.txt"},
                )
                index = archive.read("index.html").decode("utf-8")
                worker = archive.read("sw.js").decode("utf-8")
                manifest = json.loads(archive.read("manifest.webmanifest"))
                evaluation = archive.read("EVALUATION_JP.txt").decode("utf-8")
                self.assertIn("class MobileForth", index)
                self.assertIn("class MobileForthWorkerClient", index)
                self.assertIn("min0WorkerEngine.receive", index)
                self.assertIn("test-revision", index)
                self.assertIn("serviceWorker.register", index)
                self.assertNotIn("http://", index)
                self.assertNotIn("https://", index)
                self.assertNotIn("__MIN0_", index)
                self.assertIn("cache.addAll(APP_FILES)", worker)
                self.assertIn('start_url', manifest)
                self.assertEqual(manifest["display"], "standalone")
                self.assertIn("index.html?eval=test-revision", evaluation)
                self.assertIn("Worker分離モード", evaluation)
                self.assertIn(": SPIN BEGIN 1 DROP AGAIN ;", evaluation)
            self.assertTrue(output.with_suffix(".zip.sha256").is_file())
            self.assertEqual(result["revision"], "test-revision")


if __name__ == "__main__":
    unittest.main(verbosity=2)
