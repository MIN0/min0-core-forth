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
            self.assertIn("class MonitorExecutionControl", text)
            self.assertIn("class MobileForthSession", text)
            self.assertIn("class MobileForthScheduler", text)
            self.assertIn("class MobileForthWorkerEngine", text)
            self.assertIn("class MobileForthWorkerClient", text)
            self.assertIn('const VERSION = "min0-mobile-monitor/0.3"', text)
            self.assertIn('wordMeta("KEY?"', text)
            self.assertIn('wordMeta("KEY"', text)
            self.assertIn('wordMeta("VARIABLE"', text)
            self.assertIn('wordMeta("@"', text)
            self.assertIn('wordMeta("!"', text)
            self.assertIn('wordMeta("BREAK"', text)
            self.assertIn('id="pause"', text)
            self.assertIn('id="step"', text)
            self.assertIn('id="continue"', text)
            self.assertIn('id="stop"', text)
            self.assertIn('id="abort"', text)
            self.assertIn('id="current-location"', text)
            self.assertIn('id="call-history"', text)
            self.assertIn('id="execution-mode"', text)
            self.assertIn('id="input-text"', text)
            self.assertIn('id="send-input"', text)
            self.assertIn('id="input-status"', text)
            self.assertIn('id="variable-list"', text)
            self.assertIn('id="variable-status"', text)
            self.assertIn('id="clear-source"', text)
            self.assertIn('id="reset-view"', text)
            self.assertIn('twoKeyInput: \'KEY EMIT KEY EMIT CR\'', text)
            self.assertIn("safeVariable: 'VARIABLE SCORE", text)
            self.assertIn("monitorBreak: ': WATCH", text)
            self.assertIn('"waiting-input": "入力待ち"', text)
            self.assertIn("function sendInput()", text)
            self.assertIn("function resetIdleDisplay()", text)
            self.assertIn("function renderVariables(snapshot, state)", text)
            self.assertIn("以下は復旧前の観察記録です。", text)
            self.assertIn('setControls("pause-requested")', text)
            self.assertIn('const acceptsInput = ["running", "paused", "stepping", "waiting-input"].includes(state);', text)
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
            self.assertIn('source build <span id="revision">test-revision</span>', text)
            self.assertIn("@media print", text)
            self.assertIn(".trace-panel .table-wrap", text)
            self.assertIn('class="panel trace-panel"', text)
            self.assertIn('class="panel word-catalog-panel"', text)
            self.assertNotIn(BUILDER.CORE_MARKER, text)
            self.assertNotIn(BUILDER.MONITOR_MARKER, text)
            self.assertNotIn(BUILDER.SESSION_MARKER, text)
            self.assertNotIn(BUILDER.SCHEDULER_MARKER, text)
            self.assertNotIn(BUILDER.PROTOCOL_MARKER, text)
            self.assertNotIn(BUILDER.ENGINE_MARKER, text)
            self.assertNotIn(BUILDER.CLIENT_MARKER, text)
            self.assertNotIn(BUILDER.WORKER_SOURCE_MARKER, text)
            self.assertNotIn(BUILDER.REVISION_MARKER, text)
            self.assertNotIn("fetch(", text)
            self.assertNotIn("http://", text)
            self.assertNotIn("https://", text)
            self.assertNotIn("<script src=", text.lower())
            if shutil.which("node"):
                scripts = re.findall(r"<script>([\s\S]*?)</script>", text)
                self.assertEqual(len(scripts), 8)
                for index, script in enumerate(scripts):
                    script_path = Path(directory) / f"inline-{index}.js"
                    script_path.write_text(script, encoding="utf-8")
                    result = subprocess.run(
                        ["node", "--check", str(script_path)],
                        text=True, capture_output=True, check=False,
                    )
                    self.assertEqual(
                        result.returncode, 0,
                        f"inline script {index}:\n{result.stdout}{result.stderr}",
                    )
                worker_path = Path(directory) / "embedded-worker.js"
                worker_path.write_text(BUILDER.worker_source(ROOT), encoding="utf-8")
                result = subprocess.run(
                    ["node", "--check", str(worker_path)],
                    text=True, capture_output=True, check=False,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("min0WorkerEngine.receive", worker_path.read_text(encoding="utf-8"))
                result = subprocess.run(
                    ["node", "workbench/test_embedded_mobile_worker.js", str(worker_path)],
                    cwd=ROOT, text=True, capture_output=True, check=False,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("PASS", result.stdout)

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
