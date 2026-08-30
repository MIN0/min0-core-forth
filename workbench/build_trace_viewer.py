"""Generate a self-contained offline Guided Viewer from an actual VM trace."""

from __future__ import annotations

import json
from pathlib import Path

from trace_value_demo import (
    COMPILED_OUTPUT_SOURCE,
    RECORD_SOURCE,
    ROLLBACK_SOURCE,
    STACK_EARLY_SOURCE,
    STACK_LATE_SOURCE,
    VALUE_SOURCE,
    build_record_trace_document,
    build_rollback_trace_document,
    build_stack_trace_document,
    build_trace_document,
)


ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
TEMPLATE = PROJECT_ROOT / "viewer" / "trace-viewer-template.html"
DEFAULT_OUTPUT = PROJECT_ROOT / "viewer" / "value-trace.html"


def build_payload() -> dict:
    """Return the measured scenarios and their presentation metadata."""

    return {
        "scenarios": [
            {
                "id": "stack-late",
                "label": "2 3 4 * + . → 14",
                "title": "スタックで計算順序を見る — 答えは14",
                "default_mode": "word",
                "source_word_only": True,
                "filename": "stack-14.fth",
                "source": STACK_LATE_SOURCE,
                "trace": build_stack_trace_document(STACK_LATE_SOURCE),
            },
            {
                "id": "stack-early",
                "label": "2 3 * 4 + . → 10",
                "title": "スタックで計算順序を見る — 答えは10",
                "default_mode": "word",
                "source_word_only": True,
                "filename": "stack-10.fth",
                "source": STACK_EARLY_SOURCE,
                "trace": build_stack_trace_document(STACK_EARLY_SOURCE),
            },
            {
                "id": "success",
                "label": "成功: ANSWERを生成・実行",
                "title": "VALUE: から ANSWER が生まれるまで",
                "default_mode": "word",
                "filename": "value-answer.fth",
                "source": VALUE_SOURCE,
                "trace": build_trace_document(include_source_words=True),
            },
            {
                "id": "rollback",
                "label": "失敗: EMPTYを生成中に復元",
                "title": "VALUE: EMPTY — 失敗と復元",
                "default_mode": "word",
                "filename": "value-rollback.fth",
                "source": ROLLBACK_SOURCE,
                "trace": build_rollback_trace_document(include_source_words=True),
            },
            {
                "id": "record",
                "label": "複合構築: ITEMの4バイト",
                "title": "RECORD: — C,・ALLOT・ALIGNを追う",
                "default_mode": "highlights",
                "filename": "record-item.fth",
                "word_step_events": [
                    "definer.execute.begin",
                    "child.create.hidden",
                    "constructor.c_comma",
                    "constructor.allot",
                    "constructor.align",
                    "child.publish",
                    "definer.execute.end",
                ],
                "source": RECORD_SOURCE,
                "trace": build_record_trace_document(include_source_words=True),
            },
            {
                "id": "compiled-output",
                "label": '文字出力: compiled ."',
                "title": '." — DATA文字列からSERVICE 1へ',
                "default_mode": "word",
                "filename": "compiled-output.fth",
                "source": COMPILED_OUTPUT_SOURCE,
                "trace": build_stack_trace_document(COMPILED_OUTPUT_SOURCE),
            },
        ]
    }


def build_viewer(output: Path = DEFAULT_OUTPUT) -> Path:
    payload = build_payload()
    # Escaping '<' keeps embedded source-derived strings from closing the script tag.
    payload_json = json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c")
    template = TEMPLATE.read_text(encoding="utf-8")
    if "__TRACE_PAYLOAD__" not in template:
        raise ValueError("viewer template has no trace payload marker")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        template.replace("__TRACE_PAYLOAD__", payload_json),
        encoding="utf-8",
        newline="\n",
    )
    return output


if __name__ == "__main__":
    print(build_viewer())
