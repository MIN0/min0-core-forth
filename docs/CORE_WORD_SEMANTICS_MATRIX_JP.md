# 起動時65 wordのsemantics監査表

[英語版はこちらです](CORE_WORD_SEMANTICS_MATRIX.md)

状態：2026-09-14時点のPython／Ruby実装を反映した監査記録。

この表では、promptでsourceを読むときのinterpretation semanticsと、`: name ... ;`内でsourceを読むときの
compilation semanticsを分ける。「実装済み」は両実装とtestで確認済み、「文脈依存」は必要な構造やframeが
なければerror、「要検討」は現在の制限をCOREの最終仕様としてまだ承認していないことを表す。

## コメントと通常primitive

| word | interpretation semantics | compilation semantics | 状態・必要context |
| --- | --- | --- | --- |
| `(` | 次の`)`までsourceを読み飛ばす。 | 同じ。CODEは生成しない。 | 標準／CF互換。未終了はerror。 |
| `\` | 物理行末まで読み飛ばす。 | 同じ。CODEは生成しない。 | 標準的な行comment。 |
| `NOP` | 何もしない。 | `NOP` opcodeを生成する。 | 実装済み。 |
| `DROP` | 最上位cellを捨てる。 | `DROP` opcodeを生成する。 | 実装済み。 |
| `DUP` | 最上位cellを複製する。 | `DUP` opcodeを生成する。 | 実装済み。 |
| `SWAP` | 上位2 cellを交換する。 | `SWAP` opcodeを生成する。 | 実装済み。 |
| `OVER` | 2番目のcellを複写する。 | `OVER` opcodeを生成する。 | 実装済み。 |
| `+` | 32-bit加算を行う。 | `ADD` opcodeを生成する。 | 実装済み。 |
| `-` | 32-bit減算を行う。 | `SUB` opcodeを生成する。 | 実装済み。 |
| `*` | 下位32 bitの積を返す。 | `MUL` opcodeを生成する。 | 実装済み。double-cell積は将来課題。 |
| `AND` | bit ANDを行う。 | `AND` opcodeを生成する。 | 実装済み。 |
| `OR` | bit ORを行う。 | `OR` opcodeを生成する。 | 実装済み。 |
| `XOR` | bit XORを行う。 | `XOR` opcodeを生成する。 | 実装済み。 |
| `<` | 符号付き比較結果を返す。 | `LESS` opcodeを生成する。 | 実装済み。 |
| `=` | cellの等値結果を返す。 | `EQUAL` opcodeを生成する。 | 実装済み。 |
| `@` | 1 cellを読む。 | `FETCH` opcodeを生成する。 | memory権限検査あり。 |
| `!` | 1 cellを書く。 | `STORE` opcodeを生成する。 | memory権限検査あり。 |
| `C@` | 1 byteを0拡張して読む。 | `C_FETCH` opcodeを生成する。 | 実装済み。 |
| `C!` | 下位8 bitを書く。 | `C_STORE` opcodeを生成する。 | 実装済み。 |
| `CELL+` | addressを4進める。 | `CELL_PLUS` opcodeを生成する。 | 32-bit reference profile。 |
| `CELLS` | cell数をbyte数へ変換する。 | `CELLS` opcodeを生成する。 | 32-bit reference profile。 |
| `ALIGNED` | 4-byte境界へ切り上げる。 | `ALIGNED` opcodeを生成する。 | 32-bit reference profile。 |
| `CHAR+` | character addressを1進める。 | `CHAR_PLUS` opcodeを生成する。 | 1 character address unit = 1 byte。 |
| `CHARS` | character数をaddress unitへ変換する。 | `CHARS` opcodeを生成する。 | 現profileでは値を変えない。 |
| `I` | 最内loop indexを複写する。 | `I` opcodeを生成する。 | 活動中のloop frameが必要。 |
| `J` | 一つ外側のloop indexを複写する。 | `J` opcodeを生成する。 | 2個以上のloop frameが必要。 |
| `UNLOOP` | 最内loop frameを外す。 | `UNLOOP` opcodeを生成する。 | 実行時loop context依存。直接buffer内は未対応。 |

## 出力、文字列、調査

| word | interpretation semantics | compilation semantics | 状態・必要context |
| --- | --- | --- | --- |
| `.` | 符号付き10進数を出力する。 | `SERVICE 3 terminal-dot-v0.1`を生成する。 | 直接／compile一致を実装済み。 |
| `EMIT` | 下位8 bitを一文字出力する。 | `SERVICE 2 terminal-emit-v0.1`を生成する。 | CFと同じsource上の利用範囲。 |
| `CR` | 論理改行を出力する。 | `SERVICE 4 terminal-cr-v0.1`を生成する。 | DATA stackを一時使用しない。 |
| `TYPE` | byte範囲を検査して一括出力する。 | `SERVICE 1 terminal-type-v0.1`を生成する。 | fault時に引数と既存出力を保存。 |
| `S"` | byte列をDATAへ置き、addressと長さを返す。 | relocated DATA addressと長さの`LIT`を生成する。 | U+0000..U+00FF。 |
| `."` | 引用byte列を直ちに出力する。 | address、長さ、`SERVICE 1`を生成する。 | 実装済み。 |
| `WORDS` | 可視辞書wordを分類表示する。 | 現在は拒否する。 | TOOLS系。compile semanticsは要検討。 |

## allocationと定義word

| word | interpretation semantics | compilation semantics | 状態・必要context |
| --- | --- | --- | --- |
| `HERE` | 次のDATA allocation addressを返す。 | 現在は拒否する。 | 通常実行wordとしてcompile対応を要検討。 |
| `,` | cellを格納して`HERE`を進める。 | `CREATE`後のconstructor actionだけ対応。 | 一般compile semanticsは要検討。 |
| `C,` | byteを格納して`HERE`を進める。 | `CREATE`後のconstructor actionだけ対応。 | 一般compile semanticsは要検討。 |
| `ALLOT` | 非負byte数を予約する。 | `CREATE`後のconstructor actionだけ対応。 | 一般compile semanticsは要検討。 |
| `ALIGN` | `HERE`をcell境界へ進める。 | `CREATE`後のconstructor actionだけ対応。 | 一般compile semanticsは要検討。 |
| `CONSTANT` | 後続名を読み、stack値を返すwordを作る。 | 現在は拒否する。 | 実行時source解析との関係を要設計。 |
| `VARIABLE` | 後続名を読み、zero cellを持つwordを作る。 | 現在は拒否する。 | 実行時source解析との関係を要設計。 |
| `CREATE` | 後続名を読み、body addressを返すwordを作る。 | 定義word本体の先頭でconstructorを開始する。 | MIN0 v0.1制約付きで実装済み。 |

## 定義delimiterと制御構造

| word | interpretation semantics | compilation semantics | 状態・必要context |
| --- | --- | --- | --- |
| `:` | 後続名を読み、hidden colon definitionを開始する。 | 入れ子の`:`は拒否する。 | `;`までcompile状態を保持。 |
| `;` | 未完成定義がなければerror。 | `EXIT`を生成し定義を公開する。 | 対応する`:`が必要。 |
| `IF` | `THEN`まで収集後、flagで分岐実行する。 | 未解決zero-branchを生成する。 | 直接入力／定義内とも実装済み。 |
| `ELSE` | 直接`IF`収集中の代替部を開始する。 | `IF`をpatchし、end branchを生成する。 | 対応する`IF`が必要。 |
| `THEN` | 直接`IF`を閉じ、収集blockを実行する。 | `IF`／`ELSE` branchをpatchする。 | 対応する`IF`が必要。 |
| `BEGIN` | 終端まで直接入力を収集する。 | loop開始addressを記録する。 | `UNTIL`／`AGAIN`／`WHILE ... REPEAT`が必要。 |
| `UNTIL` | flagが偽なら直接`BEGIN`を反復する。 | conditional backward branchを生成する。 | 対応する`BEGIN`が必要。 |
| `AGAIN` | 直接`BEGIN`を無条件反復する。 | unconditional backward branchを生成する。 | 実行step上限あり。 |
| `WHILE` | 直接`BEGIN ... REPEAT`の継続条件を処理する。 | 未解決loop-exit branchを生成する。 | `BEGIN`と`REPEAT`が必要。 |
| `REPEAT` | 直接`BEGIN ... WHILE`を閉じる。 | backward branchとexit patchを生成する。 | 対応する`BEGIN WHILE`が必要。 |
| `DO` | `LOOP`／`+LOOP`まで収集して回数loopを行う。 | `DO` opcodeとcompile構造記録を生成する。 | 同値開始は長時間loopになる。 |
| `?DO` | start=limitなら0回、それ以外は直接loopする。 | `QDO`とexit patchを生成する。 | 実装済み。 |
| `LOOP` | 直接`DO`／`?DO`を閉じる。 | indexを1増やすbackward loopを生成する。 | 対応する`DO`系が必要。 |
| `+LOOP` | increment付きで直接`DO`／`?DO`を閉じる。 | `PLOOP`とbackward targetを生成する。 | 非zeroの符号付きincrementを推奨。 |
| `FOR` | `u`回、index 0から直接反復する。 | `LIT 0`と`QDO`を生成する。 | CF-inspired MIN0拡張。 |
| `NEXT` | 直接`FOR`を閉じる。 | `LOOP`を生成する。 | 対応する`FOR`が必要。 |
| `LEAVE` | 最内の直接counted loopを抜ける。 | 最内loopのexit patchを生成する。 | counted-loop contextが必要。 |

## execution tokenと動的call

| word | interpretation semantics | compilation semantics | 状態・必要context |
| --- | --- | --- | --- |
| `DEFER` | 後続名を読み、未割当てcall slotを作る。 | 現在は拒否する。 | 実行時source解析との関係を要設計。 |
| `'` | 後続名を読み、その`xt`を返す。 | 現在は拒否する。 | `[']`との役割分担を標準／CF比較して確定する。 |
| `[']` | 直接入力ではcontext error。 | 後続名の`xt`を残す`LIT`を生成する。 | compile専用構文として実装済み。 |
| `IS` | 後続DEFER名のtargetを設定する。 | `standard-build`だけ`DSET`を生成する。 | `safe-runtime`では意図的に変更禁止。 |
| `ACTION-OF` | 後続DEFER名の現在target `xt`を返す。 | DEFER slotを読むCODEを生成する。 | 未割当てはerror。 |
| `DOES>` | 直接入力ではcontext error。 | constructorを閉じ、子word behaviorを開始する。 | 先行する定義内`CREATE`が必要。 |

## 監査結果

- `. EMIT CR TYPE`の無理由なcompile制限は解消した。
- `WORDS`とallocation／source定義wordには、まだ要検討のcompilation semanticsがある。
- 制御wordの直接入力はbuffer、定義内はbytecode生成という二つの経路を持つが、実行結果を一致させる。
- `I J UNLOOP LEAVE`のerrorはword不在ではなく、必要なloop context不在として扱う。
- 今後wordを追加するときも、この表と同じ三semanticsおよびcontextを定義してから実装する。
