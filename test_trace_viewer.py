import tempfile
import unittest
from pathlib import Path

from build_trace_viewer import build_payload, build_viewer
from trace_value_demo import (
    STACK_EARLY_SOURCE,
    STACK_LATE_SOURCE,
    build_record_trace_document,
    build_rollback_trace_document,
    build_stack_trace_document,
    build_trace_document,
)


class TraceViewerTests(unittest.TestCase):
    def test_beginner_stack_traces_are_measured_word_by_word(self) -> None:
        cases = [(STACK_LATE_SOURCE, "14"), (STACK_EARLY_SOURCE, "10")]
        for source, expected in cases:
            with self.subTest(source=source):
                document = build_stack_trace_document(source)
                words = [
                    event
                    for event in document["events"]
                    if event["event"] == "source.word.complete"
                ]
                self.assertEqual(len(words), 6)
                self.assertEqual(words[-1]["details"]["token"], ".")
                self.assertEqual(words[-1]["details"]["action"], "emit-number")
                self.assertEqual(words[-1]["details"]["data_stack_before"], [int(expected)])
                self.assertEqual(words[-1]["state"]["data_stack"], [])
                self.assertEqual(words[-1]["details"]["terminal_output"], [expected])
                self.assertEqual(document["terminal_output"], [expected])

    def test_character_output_trace_keeps_the_exact_stream(self) -> None:
        document = build_stack_trace_document("65 EMIT CR")
        words = [
            event
            for event in document["events"]
            if event["event"] == "source.word.complete"
        ]
        self.assertEqual(
            [event["details"]["action"] for event in words],
            ["push-number", "emit-character", "emit-newline"],
        )
        self.assertEqual(words[1]["details"]["terminal_output"], ["A"])
        self.assertEqual(words[2]["details"]["terminal_output"], ["A", "\n"])
        self.assertIn("文字 'A'", words[1]["basic_explanation"])
        self.assertIn("改行（LF）", words[2]["basic_explanation"])
        self.assertEqual(document["terminal_output"], ["A", "\n"])

    def test_type_trace_records_one_validated_string_operation(self) -> None:
        document = build_stack_trace_document(
            "CREATE TEXT 0x41 C, 0x42 C, TEXT 2 TYPE"
        )
        words = [
            event
            for event in document["events"]
            if event["event"] == "source.word.complete"
        ]
        type_event = words[-1]
        self.assertEqual(type_event["details"]["token"], "TYPE")
        self.assertEqual(type_event["details"]["action"], "emit-string")
        self.assertEqual(type_event["details"]["data_stack_before"][-1], 2)
        self.assertEqual(type_event["state"]["data_stack"], [])
        self.assertEqual(type_event["details"]["terminal_output"], ["AB"])
        self.assertIn("指定範囲全体を検査", type_event["basic_explanation"])
        self.assertEqual(document["terminal_output"], ["AB"])

    def test_quoted_string_trace_preserves_word_level_actions(self) -> None:
        document = build_stack_trace_document('S" AB" TYPE ." !"')
        words = [
            event
            for event in document["events"]
            if event["event"] == "source.word.complete"
        ]
        self.assertEqual(
            [event["details"]["token"] for event in words],
            ['S"', "TYPE", '."'],
        )
        self.assertEqual(
            [event["details"]["action"] for event in words],
            ["push-string-literal", "emit-string", "emit-string-literal"],
        )
        self.assertEqual(words[0]["state"]["data_stack"][-1], 2)
        self.assertIn("DATA文字列", words[0]["basic_explanation"])
        self.assertIn("1バイト", words[2]["basic_explanation"])
        self.assertEqual(document["terminal_output"], ["AB", "!"])

    def test_compiled_s_quote_trace_shows_image_placement(self) -> None:
        document = build_stack_trace_document(': MESSAGE S" Hi" ; MESSAGE')
        words = [
            event
            for event in document["events"]
            if event["event"] == "source.word.complete"
        ]
        quoted = next(event for event in words if event["details"]["token"] == 'S"')
        self.assertEqual(quoted["details"]["action"], "compile-string-literal")
        self.assertIn("image DATA", quoted["basic_explanation"])
        self.assertIn("relocation", quoted["basic_explanation"])
        self.assertEqual(words[-1]["state"]["data_stack"][-1], 2)

    def test_compiled_dot_quote_trace_shows_verified_service(self) -> None:
        document = build_stack_trace_document(': GREET ." Hi" ; GREET')
        words = [
            event
            for event in document["events"]
            if event["event"] == "source.word.complete"
        ]
        quoted = next(event for event in words if event["details"]["token"] == '."')
        self.assertEqual(quoted["details"]["action"], "compile-output-literal")
        self.assertIn("terminal-type SERVICE", quoted["basic_explanation"])
        self.assertEqual(words[-1]["state"]["data_stack"], [])
        self.assertEqual(document["terminal_output"], ["Hi"])

    def test_reusable_trace_builder_returns_actual_13_event_trace(self) -> None:
        document = build_trace_document()
        self.assertEqual(document["trace_format"], "min0-core-forth-trace/0.1")
        self.assertEqual(len(document["events"]), 13)
        self.assertEqual(document["events"][5]["event"], "constructor.comma")
        self.assertEqual(document["events"][5]["details"]["value"], 123)

    def test_viewer_trace_adds_nine_source_word_checkpoints(self) -> None:
        document = build_trace_document(include_source_words=True)
        words = [
            event
            for event in document["events"]
            if event["event"] == "source.word.complete"
        ]
        self.assertEqual(len(words), 9)
        self.assertEqual(
            [event["details"]["token"] for event in words],
            [":", "CREATE", ",", "DOES>", "@", ";", "123", "VALUE:", "ANSWER"],
        )
        value = words[7]
        self.assertEqual(value["details"]["operands"], ["ANSWER"])
        self.assertEqual(value["details"]["data_stack_before"], [123])
        self.assertEqual(value["state"]["data_stack"], [])

    def test_answer_trace_steps_into_does_behavior(self) -> None:
        document = build_trace_document(include_source_words=True)
        word_events = [
            event
            for event in document["events"]
            if event["event"]
            in {
                "source.word.complete",
                "word.execute.enter",
                "does.body.push",
                "word.execute.nested.complete",
            }
        ]
        self.assertEqual(len(word_events), 13)
        answer_events = word_events[-4:]
        self.assertEqual(
            [event["event"] for event in answer_events],
            [
                "word.execute.enter",
                "does.body.push",
                "word.execute.nested.complete",
                "source.word.complete",
            ],
        )
        self.assertEqual(answer_events[0]["details"]["word"], "ANSWER")
        self.assertEqual(answer_events[1]["state"]["data_stack"], [0x8000])
        self.assertEqual(answer_events[2]["details"]["word"], "@")
        self.assertEqual(answer_events[2]["details"]["data_stack_before"], [0x8000])
        self.assertEqual(answer_events[2]["state"]["data_stack"], [123])

    def test_failed_definer_word_is_recorded_after_rollback(self) -> None:
        document = build_rollback_trace_document(include_source_words=True)
        self.assertEqual(
            document["outcome"],
            {"status": "rolled-back", "error": "StackUnderflow"},
        )
        rollback = next(
            event
            for event in document["events"]
            if event["event"] == "definer.execute.rollback"
        )
        source_error = document["events"][-1]
        self.assertEqual(source_error["event"], "source.word.error")
        self.assertEqual(source_error["details"]["token"], "VALUE:")
        self.assertEqual(source_error["details"]["operands"], ["EMPTY"])
        self.assertEqual(source_error["state"], rollback["state"])
        self.assertEqual(source_error["state"]["data_stack"], [])

    def test_record_trace_exposes_allocator_progression(self) -> None:
        document = build_record_trace_document(include_source_words=True)
        actions = [
            event
            for event in document["events"]
            if event["event"]
            in {"constructor.c_comma", "constructor.allot", "constructor.align"}
        ]
        self.assertEqual(
            [event["event"] for event in actions],
            ["constructor.c_comma", "constructor.allot", "constructor.align"],
        )
        self.assertEqual(
            [event["state"]["data_here"] for event in actions],
            [0x8001, 0x8003, 0x8004],
        )
        self.assertEqual(actions[0]["state"]["data_stack"], [2])
        self.assertEqual(actions[1]["state"]["data_stack"], [])
        self.assertEqual(actions[2]["details"]["padding"], 1)

        source_words = [
            event
            for event in document["events"]
            if event["event"] == "source.word.complete"
        ]
        explanations = {event["details"]["token"]: event["basic_explanation"] for event in source_words}
        self.assertIn("1バイト保存", explanations["C,"])
        self.assertIn("指定バイト数", explanations["ALLOT"])
        self.assertIn("セル境界", explanations["ALIGN"])

    def test_record_word_view_steps_through_constructor(self) -> None:
        record = next(
            scenario
            for scenario in build_payload()["scenarios"]
            if scenario["id"] == "record"
        )
        base_word_events = {
            "source.word.complete",
            "source.word.error",
            "word.execute.enter",
            "does.body.push",
            "word.execute.nested.complete",
        }
        included = base_word_events | set(record["word_step_events"])
        word_view = [
            event for event in record["trace"]["events"] if event["event"] in included
        ]
        self.assertEqual(len(word_view), 19)

        entry = next(
            index
            for index, event in enumerate(word_view)
            if event["event"] == "word.execute.enter"
            and event["details"]["word"] == "RECORD:"
        )
        self.assertEqual(
            [event["event"] for event in word_view[entry : entry + 9]],
            [
                "word.execute.enter",
                "definer.execute.begin",
                "child.create.hidden",
                "constructor.c_comma",
                "constructor.allot",
                "constructor.align",
                "child.publish",
                "definer.execute.end",
                "source.word.complete",
            ],
        )

    def test_beginner_scenarios_request_source_word_only_view(self) -> None:
        scenarios = build_payload()["scenarios"][:2]
        self.assertEqual(
            [scenario["id"] for scenario in scenarios],
            ["stack-late", "stack-early"],
        )
        self.assertTrue(all(scenario["source_word_only"] for scenario in scenarios))
        self.assertEqual(
            [
                len(
                    [
                        event
                        for event in scenario["trace"]["events"]
                        if event["event"] == "source.word.complete"
                    ]
                )
                for scenario in scenarios
            ],
            [6, 6],
        )

    def test_generated_viewer_is_offline_and_contains_actual_trace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = build_viewer(Path(directory) / "viewer.html")
            html = output.read_text(encoding="utf-8")

        self.assertIn("min0-core-forth-trace/0.1", html)
        self.assertIn("constructor.comma", html)
        self.assertIn("1ワードずつ", html)
        self.assertIn('id="stackChange"', html)
        self.assertIn('id="breadcrumb"', html)
        self.assertIn("実行前", html)
        self.assertIn("今はここを見てください", html)
        self.assertIn("失敗: EMPTYを生成中に復元", html)
        self.assertIn("複合構築: ITEMの4バイト", html)
        self.assertIn("2 3 4 * + . → 14", html)
        self.assertIn("2 3 * 4 + . → 10", html)
        self.assertIn("文字出力: compiled .", html)
        self.assertIn("Hello from compiled Forth", html)
        self.assertIn("terminal-type SERVICE", html)
        self.assertIn('id="terminalOutput"', html)
        self.assertIn("例題FORTHソース（コピー・編集できます）", html)
        self.assertIn("変更内容はViewerの動きには反映されません。", html)
        self.assertIn('id="copySource"', html)
        self.assertIn('id="saveSource"', html)
        self.assertIn("navigator.clipboard.writeText", html)
        self.assertIn("new Blob", html)
        self.assertIn('output.join("")', html)
        self.assertIn("構築の要所", html)
        self.assertIn("constructor.c_comma", html)
        self.assertIn("constructor.allot", html)
        self.assertIn("constructor.align", html)
        self.assertIn('"default_mode": "highlights"', html)
        self.assertIn('"source_word_only": true', html)
        self.assertIn('"word_step_events": [', html)
        self.assertIn("allEvents.filter(isWordEvent)", html)
        self.assertIn('id="rollbackProof"', html)
        self.assertIn("--attention:", html)
        self.assertIn("prefers-reduced-motion: reduce", html)
        self.assertIn("DATAアドレス0x00008000へ123を保存", html)
        self.assertNotIn("__TRACE_PAYLOAD__", html)
        for network_api in ("fetch(", "XMLHttpRequest", "WebSocket("):
            self.assertNotIn(network_api, html)

    def test_viewer_uses_text_nodes_for_trace_derived_content(self) -> None:
        template = (
            Path(__file__).resolve().parent
            / "viewer"
            / "trace-viewer-template.html"
        ).read_text(encoding="utf-8")
        self.assertNotIn("innerHTML", template)
        self.assertIn("textContent = event.basic_explanation", template)
        self.assertIn("textContent = JSON.stringify(event", template)
        self.assertIn('$("exampleSource").value', template)
        self.assertNotIn('$("source").innerHTML', template)


if __name__ == "__main__":
    unittest.main(verbosity=2)
