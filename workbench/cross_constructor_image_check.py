"""Exchange the constructor audit envelope between Python and Ruby."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def run_json(command: list[str]) -> dict:
    completed = subprocess.run(
        command, cwd=ROOT, check=True, capture_output=True, text=True
    )
    return json.loads(completed.stdout)


def require_rejection(command: list[str], message: str) -> None:
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    if completed.returncode == 0 or message not in completed.stderr:
        raise SystemExit(
            f"FAIL: {command[0]} did not reject image with {message!r}"
        )


def normalized_envelope(path: Path) -> dict:
    envelope = json.loads(path.read_text(encoding="utf-8"))
    envelope.pop("writer", None)
    return envelope


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        temp = Path(directory)
        python_image = temp / "python-constructor.json"
        ruby_image = temp / "ruby-constructor.json"
        python_write = run_json(
            [sys.executable, "constructor_image_fixture.py", "write", str(python_image)]
        )
        ruby_read = run_json(
            ["ruby", "constructor_image_fixture.rb", "read", str(python_image)]
        )
        ruby_write = run_json(
            ["ruby", "constructor_image_fixture.rb", "write", str(ruby_image)]
        )
        python_read = run_json(
            [sys.executable, "constructor_image_fixture.py", "read", str(ruby_image)]
        )
        envelopes_equal = normalized_envelope(python_image) == normalized_envelope(ruby_image)

        expected = {
            "plan_version": 1,
            "actions": [2, 3, 4, 0],
            "stack": [0x8000],
            "item_body": 0x8000,
            "body_hex": "ab000000",
            "data_here": 0x8004,
        }
        ruby_semantics = {key: ruby_read[key] for key in expected}
        python_semantics = {key: python_read[key] for key in expected}

        transport_bad = temp / "transport-version-2.json"
        transport = json.loads(python_image.read_text(encoding="utf-8"))
        transport["version"] = 2
        transport_bad.write_text(json.dumps(transport), encoding="utf-8")

        plan_bad = temp / "plan-version-2.json"
        plan = json.loads(python_image.read_text(encoding="utf-8"))
        headers = bytearray.fromhex(plan["dictionary_hex"])
        offset = plan["record_plan"] - plan["dictionary_base"] + 4
        headers[offset : offset + 4] = (2).to_bytes(4, "little")
        plan["dictionary_hex"] = headers.hex()
        plan_bad.write_text(json.dumps(plan), encoding="utf-8")

        for reader in (
            [sys.executable, "constructor_image_fixture.py", "read"],
            ["ruby", "constructor_image_fixture.rb", "read"],
        ):
            require_rejection([*reader, str(transport_bad)], "version")
            require_rejection([*reader, str(plan_bad)], "constructor plan version")

    print(f"Python envelope: {python_write['bytes']} bytes")
    print(f"Ruby envelope:   {ruby_write['bytes']} bytes")
    print(f"transport payload match: {envelopes_equal}")
    print(f"Python -> Ruby semantics: {ruby_semantics}")
    print(f"Ruby -> Python semantics: {python_semantics}")
    if not envelopes_equal or ruby_semantics != expected or python_semantics != expected:
        raise SystemExit("FAIL: constructor image round-trip mismatch")
    print("PASS: Python and Ruby constructor images round-trip in both directions")


if __name__ == "__main__":
    main()
