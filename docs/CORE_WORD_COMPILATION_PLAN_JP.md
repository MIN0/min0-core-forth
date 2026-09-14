# CORE wordのcompile互換性解消計画

[英語版はこちらです](CORE_WORD_COMPILATION_PLAN.md)

状態：2026-09-14実装・検証済み。本書は決定理由と受入れ記録を残す。

## 決定

旧実装では`. EMIT CR TYPE`をpromptで直接実行できたが、colon definition内へcompileできなかった。これは
維持するMIN0仕様ではなく、CORE互換性を完成させる過程の実装上の不足と判断し、現在の開発版で解消した。

通常の実行wordには、原則として次を要求する。

> promptで実行できる通常wordはcolon definition内へcompileでき、直接入力とcompile済み実行で同じ
> execution semanticsを与える。

compile構造、定義delimiter、名前を解析するword、活動中のframeを必要とするwordには固有のsemanticsが
あるため、この原則とは別に分類する。内部でhost関数を使うことは、source上のcompile禁止理由にしない。

## CFとの比較結果

確認したCF commitは`07ec6a7a2a65d382d0c54111ec2a2c5b93cc0cf4`である。CFの`emit`はC側出力関数を
呼ぶVM primitiveとして辞書登録され、COMPILE状態では通常wordとしてcompileされる。CF自身も`space`、
`tab`、`cr`などのcolon definition内で`emit`を使用する。

したがって、MIN0のcompiled `EMIT`拒否はCF準拠仕様ではない。

## 実装結果

次の四wordを直接入力とcolon definitionの両方で使用可能にした。

| word | stack effect | compile時の実装 |
| --- | --- | --- |
| `TYPE` | `( c-addr u -- )` | 既存`SERVICE 1 terminal-type-v0.1`を生成する。 |
| `EMIT` | `( x -- )` | 新設`SERVICE 2 terminal-emit-v0.1`を生成する。 |
| `CR` | `( -- )` | 専用`SERVICE 4 terminal-cr-v0.1`を生成する。 |
| `.` | `( n -- )` | 新設`SERVICE 3 terminal-dot-v0.1`を生成する。 |

`terminal-emit-v0.1`は`x`の下位8 bitを一文字として出力し、成功後にだけ`x`を消費する。
`terminal-dot-v0.1`は現在の直接`.`と同じ符号付き10進表現を出力し、余分なspaceを追加しない。直接入力経路と
SERVICE handlerは共通処理を使い、表示、stack effect、error時状態を一致させる。

当初はcompiled `CR`を`LIT 10`＋`SERVICE 2`とする案だった。しかし、この形は論理上stack effectが
`( -- )`でも、実行途中にDATA stackを1 cell余分に必要とし、満杯のstackで`StackOverflow`になり得る。
そこで入力cellを必要としない専用`SERVICE 4`へ変更した。直接入力とcompile済み`CR`はいずれも同じ
handlerを使い、論理LFを一つ出力する。

`WORDS`は辞書内容を参照するTOOLS系wordなので同じ監査対象には含めるが、上記四wordの修正を妨げないよう
別判定とする。

## CORE全word監査

起動時65 wordすべてについてmatrixを作り、無理由なinterpret-only制限を監査した。結果は
[CORE word semantics matrix](CORE_WORD_SEMANTICS_MATRIX_JP.md)に保存した。

| 記録項目 | 内容 |
| --- | --- |
| interpretation semantics | promptで入力した時の動作 |
| compilation semantics | 定義中に実行する処理、または生成するCODE |
| execution semantics | compile済みwordを呼んだ時の動作 |
| 必要context | 定義中、loop中、後続名などの条件 |
| 基準 | 標準FORTH、CF、MIN0独自拡張のどれに基づくか |
| 差異 | 意図的な差か、未実装か、error理由は何か |

優先監査対象は`. EMIT CR TYPE WORDS`、`HERE , C, ALLOT ALIGN`、`CONSTANT VARIABLE CREATE`、
`DEFER ' IS ACTION-OF`である。解析wordや定義wordは無条件にcompile可能と決めず、source parserと実行時入力の
semanticsを確認してから判断する。

## 受入れtest

Python版とRuby版の両方で次を確認した。

```forth
65 EMIT
: EMIT-A 65 EMIT ;
EMIT-A

: NEWLINE CR ;
NEWLINE

: SAY-ABC S" ABC" TYPE ;
SAY-ABC

: SHOW-NUMBER -42 . ;
SHOW-NUMBER

: DIGITS 3 FOR I 48 + EMIT NEXT ;
DIGITS
```

受入れ条件：

- 直接入力とcompile済みwordの出力byte列および最終DATA stackが一致する
- `EMIT-A`は`A`、`SAY-ABC`は`ABC`、`SHOW-NUMBER`は`-42`、`DIGITS`は`012`を出力する
- stack underflow、無効memory範囲、未登録serviceでは、失敗したserviceの引数と既存出力を変更しない
- verifierがservice operand、許可ID、branch境界を検証する
- sealed実行では必要serviceが登録・固定されていなければ公開を拒否する
- Python／Rubyのbytecode、service要求集合、出力、error結果が一致する
- word referenceと既知の制限から古い「compile不可」記述を更新する

2026-09-14の全体検証結果は、Python 336 test、Ruby 48 test file、Python／Ruby間49 checkがすべて合格である。

## 主な変更箇所

- `workbench/min0_core_forth_outer.py`／`.rb`：compile分岐、共通出力処理、service登録
- `workbench/test_compiled_output_words.py`／`.rb`：直接／compile済みsemanticsと失敗時原子性
- service境界、CLI、cross-language test：4 service、sealed実行、Python／Ruby一致
- word reference、既知の制限、terminal／service境界仕様、65 word監査matrix

新しいterminal専用opcodeは追加せず、CPU非依存の`SERVICE`境界を維持する。UART、host console、test bufferは
target側adapterの違いとして扱い、FORTH sourceのsemanticsを変えない。
