"""Generate a self-contained offline Guided Viewer from an actual VM trace."""

from __future__ import annotations

import json
import re
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
ENGLISH_OUTPUT = PROJECT_ROOT / "viewer" / "value-trace-en.html"


ENGLISH_REPLACEMENTS = {
    "MIN0 CORE FORTH Guided Viewer — VALUE: の誕生": "MIN0 CORE FORTH Guided Viewer — the birth of VALUE:",
    "VALUE: から ANSWER が生まれるまで": "From VALUE: to the birth of ANSWER",
    "今はここを見てください": "Look here now",
    "実行例": "Scenario",
    "表示粒度": "View level",
    "1ワードずつ": "One word at a time",
    "構築の要所": "Construction highlights",
    "内部イベント": "Internal events",
    "トレース操作": "Trace controls",
    "← 前へ": "← Previous",
    "▶ 自動再生": "▶ Auto play",
    "次へ →": "Next →",
    "表示する段階": "Displayed step",
    "FORTHソース": "FORTH source",
    "端末出力": "Terminal output",
    "（まだありません）": "(none yet)",
    "現在位置と辞書allocator": "Current position and dictionary allocator",
    "三つのメモリ領域": "Three memory regions",
    "VM命令・behavior": "VM instructions and behavior",
    "header・plan・descriptor": "headers, plans, and descriptors",
    "生成されたワードのbody": "body of the generated word",
    "三つのスタック": "Three stacks",
    "観測イベントの生データ": "Raw observed event data",
    "例題FORTHソース（コピー・編集できます）": "Example FORTH source (copy and edit)",
    "変更内容はViewerの動きには反映されません。コピーまたは.fthで保存し、実機やPython／Ruby版で確認してください。":
        "Edits do not change this measured Viewer trace. Copy or save the source as .fth and test it on a target or with Python/Ruby.",
    "コピーまたは保存するFORTHソース": "FORTH source to copy or save",
    "ソースをコピー": "Copy source",
    "example.fthとして保存": "Save as example.fth",
    "安全境界:": "Safety boundary:",
    "このHTMLはオフラインで動き、トレースを観測データとして表示するだけです。表示文字列を命令として実行しません。":
        "This HTML runs offline and only displays traces as observed data. It never executes displayed text as instructions.",
    "実行位置": "execution position",
    "空": "empty",
    "実行前": "before",
    "実行後": "after",
    "開始前 = 復元後": "before start = after restoration",
    "ワード": "word",
    "要所": "highlights",
    "内部": "internal",
    "コピーしました。": "Copied.",
    "自動コピーできませんでした。文字列を選択してコピーしてください。":
        "Automatic copying failed. Select the text and copy it manually.",
    "を保存しました。": " was saved.",
    "Ⅱ 一時停止": "Ⅱ Pause",
    "スタックで計算順序を見る — 答えは14": "Watch stack order — the answer is 14",
    "スタックで計算順序を見る — 答えは10": "Watch stack order — the answer is 10",
    "成功: ANSWERを生成・実行": "Success: create and execute ANSWER",
    "失敗: EMPTYを生成中に復元": "Failure: restore while creating EMPTY",
    "VALUE: EMPTY — 失敗と復元": "VALUE: EMPTY — failure and restoration",
    "複合構築: ITEMの4バイト": "Compound construction: ITEM's four bytes",
    "RECORD: — C,・ALLOT・ALIGNを追う": "RECORD: — follow C, ALLOT, and ALIGN",
    "文字出力: compiled .\"": "Text output: compiled .\"",
    ".\" — DATA文字列からSERVICE 1へ": ".\" — from a DATA string to SERVICE 1",
    "数値 2 をDATA stackへ積みました。": "Pushed the number 2 onto the DATA stack.",
    "数値 3 をDATA stackへ積みました。": "Pushed the number 3 onto the DATA stack.",
    "数値 4 をDATA stackへ積みました。": "Pushed the number 4 onto the DATA stack.",
    "ワード * の中へ入ります。": "Enter word *.",
    "ワード * の内部実行を終え、呼出し元へ戻りました。": "Word * completed and returned to its caller.",
    "ワード + の中へ入ります。": "Enter word +.",
    "ワード + の内部実行を終え、呼出し元へ戻りました。": "Word + completed and returned to its caller.",
    ". がDATA stack最上段の 14 を端末へ表示し、stackから取り除きました。":
        ". displayed 14 from the top of the DATA stack and removed it.",
    ". がDATA stack最上段の 10 を端末へ表示し、stackから取り除きました。":
        ". displayed 10 from the top of the DATA stack and removed it.",
    ": が新しいワード VALUE: の定義を開始しました。": ": began the definition of the new word VALUE:.",
    "CREATEを定義ワードのconstructorとして記録しました。": "Recorded CREATE as the defining word's constructor.",
    ", を実行時のallocator actionとして記録しました。": "Recorded , as a run-time allocator action.",
    "DOES>がconstructorと、子の実行時behaviorを分けました。": "DOES> separated the constructor from the child's run-time behavior.",
    "@ を現在の定義へコンパイルしました。": "Compiled @ into the current definition.",
    "VALUE: のconstructor planを辞書へ公開しました。": "Published VALUE:'s constructor plan in the dictionary.",
    "; が定義を完成させ、解釈状態へ戻しました。": "; completed the definition and returned to interpretation state.",
    "数値 123 をDATA stackへ積みました。": "Pushed the number 123 onto the DATA stack.",
    "ワード VALUE: の中へ入ります。": "Enter word VALUE:.",
    "定義ワード VALUE: が子 ANSWER の生成を開始しました。": "Defining word VALUE: began creating child ANSWER.",
    "ANSWER をhidden状態で作成しました。": "Created ANSWER in the hidden state.",
    "constructorのCODE断片 0x00001000 を実行します。": "Execute constructor CODE fragment 0x00001000.",
    "constructorのCODE断片 0x00001000 が終了しました。": "Constructor CODE fragment 0x00001000 completed.",
    "DATAアドレス0x00008000へ123を保存し、data HEREを0x00008004へ進めました。":
        "Stored 123 at DATA address 0x00008000 and advanced data HERE to 0x00008004.",
    "constructorのCODE断片 0x00001001 を実行します。": "Execute constructor CODE fragment 0x00001001.",
    "constructorのCODE断片 0x00001001 が終了しました。": "Constructor CODE fragment 0x00001001 completed.",
    "ANSWER のbody 0x00008000 とbehavior 0x00001002を接続しました。":
        "Connected ANSWER body 0x00008000 to behavior 0x00001002.",
    "完成した ANSWER のhidden状態を解除して公開しました。": "Unhid and published the completed ANSWER.",
    "ANSWER の生成が正常に完了しました。": "ANSWER was created successfully.",
    "定義ワード VALUE: が、子の名前 ANSWER を読み取って生成しました。": "Defining word VALUE: read the child name and created ANSWER.",
    "ワード ANSWER の中へ入ります。": "Enter word ANSWER.",
    "ANSWER がbody 0x00008000を積み、behavior 0x00001002を開始します。":
        "ANSWER pushes body 0x00008000 and starts behavior 0x00001002.",
    "ANSWER がbody 0x00008000をDATA stackへ積みました。": "ANSWER pushed body 0x00008000 onto the DATA stack.",
    "ANSWER の中でワード @ を実行しました。": "ANSWER executed word @.",
    "ANSWER のDOES behaviorが終了しました。": "ANSWER's DOES behavior completed.",
    "ワード ANSWER の内部実行を終え、呼出し元へ戻りました。": "Word ANSWER completed and returned to its caller.",
    "定義ワード VALUE: が子 EMPTY の生成を開始しました。": "Defining word VALUE: began creating child EMPTY.",
    "EMPTY をhidden状態で作成しました。": "Created EMPTY in the hidden state.",
    "EMPTY の生成中にStackUnderflowが発生したため、辞書とスタックを開始前へ戻しました。":
        "StackUnderflow occurred while creating EMPTY, so the dictionary and stacks were restored.",
    "VALUE: EMPTY はStackUnderflowで完了できませんでした。未完成の変更を捨て、開始前の状態へ戻しました。":
        "VALUE: EMPTY failed with StackUnderflow; incomplete changes were discarded and the initial state restored.",
    ": が新しいワード RECORD: の定義を開始しました。": ": began the definition of the new word RECORD:.",
    "C, を1バイト保存するallocator actionとして記録しました。": "Recorded C, as an allocator action that stores one byte.",
    "ALLOTを指定バイト数だけ予約するallocator actionとして記録しました。": "Recorded ALLOT as an allocator action that reserves the requested byte count.",
    "ALIGNをdata HEREをセル境界へ整列するallocator actionとして記録しました。": "Recorded ALIGN as an allocator action that aligns data HERE to a cell boundary.",
    "RECORD: のconstructor planを辞書へ公開しました。": "Published RECORD:'s constructor plan in the dictionary.",
    "数値 0X1AB をDATA stackへ積みました。": "Pushed the number 0X1AB onto the DATA stack.",
    "ワード RECORD: の中へ入ります。": "Enter word RECORD:.",
    "定義ワード RECORD: が子 ITEM の生成を開始しました。": "Defining word RECORD: began creating child ITEM.",
    "ITEM をhidden状態で作成しました。": "Created ITEM in the hidden state.",
    "DATAアドレス0x00008000へ1バイト値171を保存し、data HEREを0x00008001へ進めました。":
        "Stored one-byte value 171 at DATA address 0x00008000 and advanced data HERE to 0x00008001.",
    "DATAアドレス0x00008001から2バイトを予約し、data HEREを0x00008003へ進めました。":
        "Reserved two bytes from DATA address 0x00008001 and advanced data HERE to 0x00008003.",
    "constructorのCODE断片 0x00001002 を実行します。": "Execute constructor CODE fragment 0x00001002.",
    "constructorのCODE断片 0x00001002 が終了しました。": "Constructor CODE fragment 0x00001002 completed.",
    "data HERE 0x00008003へ1バイトのpaddingを入れ、0x00008004へ整列しました。":
        "Inserted one padding byte at data HERE 0x00008003 and aligned it to 0x00008004.",
    "constructorのCODE断片 0x00001003 を実行します。": "Execute constructor CODE fragment 0x00001003.",
    "constructorのCODE断片 0x00001003 が終了しました。": "Constructor CODE fragment 0x00001003 completed.",
    "完成した ITEM のhidden状態を解除して公開しました。": "Unhid and published the completed ITEM.",
    "ITEM の生成が正常に完了しました。": "ITEM was created successfully.",
    "定義ワード RECORD: が、子の名前 ITEM を読み取って生成しました。": "Defining word RECORD: read the child name and created ITEM.",
    "ワード ITEM の中へ入ります。": "Enter word ITEM.",
    "ワード ITEM の内部実行を終え、呼出し元へ戻りました。": "Word ITEM completed and returned to its caller.",
    ": が新しいワード GREET の定義を開始しました。": ": began the definition of the new word GREET.",
    ".\" が引用内容25バイト、relocation可能なaddress、検証対象のterminal-type SERVICE呼出しを定義へコンパイルしました。":
        ".\" compiled 25 quoted bytes, a relocatable address, and a verified terminal-type SERVICE call.",
    "ワード GREET の中へ入ります。": "Enter word GREET.",
    "ワード GREET の内部実行を終え、呼出し元へ戻りました。": "Word GREET completed and returned to its caller.",
}


JAPANESE_TEXT = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")


def _translate_english(value):
    """Translate Viewer presentation strings while preserving measured values."""

    if isinstance(value, dict):
        return {key: _translate_english(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_translate_english(item) for item in value]
    if not isinstance(value, str):
        return value
    for source, replacement in sorted(
        ENGLISH_REPLACEMENTS.items(), key=lambda item: len(item[0]), reverse=True
    ):
        value = value.replace(source, replacement)
    return value


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


def build_viewer(output: Path = DEFAULT_OUTPUT, *, language: str = "ja") -> Path:
    payload = build_payload()
    if language == "en":
        payload = _translate_english(payload)
    elif language != "ja":
        raise ValueError(f"unsupported Viewer language: {language!r}")
    # Escaping '<' keeps embedded source-derived strings from closing the script tag.
    payload_json = json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c")
    template = TEMPLATE.read_text(encoding="utf-8")
    if "__TRACE_PAYLOAD__" not in template:
        raise ValueError("viewer template has no trace payload marker")
    output.parent.mkdir(parents=True, exist_ok=True)
    html = template.replace("__TRACE_PAYLOAD__", payload_json)
    if language == "en":
        html = _translate_english(html)
        remaining = JAPANESE_TEXT.search(html)
        if remaining is not None:
            excerpt = html[max(0, remaining.start() - 40) : remaining.start() + 80]
            raise ValueError(f"untranslated Japanese text remains in English Viewer: {excerpt!r}")
    output.write_text(
        html,
        encoding="utf-8",
        newline="\n",
    )
    return output


if __name__ == "__main__":
    print(build_viewer())
    print(build_viewer(ENGLISH_OUTPUT, language="en"))
