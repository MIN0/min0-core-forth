# MIN0 CORE FORTH compiler relocation R0

## 対象

対話型の`OuterInterpreter` compilerがCODEへ32ビット絶対論理アドレスを書き込む際、
同時に型付きrelocation recordを生成する。これは`IMAGE_ADDRESSING_R0.md`で推奨した
ハイブリッド方式のCODE側実装である。

ラベル付き簡易`Assembler`と、最終persistent image containerへのmanifest格納は
このR0の対象外であり、形式はまだ凍結しない。

## record

各recordは次の5項目を持つ。

| field | R0の意味 |
| --- | --- |
| `section` | patch対象領域。現在は常に`code` |
| `offset` | compiler開始時の`code_base`からaddress cellまでのbyte offset |
| `target` | cellが指す領域。`code`、`dictionary`、`data` |
| `width` | Reference32では4 byte |
| `kind` | `call`、`zbranch`など、生成理由を示す検査用分類 |

link時の基本操作は、recordのpatch cellに`target領域の新base－旧base`を加えることで
ある。source sectionの移動差分はpatch位置を探すために使い、cell値へ重ねて加えない。

## 記録する参照

- colon word呼出しの`CALL`: CODE
- `BRANCH`、`ZBRANCH`: CODE
- `?DO`の脱出先: CODE
- `LOOP`、`+LOOP`の反復先: CODE
- `LEAVE`の脱出先: CODE
- `VARIABLE`、`CREATE`をcompileした`LIT`: DATA
- DOES wordのbodyを積む`LIT`: DATA
- DOES behaviorを呼ぶ`CALL`: CODE

普通の数値literalと`CONSTANT`の値は、同じ`LIT` operandでもrecordを生成しない。
値がアドレスに見えるかどうかをcompilerが推測することもない。

## rollback

定義開始時にmanifest件数を保存する。構文不正、容量不足などで定義を破棄する場合は、
CODE、辞書、allocatorとともに、その定義中に追加したrecordも削除する。したがって
未公開wordの参照だけがmanifestへ残ることはない。

## 実働確認

Python版とRuby版で、次を含む同一sourceをcompileした。

- colon word間のCALL
- `IF ELSE THEN`
- `BEGIN WHILE REPEAT`
- `DO LOOP`、`?DO`、`LEAVE`、`+LOOP`
- `VARIABLE`
- `CREATE , DOES> @`で作る`VALUE:`とそのchild

両言語は同じ順序・offset・分類で15件を生成した。内訳はCODE向け13件、DATA向け
2件である。さらに辞書metadataから得た53件と結合し、三領域を次のように移動した。

| 領域 | 元のbase | 移動後base |
| --- | ---: | ---: |
| CODE | `0x1000` | `0x2000` |
| DICTIONARY | `0x4000` | `0x5000` |
| DATA | `0x8000` | `0x9000` |

移動後imageを`RuntimeDictionary.load_images`で検査し、colon word、全control flow、
VARIABLE、DOES wordを実行した。最終stackは
`[99, 2, 3, 3, 0, 2, 7, 0x9000]`で一致した。`SLOT`は`0x9000`、
`ANSWER` bodyは`0x9004`、保存値は7、data HEREは`0x9008`となった。

## R0で未凍結の事項

- manifestの永続byte／file表現
- image containerのversionとchecksum
- recordの重複、範囲、整列、overflowを検査する正式linker
- 辞書recordを生成時に直接記録する方式への統一
- 利用者がDATAへ明示的なアドレスcellを保存するwordまたはAPI
- Reference16／Reference64でのwidth表現

この次段階は`RELOCATION_LINKER_R0.md`で実装した。CODEとDICTIONARYのrecord合計68件を
一つのmanifestへ統合し、不正recordをimage変更前に拒否するcopy-on-success linkerを
Python／Ruby双方で確認した。次はcomponent digestとallocator metadataを含むimage envelopeを
検討する。
