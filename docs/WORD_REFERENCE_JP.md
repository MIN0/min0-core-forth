# MIN0 CORE FORTH ワード・ポケットリファレンス

[英語版はこちらです](WORD_REFERENCE.md)

これはリリース0.1.1の`WORDS`が表示する起動時ワード61個の短いマニュアルです。端末の横に置いて
使うことを想定しています。詳しい設計理由と制限は、各仕様書に残しています。

## 最初にここを見る：何ができるのか

| やりたいこと | 注目するワード |
| --- | --- |
| stackを見ながら計算する | `DUP SWAP OVER DROP + - * .` |
| 新しい処理を定義する | `: ;` |
| 条件判断とloopを作る | `IF ELSE THEN BEGIN UNTIL DO LOOP` |
| 値を保存して取り出す | `VARIABLE ! @ CONSTANT` |
| 新しい種類のワードを作る | `CREATE DOES>` |
| 呼出し元を再compileせず、選んだ処理だけを切り替える | `DEFER ' ['] IS ACTION-OF` |
| 使えるワードを見る | `WORDS` |

> [!TIP]
> **動的切替えは、このFORTHで意識して用意した機能です。** `DEFER`は名前付きの呼出しslotを作り、
> `IS`が現在の飛び先を選び、`ACTION-OF`が現在の飛び先を調べます。compile済みの呼出し元は
> slotを呼び続けるため、選択する処理を変えても再compileする必要がありません。

```forth
: OLD-ACTION 10 ;
: NEW-ACTION 20 ;
DEFER ACTION
' OLD-ACTION IS ACTION
: USE-ACTION ACTION ;
USE-ACTION          \ 10を残す
' NEW-ACTION IS ACTION
USE-ACTION          \ 20を残す。USE-ACTIONは再compileしていない
```

現在の0.1では、`DEFER`の飛び先はcolon definitionだけです。認証済みMonitorがruntime辞書をlockした後は、
通常sourceからの`IS`を拒否し、Monitorの狭く監査された制御経路だけで切り替えます。

## stack effectの読み方

`( 実行前 -- 実行後 )`はDATA stackの変化です。最も右が最上段です。

- `DUP ( x -- x x )`：最上段を複製します。
- `! ( x addr -- )`：値と書込み先addressを消費します。
- `WORDS ( -- )`：DATA stackを変えません。
- `flag`は偽が`0`、真が`0xFFFFFFFF`です。
- `xt`はexecution tokenであり、生のCODE addressではありません。

「解釈」はpromptで直接使うこと、「compile」は`: name ... ;`の中で使うことです。「構造」はcompile時に
形を作り、定義したワードを後で実行したときにstack effectが現れるワードです。

## stack操作、算術、論理、比較

| ワード | stack effect | 使用場所 | 意味 |
| --- | --- | --- | --- |
| `NOP` | `( -- )` | 解釈／compile | 何もしません。 |
| `DROP` | `( x -- )` | 解釈／compile | 最上段を捨てます。 |
| `DUP` | `( x -- x x )` | 解釈／compile | 最上段を複製します。 |
| `SWAP` | `( x1 x2 -- x2 x1 )` | 解釈／compile | 上の二つを交換します。 |
| `OVER` | `( x1 x2 -- x1 x2 x1 )` | 解釈／compile | 二番目を最上段へ複写します。 |
| `+` | `( x1 x2 -- sum )` | 解釈／compile | 32ビットcellとして加算します。 |
| `-` | `( x1 x2 -- difference )` | 解釈／compile | `x1-x2`を計算します。 |
| `*` | `( x1 x2 -- product )` | 解釈／compile | 32ビットcellとして乗算します。 |
| `AND` | `( x1 x2 -- x3 )` | 解釈／compile | bit単位ANDです。 |
| `OR` | `( x1 x2 -- x3 )` | 解釈／compile | bit単位ORです。 |
| `XOR` | `( x1 x2 -- x3 )` | 解釈／compile | bit単位排他的ORです。 |
| `<` | `( x1 x2 -- flag )` | 解釈／compile | 符号付きで`x1<x2`を調べます。 |
| `=` | `( x1 x2 -- flag )` | 解釈／compile | 二つのcellが等しいか調べます。 |

## メモリ、cell、文字

| ワード | stack effect | 使用場所 | 意味 |
| --- | --- | --- | --- |
| `@` | `( addr -- x )` | 解釈／compile | 32ビットlittle-endian cellを読みます。 |
| `!` | `( x addr -- )` | 解釈／compile | 許可された場所へcellを書きます。 |
| `C@` | `( c-addr -- char )` | 解釈／compile | 1 byteを読み、0拡張します。 |
| `C!` | `( char c-addr -- )` | 解釈／compile | 下位8 bitを書きます。 |
| `CELL+` | `( addr -- addr+4 )` | 解釈／compile | 32ビットcell一個分進めます。 |
| `CELLS` | `( n -- n*4 )` | 解釈／compile | cell数をbyte数へ変換します。 |
| `ALIGNED` | `( addr -- aligned-addr )` | 解釈／compile | addressを4 byte境界へ切り上げます。 |
| `CHAR+` | `( c-addr -- c-addr+1 )` | 解釈／compile | 文字1 byte分進めます。 |
| `CHARS` | `( n -- n )` | 解釈／compile | 文字数をbyte address単位へ変換します。 |

`!`はmemory backendの権限を回避できません。seal済みCODEは通常の`!`では書き換えられません。

## 辞書allocationとdata定義

| ワード | stack effect | 使用場所 | 意味 |
| --- | --- | --- | --- |
| `HERE` | `( -- addr )` | 解釈 | 次に使う辞書／data addressを返します。 |
| `,` | `( x -- )` | 解釈／定義ワード | 整列してcell一個を書き、`HERE`を進めます。 |
| `C,` | `( char -- )` | 解釈／定義ワード | 現在の`HERE`へ1 byteを書きます。 |
| `ALLOT` | `( u -- )` | 解釈／定義ワード | 0以上の`u` byteを予約して0で埋めます。 |
| `ALIGN` | `( -- )` | 解釈／定義ワード | `HERE`をcell境界へ進めます。 |
| `CONSTANT name` | `( x -- )` | 解釈 | 実行すると`x`を残す`name`を定義します。 |
| `VARIABLE name` | `( -- )` | 解釈 | 0のcellを定義し、`name`はaddressを残します。 |
| `CREATE name` | `( -- )` | 解釈／定義ワード | body addressを残すワードを定義します。 |

`CONSTANT`、`VARIABLE`、対話時の`CREATE`は、同じ入力の中に新しい名前が必要です。負の`ALLOT`は
拒否します。allocation失敗時は未完成の辞書変更をrollbackします。

```forth
123 CONSTANT ANSWER
VARIABLE SLOT
ANSWER SLOT !
SLOT @ .             \ 123を表示
```

## colon definitionと条件構造

| ワード | 実行時stack effect | 使用場所 | 意味 |
| --- | --- | --- | --- |
| `: name` | `( -- )` | 解釈 | hidden状態でcolon definitionを開始します。 |
| `;` | `( -- )` | compile専用 | 現在の定義を完成して公開します。 |
| `IF` | `( flag -- )` | 構造 | 真のとき次の部分を実行します。 |
| `ELSE` | `( -- )` | 構造 | 偽の場合の部分を開始します。 |
| `THEN` | `( -- )` | 構造 | `IF`または`ELSE`を閉じます。 |
| `BEGIN` | `( -- )` | 構造 | 不定回loopの開始位置です。 |
| `UNTIL` | `( flag -- )` | 構造 | 偽なら`BEGIN`へ戻ります。 |
| `AGAIN` | `( -- )` | 構造 | 無条件に`BEGIN`へ戻ります。 |
| `WHILE` | `( flag -- )` | 構造 | 偽なら`BEGIN ... REPEAT`を抜けます。 |
| `REPEAT` | `( -- )` | 構造 | `BEGIN`へ戻り`WHILE`を閉じます。 |

構造の対応が崩れた場合は定義を中止し、辞書とcompile済みCODE allocationを元へ戻します。

## 回数指定loop

| ワード | 実行時stack effect | 使用場所 | 意味 |
| --- | --- | --- | --- |
| `DO` | `( limit start -- )` | 構造 | 回数指定loopを開始します。同値開始は避けます。 |
| `?DO` | `( limit start -- )` | 構造 | startとlimitが同じならloopを飛ばします。 |
| `LOOP` | `( -- )` | 構造 | indexを1増やし、必要なら続けます。 |
| `+LOOP` | `( increment -- )` | 構造 | 符号付きincrementを加え、limit通過を調べます。 |
| `I` | `( -- index )` | 解釈／compile | 最も内側のloop indexを複写します。 |
| `J` | `( -- index )` | 解釈／compile | 一つ外側のloop indexを複写します。 |
| `LEAVE` | `( -- )` | 構造 | 最も内側の回数指定loopを抜けます。 |
| `UNLOOP` | `( -- )` | 解釈／compile | loop frameを一個明示的に外します。 |

参照上限は32 frame、移植可能な最低保証は8 frameです。必要なframeがない`I`、`J`、`UNLOOP`は
errorになります。

## 文字、文字列、数値出力

| ワード | stack effect | 使用場所 | 意味 |
| --- | --- | --- | --- |
| `.` | `( n -- )` | 解釈 | 符号付き10進数を表示し、`n`を取り除きます。 |
| `EMIT` | `( x -- )` | 解釈 | 下位1 byteを一文字として出力します。 |
| `CR` | `( -- )` | 解釈 | 論理的な改行を一つ出力します。 |
| `TYPE` | `( c-addr u -- )` | 解釈 | `u` byte全体を検査して一括出力します。 |
| `S" text"` | `( -- c-addr u )` | 解釈／compile | 引用byte列を保存またはcompileし、範囲を返します。 |
| `." text"` | `( -- )` | 解釈／compile | 引用byte列を出力し、compile時は検証済みSERVICE 1を使います。 |

引用文字列は現在1文字1 byte、U+0000からU+00FFです。移植可能な表示用部分集合はASCIIです。解釈時の
`.`、`EMIT`、`CR`、`TYPE`はhost wordであり、そのままcolon definitionへcompileできません。

## 定義ワード：`CREATE`と`DOES>`

| ワード | stack effect | 使用場所 | 意味 |
| --- | --- | --- | --- |
| `CREATE` | `( -- )` | 定義ワード本体の先頭 | 最初はbody addressを返す子ワードを作ります。 |
| `DOES>` | `( -- )` | 定義ワード構造 | constructor actionを終え、子の実行時behaviorを開始します。 |

```forth
: VALUE: CREATE , DOES> @ ;
123 VALUE: ANSWER
ANSWER .              \ 123を表示
```

現在の0.1では`CREATE`が定義ワード本体の最初でなければなりません。constructor actionは`,`、`C,`、
`ALLOT`、`ALIGN`に限ります。

## 動的な実行先の選択

| ワード | stack effect | 使用場所 | 意味 |
| --- | --- | --- | --- |
| `DEFER name` | `( -- )` | 解釈 | 最初は未割当ての動的call slotを作ります。 |
| `' name` | `( -- xt )` | 解釈 | `name`の辞書execution tokenを返します。 |
| `['] name` | `( -- xt )` | compile専用 | 実行時に`name`のexecution tokenを残すCODEをcompileします。 |
| `IS defer-name` | `( xt -- )` | build時の解釈 | `DEFER`ワードの選択先を設定します。 |
| `ACTION-OF defer-name` | `( -- xt )` | 解釈／compile | 現在選択されている飛び先tokenを返します。 |

未割当ての`DEFER`実行と`ACTION-OF`はerrorです。compile済み`IS`は既定の`safe-runtime`では拒否し、
明示的な`standard-build`実験だけで利用できます。Monitor接続後は通常の変更をlockし、認証済み切替えだけを残します。

## 調査

| ワード | stack effect | 使用場所 | 意味 |
| --- | --- | --- | --- |
| `WORDS` | `( -- )` | 解釈 | 起動時ワードと利用者の追加定義を分けて表示します。 |

`WORDS`は同名ワードの最新の検索可能な定義だけを表示します。hidden、失敗、rollbackされたentryは表示しません。

## 起動時ワードではない入力構文

- `123`のような10進数と`0x7B`のような16進数は一つのcellを積みます。
- `\`から行末まではcommentです。
- 引用文字列以外の入力は大文字・小文字を区別しません。
- `BYE`と`EXIT`はhost参照REPLを終了するlauncher commandであり、凍結したCORE wordではありません。

## 次に学ぶために

[FORTHの設計と学習のための参考資料](REFERENCES_JP.md)では、入門書から辞書、interpreter、小さなVM、
小規模MPU実装へ進むための読書順を案内しています。
