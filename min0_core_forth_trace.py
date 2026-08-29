"""Versioned semantic trace records for the MIN0 CORE FORTH Guided Viewer."""

from __future__ import annotations

from typing import Any


TRACE_FORMAT = "min0-core-forth-trace/0.1"
PAYLOAD_ROLE = "observed-data-not-instructions"
SOURCE_WORD_EVENT = "source.word.complete"
WORD_TRACE_EVENTS = frozenset(
    {
        SOURCE_WORD_EVENT,
        "source.word.error",
        "word.execute.enter",
        "does.body.push",
        "word.execute.nested.complete",
    }
)


def _hex(address: int) -> str:
    return f"0x{address:08X}"


def explain_event(event: str, details: dict[str, Any]) -> str:
    """Return the deterministic Japanese explanation for one semantic event."""

    if event == SOURCE_WORD_EVENT:
        token = details["token"]
        operands = details.get("operands", [])
        action = details["action"]
        operand = operands[0] if operands else ""
        if action == "begin-definition":
            return f"{token} が新しいワード {operand} の定義を開始しました。"
        if action == "finish-definition":
            return f"{token} が定義を完成させ、解釈状態へ戻しました。"
        if action == "compile-token":
            if token == "CREATE":
                return "CREATEを定義ワードのconstructorとして記録しました。"
            if token == ",":
                return ", を実行時のallocator actionとして記録しました。"
            if token == "C,":
                return "C, を1バイト保存するallocator actionとして記録しました。"
            if token == "ALLOT":
                return "ALLOTを指定バイト数だけ予約するallocator actionとして記録しました。"
            if token == "ALIGN":
                return "ALIGNをdata HEREをセル境界へ整列するallocator actionとして記録しました。"
            if token == "DOES>":
                return "DOES>がconstructorと、子の実行時behaviorを分けました。"
            return f"{token} を現在の定義へコンパイルしました。"
        if action == "push-number":
            return f"数値 {token} をDATA stackへ積みました。"
        if action == "emit-number":
            output = details.get("terminal_output", [])
            value = output[-1] if output else "?"
            return f". がDATA stack最上段の {value} を端末へ表示し、stackから取り除きました。"
        if action == "emit-character":
            output = details.get("terminal_output", [])
            value = output[-1] if output else "?"
            shown = repr(value)
            return f"EMITがDATA stack最上段の下位8bitを文字 {shown} として端末へ送りました。"
        if action == "emit-newline":
            return "CRが端末へ改行（LF）を送りました。"
        if action == "emit-string":
            stack = details.get("data_stack_before", [])
            length = stack[-1] if stack else "?"
            return (
                f"TYPEが指定範囲全体を検査してから{length}バイトを"
                "端末へ送り、アドレスと長さをstackから取り除きました。"
            )
        if action == "push-string-literal":
            length = operands[0] if operands else "?"
            return (
                f'S" が引用内容を{length}バイトのDATA文字列として保存し、'
                "そのアドレスと長さをstackへ積みました。"
            )
        if action == "emit-string-literal":
            length = operands[0] if operands else "?"
            return f'." が引用内容{length}バイトを端末へ送りました。'
        if action == "compile-string-literal":
            length = operands[0] if operands else "?"
            return (
                f'S" が引用内容{length}バイトをimage DATAへ保存し、'
                "relocation可能なaddressとlengthを現在の定義へコンパイルしました。"
            )
        if action == "compile-output-literal":
            length = operands[0] if operands else "?"
            return (
                f'." が引用内容{length}バイト、relocation可能なaddress、'
                "検証対象のterminal-type SERVICE呼出しを定義へコンパイルしました。"
            )
        if action == "execute-definer":
            return f"定義ワード {token} が、子の名前 {operand} を読み取って生成しました。"
        if action == "execute-word":
            return f"ワード {token} の内部実行を終え、呼出し元へ戻りました。"
        if action == "define-data-word":
            return f"{token} が名前 {operand} のデータワードを作成しました。"
        return f"ソースワード {token} の処理が完了しました。"
    if event == "word.execute.enter":
        return f"ワード {details['word']} の中へ入ります。"
    if event == "source.word.error":
        operand = details.get("operands", [""])[0]
        target = f" {operand}" if operand else ""
        return (
            f"{details['token']}{target} は{details['error']}で完了できませんでした。"
            "未完成の変更を捨て、開始前の状態へ戻しました。"
        )
    if event == "does.body.push":
        return (
            f"{details['word']} がbody {_hex(details['body'])}をDATA stackへ積みました。"
        )
    if event == "word.execute.nested.complete":
        return (
            f"{details['parent']} の中でワード {details['word']} を実行しました。"
        )
    if event == "definer.compile.complete":
        return f"{details['word']} のconstructor planを辞書へ公開しました。"
    if event == "definer.execute.begin":
        return (
            f"定義ワード {details['word']} が子 {details['child']} の生成を開始しました。"
        )
    if event == "child.create.hidden":
        return f"{details['child']} をhidden状態で作成しました。"
    if event == "constructor.segment.begin":
        return (
            f"constructorのCODE断片 {_hex(details['code_address'])} を実行します。"
        )
    if event == "constructor.segment.end":
        return (
            f"constructorのCODE断片 {_hex(details['code_address'])} が終了しました。"
        )
    if event == "constructor.comma":
        return (
            f"DATAアドレス{_hex(details['address'])}へ{details['value']}を保存し、"
            f"data HEREを{_hex(details['data_here_after'])}へ進めました。"
        )
    if event == "constructor.c_comma":
        return (
            f"DATAアドレス{_hex(details['address'])}へ1バイト値{details['value']}を保存し、"
            f"data HEREを{_hex(details['data_here_after'])}へ進めました。"
        )
    if event == "constructor.allot":
        return (
            f"DATAアドレス{_hex(details['address'])}から{details['count']}バイトを予約し、"
            f"data HEREを{_hex(details['data_here_after'])}へ進めました。"
        )
    if event == "constructor.align":
        return (
            f"data HERE {_hex(details['address_before'])}へ{details['padding']}バイトの"
            f"paddingを入れ、{_hex(details['data_here_after'])}へ整列しました。"
        )
    if event == "child.does.attach":
        return (
            f"{details['child']} のbody {_hex(details['body'])} とbehavior "
            f"{_hex(details['behavior'])}を接続しました。"
        )
    if event == "child.publish":
        return f"完成した {details['child']} のhidden状態を解除して公開しました。"
    if event == "definer.execute.end":
        return f"{details['child']} の生成が正常に完了しました。"
    if event == "definer.execute.rollback":
        return (
            f"{details['child']} の生成中に{details['error']}が発生したため、"
            "辞書とスタックを開始前へ戻しました。"
        )
    if event == "does.execute.begin":
        return (
            f"{details['word']} がbody {_hex(details['body'])}を積み、"
            f"behavior {_hex(details['behavior'])}を開始します。"
        )
    if event == "does.execute.end":
        return f"{details['word']} のDOES behaviorが終了しました。"
    return f"{event} が発生しました。"


class TraceRecorder:
    """Optional observer; it never controls or mutates FORTH execution."""

    def __init__(
        self, implementation: str, *, include_source_words: bool = False
    ) -> None:
        self.implementation = implementation
        self.include_source_words = include_source_words
        self.events: list[dict[str, Any]] = []

    def emit(self, vm: Any, dictionary: Any, event: str, **details: Any) -> None:
        if event in WORD_TRACE_EVENTS and not self.include_source_words:
            return
        loops = [
            {"limit": frame.limit, "index": frame.index}
            for frame in vm.loop_stack
        ]
        self.events.append(
            {
                "sequence": len(self.events),
                "event": event,
                "payload_role": PAYLOAD_ROLE,
                "details": details,
                "state": {
                    "ip": vm.ip,
                    "steps": vm.steps,
                    "data_stack": list(vm.data_stack),
                    "return_stack": list(vm.return_stack),
                    "loop_stack": loops,
                    "header_here": dictionary.here,
                    "data_here": dictionary.data_here,
                    "latest": dictionary.latest,
                },
                "basic_explanation": explain_event(event, details),
            }
        )

    def document(self) -> dict[str, Any]:
        return {
            "trace_format": TRACE_FORMAT,
            "implementation": self.implementation,
            "events": list(self.events),
        }
