import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from min0_rp2350_runtime import (
    HelperStatus,
    Rp2350ExecutionContext,
    RuntimeCapability,
    min0_abort_transaction,
    min0_checked_ld32,
    min0_frame_commit,
    min0_result_stage,
    min0_stage_st32,
)
from min0_virtual_assembler import MemoryWindow


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime" / "rp2350" / "min0_rp2350_runtime.c"
FIXTURE = ROOT / "workbench" / "rp2350_runtime_c_fixture.c"
INCLUDE = ROOT / "runtime" / "rp2350"


def _compiler_candidates():
    configured = os.environ.get("MIN0_CC")
    if configured:
        yield Path(configured)
    names = ("cc", "gcc") if os.name == "nt" else ("cc", "gcc", "clang")
    for name in names:
        found = shutil.which(name)
        if found:
            yield Path(found)
    ruby = shutil.which("ruby")
    if ruby:
        root = Path(ruby).resolve().parent.parent
        for relative in (
            Path("msys64/ucrt64/bin/gcc.exe"),
            Path("msys64/mingw64/bin/gcc.exe"),
        ):
            candidate = root / relative
            if candidate.is_file():
                yield candidate
    if os.name == "nt":
        system_root = Path(os.environ.get("SystemDrive", "C:") + "\\")
        for pattern in (
            "Ruby*/msys64/ucrt64/bin/gcc.exe",
            "Ruby*/msys64/mingw64/bin/gcc.exe",
        ):
            yield from sorted(system_root.glob(pattern), reverse=True)


def _parse_fixture(stdout):
    result = {}
    for line in stdout.splitlines():
        fields = line.split()
        if not fields:
            continue
        result[fields[0]] = dict(field.split("=", 1) for field in fields[1:])
    return result


def _python_reference_vectors():
    memory = MemoryWindow(0x1000, 16)
    success = Rp2350ExecutionContext(
        [99, 10, 20, 0x1000], 3, 2,
        (RuntimeCapability(7, "DATA", memory),),
    )
    min0_stage_st32(success, 7, 0x1000, 4, 88)
    _, forwarded = min0_checked_ld32(success, 7, 0x1000, 4)
    min0_result_stage(success, 0, 30)
    min0_result_stage(success, 1, 40)
    committed = min0_frame_commit(success, 3, 2)

    abort_memory = MemoryWindow(0x1000, 4, initial=(7).to_bytes(4, "little"))
    aborted = Rp2350ExecutionContext(
        [99, 10, 20, 0x1000], 3, 2,
        (RuntimeCapability(7, "DATA", abort_memory),),
    )
    min0_result_stage(aborted, 0, 30)
    min0_stage_st32(aborted, 7, 0x1000, 0, 88)
    abort_status = min0_abort_transaction(aborted, HelperStatus.ABORTED)

    readonly = MemoryWindow(
        0x1000, 4, readable=True, writable=False,
        initial=(0).to_bytes(4, "little"),
    )
    rejected = Rp2350ExecutionContext(
        [10, 0x1000], 2, 1,
        (RuntimeCapability(7, "DATA", readonly),),
    )
    denied = min0_stage_st32(rejected, 7, 0x1000, 0, 1)
    min0_abort_transaction(rejected, denied)
    repeated = min0_abort_transaction(rejected, HelperStatus.ABORTED)

    return {
        "success": {
            "status": str(int(committed)),
            "state": "1",
            "depth": str(len(success.data_stack)),
            "stack": ",".join(str(value) for value in success.data_stack),
            "memory": str(memory.read32(0x1004)),
            "forwarded": str(forwarded),
        },
        "abort": {
            "status": str(int(abort_status)),
            "state": "2",
            "depth": str(len(aborted.data_stack)),
            "stack": ",".join(str(value) for value in aborted.data_stack),
            "memory": str(abort_memory.read32(0x1000)),
            "pending": str(len(aborted.pending_writes)),
        },
        "reject": {
            "denied": str(int(denied)),
            "repeated": str(int(repeated)),
            "state": "2",
            "depth": str(len(rejected.data_stack)),
            "memory": str(readonly.read32(0x1000)),
        },
        "matrix": {
            "statuses": ",".join(str(int(status)) for status in (
                HelperStatus.INPUT_INDEX,
                HelperStatus.OUTPUT_INDEX,
                HelperStatus.OUTPUT_DUPLICATE,
                HelperStatus.OUTPUT_MISSING,
                HelperStatus.CONTRACT_MISMATCH,
                HelperStatus.UNKNOWN_CAPABILITY,
                HelperStatus.ADDRESS_OVERFLOW,
                HelperStatus.UNALIGNED_ADDRESS,
                HelperStatus.ADDRESS_RANGE,
                HelperStatus.READ_DENIED,
                HelperStatus.WRITE_DENIED,
                HelperStatus.PENDING_FULL,
                HelperStatus.OK,
            )),
            "input": "10",
        },
    }


class Rp2350RuntimeCTests(unittest.TestCase):
    def test_c_source_passes_strict_riscv32_syntax_check(self):
        clang = shutil.which("clang")
        if not clang:
            self.skipTest("clang is not available for the portable C syntax gate")
        result = subprocess.run(
            [
                clang, "-target", "riscv32-unknown-elf", "-std=c11",
                "-Wall", "-Wextra", "-Werror", "-pedantic",
                f"-I{INCLUDE}", "-fsyntax-only", str(RUNTIME), str(FIXTURE),
            ],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_compiled_c_vectors_match_python_reference(self):
        compiler = next(_compiler_candidates(), None)
        if compiler is None:
            self.skipTest("no host C compiler is available")
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
            executable = Path(directory) / (
                "rp2350-runtime-fixture.exe" if os.name == "nt"
                else "rp2350-runtime-fixture"
            )
            command = [
                str(compiler), "-std=c11", "-Wall", "-Wextra", "-Werror",
                "-pedantic", f"-I{INCLUDE}", str(RUNTIME), str(FIXTURE),
                "-o", str(executable),
            ]
            compiled = subprocess.run(
                command, cwd=ROOT, capture_output=True, text=True, check=False,
            )
            diagnostics = compiled.stdout + compiled.stderr
            if compiled.returncode != 0 and not diagnostics.strip():
                self.skipTest("compiler child process is unavailable in this sandbox")
            self.assertEqual(compiled.returncode, 0, diagnostics)
            executed = subprocess.run(
                [str(executable)], cwd=ROOT, capture_output=True, text=True,
                check=False,
            )
            self.assertEqual(
                executed.returncode, 0, executed.stdout + executed.stderr
            )
            self.assertEqual(
                _parse_fixture(executed.stdout), _python_reference_vectors()
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
