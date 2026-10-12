# FORTHの解釈・compile・実行を理解するためのノート

[英語版はこちらです](FORTH_EXECUTION_PHASES.md)

状態：次回リリースの学習資料へ統合するための、MIN0 CORE FORTH実装済み仕様に基づくノウハウ記録。

## なぜ一つのワードに複数の意味が見えるのか

FORTHでは、sourceを読んでいる時点と、生成したワードを後で実行する時点が明確に分かれる。同じsource中の
ワードでも、現在のinterpreter状態とそのワードに定義されたsemanticsによって、今実行するのか、後で実行する
CODEを作るのかが変わる。

このノートでは便宜上、次の四つの時点を区別する。

| 時点 | 起きること |
| --- | --- |
| 解釈時 | promptから読んだ数値や通常wordを、その場で処理する。 |
| compile時 | `: name ... ;`を読み、後で実行するCODEや辞書entryを作る。 |
| 定義ワード実行時 | `CREATE`を含む定義ワードを呼び、指定された名前の子wordを作る。 |
| 生成word実行時 | `DOES>`で与えられた子word固有の動作を実行する。 |

標準FORTHの文書では、wordごとにinterpretation semantics、compilation semantics、execution semanticsを
区別する。一つのwordを単純に「compile用」または「実行用」とだけ分類すると、この時間差を説明できない。

## `: ... ;`――compile状態の開始と終了

```forth
: SQUARE
  DUP *
;
```

`:`は解釈時に実行され、名前を読み、hidden状態のcolon definitionを開始する。以後の`DUP`と`*`はその場で
DATA stackへ作用するのではなく、`SQUARE`を将来実行するためのCODEとしてcompileされる。`;`は現在の定義を
完成して公開し、interpreterを解釈状態へ戻す。

したがって、`:`と`;`は対応する開始・終了wordである。ただし、直接制御構造用bufferの対象ではない。
colon compiler自身が複数行にまたがる状態、CODE生成、公開、error時rollbackを管理しているからである。

単独の`;`がerrorになる理由は「実行できないwordだから」ではなく、終了対象となる未完成定義がないためである。

## `IF ... THEN`――compile時に構造を作り、実行時にflagを使う

```forth
: ABS-LIKE
  DUP 0 < IF
    0 SWAP -
  THEN
;
```

定義中の`IF`と`THEN`はbranch先を持つCODEを組み立てる。`IF`のstack effect `( flag -- )`が現れるのは
`ABS-LIKE`を実行した時であり、定義をcompileしている時ではない。

MIN0 CORE FORTHでは同じ構造をpromptへ直接入力することもできる。

```forth
1 IF 10 ELSE 20 THEN
```

この場合は`THEN`までをbufferへ収集し、構造と全wordを検査してから実行する。開始語だけを見てerrorにしない
一方、対応する開始語のない`ELSE`や`THEN`は文脈errorになる。

## `['] name`――compile時に名前を解決し、実行時に`xt`を残す

```forth
: GET-SQUARE-XT
  ['] SQUARE
;
```

`[']`はcompile中に後続の`SQUARE`を読み、そのexecution tokenである`xt`を将来DATA stackへ置くCODEを
生成する。`GET-SQUARE-XT`をcompileしている最中に`xt`をstackへ置くわけではない。

promptでその場で`xt`を得る場合は、次の解釈時wordを使う。

```forth
' SQUARE
```

`[']`の後続名は終端wordではなく構文上のoperandである。そのため、`IF ... THEN`のような対応終端を待つ
buffer構造ではない。

## `CREATE ... DOES>`――一つの定義から別のwordを作る

```forth
: VALUE:
  CREATE ,
  DOES> @
;

10 VALUE: TEN
TEN
```

この例には三つの異なる実行時点がある。

1. `VALUE:`の定義時：`CREATE , DOES> @`を解析し、定義wordを作る。
2. `10 VALUE: TEN`の実行時：`CREATE`が`TEN`を作り、`,`が10を子wordのdata fieldへ保存する。
3. `TEN`の実行時：`DOES>`以降の`@`が働き、data fieldから10を取り出す。

`CREATE`と`DOES>`は協調するが、単純な開始語と終端語の組ではない。

- `CREATE`は`DOES>`なしでも子wordを作れる。
- `DOES>`は`CREATE`を閉じず、作成された子wordの将来の動作を指定する境界である。
- `DOES>`以降を含む定義全体を閉じるのは`;`である。

MIN0 CORE FORTH v0.1では、source定義word内の`CREATE`は本体の最初のtokenであり、`DOES>`はその後に一度だけ
置ける。この制約は現在の実装段階の仕様であり、一般的なFORTH概念そのものとは分けて記録する。

## `UNLOOP`――構文の終端ではなく、実行資源を外す

`DO`の対応終端は`LOOP`または`+LOOP`である。`UNLOOP`はそれらの代わりになる終端wordではなく、実行中の
最内loop frameを明示的に取り除く実行wordである。

```forth
: SEARCH-LIKE
  10 0 DO
    I 3 = IF
      UNLOOP EXIT
    THEN
  LOOP
;
```

典型的には、通常のloop終端を通らずにcolon definitionを抜ける前に使う。`UNLOOP`だけでは命令位置を移動
しないため、上の例では`EXIT`と組み合わせている。活動中のloop frameがなければcontext errorになる。

MIN0の直接入力loopでは、現在は`LEAVE`が制御移動とloop frameの後始末を一体で行う。直接入力buffer内の
`UNLOOP`は、後続実行、`EXIT`、loop終端との関係を別途定めるまで対象外とする。

## 同じ「error」でも理由を分ける

| 種類 | 例 | 意味 |
| --- | --- | --- |
| 未完了 | `1 IF`のままEOF | 続きが入力される間は待機し、入力終了時に必要な`THEN`を報告する。 |
| 対応不在 | 単独の`THEN`、`LOOP`、`;` | 閉じる対象が現在の文脈に存在しない。 |
| 使用文脈不在 | loop外の`I`、`J`、`UNLOOP` | wordは存在するが、必要な実行frameがない。 |
| 現段階の実装制限 | 直接buffer内の`S"`や`UNLOOP` | semanticsを安全に統一する設計がまだ確定していない。 |

この区別により、「辞書にあるのに実行できない」と一括りにせず、構文待機、構造不一致、実行時context不足、
実装段階の制限を別々に説明できる。

## 次回リリース資料へ統合する内容

次回の学習資料では、このノートを基礎として次を一つの章にまとめる。

- interpretation semantics、compilation semantics、execution semanticsの違い
- sourceを読む時点、定義wordを呼ぶ時点、生成wordを呼ぶ時点の時間軸
- `: ... ;`、直接制御構造、`[']`、`CREATE ... DOES>`、`UNLOOP`の比較
- 「compile専用」という短い表現では説明できないwordの分類
- 待機すべき未完了入力と、直ちに報告すべきcontext errorの判定基準
- Python版とRuby版で同じ結果を保証する実行例と回帰test

この章は、実装固有の制限と一般的なFORTHの考え方を明確に分けて記述する。
