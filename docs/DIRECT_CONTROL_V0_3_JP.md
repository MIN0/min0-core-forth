# MIN0 CORE FORTH 直接制御構造設計 v0.3

[英語版はこちらです](DIRECT_CONTROL_V0_3.md)

状態：Python版とRuby版host referenceへ実装済みの実験仕様。

## 決定事項

直接入力で制御構造の開始ワードを検出しても、その場では終端がないと判断しない。対応する終端ワードまで
解析済みtokenを収集し、構造全体を検査してから実行する。この方式を`FOR ... NEXT`だけでなく、次へ拡張する。

```forth
flag IF true-part [ ELSE false-part ] THEN
BEGIN body flag UNTIL
BEGIN body AGAIN
BEGIN test WHILE body REPEAT
limit start DO body LOOP
limit start ?DO body LOOP
limit start DO body increment +LOOP
limit start ?DO body increment +LOOP
u FOR body NEXT
```

これらはcolon definition内では従来どおりbytecodeへcompileされ、直接入力ではbufferを使って実行される。

## 入力収集

- 開始ワードは`IF`、`BEGIN`、`DO`、`?DO`、`FOR`
- 対応する終端まで複数の入力行を収集する
- 収集中のpromptは`...> `とする
- 異なる種類を含む多重構造をLIFO stackで対応づける
- 最外側が閉じた後の同一入力行のtokenは、構造実行後に通常どおり処理する
- EOFで未完了なら、必要な終端を示してerrorにする

開始時の`flag`、`limit start`、`u`はDATA stackから一度取り出して収集状態に保存する。構造の検査が成功した
後に実行入力として戻す。このため、収集中のstack表示には開始引数を残さない。

## 実行と入れ子

収集後のtokenは直接制御用の構造木へ変換し、実行前に全分岐を検査する。直接構造の内部には別の直接構造を
入れられる。`I`は最内側、`J`は一つ外側の`DO`／`?DO`／`FOR` frameを参照する。

`LEAVE`は直接入力された`DO`、`?DO`、`FOR`の最内側から脱出でき、`IF`や`BEGIN`の内部に置いても、字句上
それらを囲む回数指定loopから脱出する。

## 安全上限とrollback

```text
token buffer       4096 token
direct execution  100,000 node／iteration単位
loop depth         VM設定値（通常32 frame）
```

`BEGIN ... AGAIN`、終了しない`UNTIL`、0 incrementの`+LOOP`、同値開始の通常`DO`なども実行上限で停止する。
収集、構造検査、実行のerrorでは、DATA stackとloop stackを最外側の直接構造を開始した入力blockの状態へ戻す。
すでに外部へ出した表示と完了済みmemory書込みはtransactional rollbackの対象外である。

## 対象外

`;`はcolon definitionの終端であり、直接構造の開始語ではない。`[']`は後続名をcompileする構文、`DOES>`は
定義ワード構造なので、直接入力用bufferの対象にしない。`UNLOOP`単独も直接構造ではなく、有効な実行文脈が
なければerrorである。

初期実装の直接本体は、数値、通常の実行可能な辞書word、host出力word、`."`、上記制御構造を許可する。
`S"`、DATA/source定義word、colon定義開始・終了は、別途semantics統一を行うまで拒否する。

## 以前の仕様との関係

この文書は`FOR_NEXT_DIRECT_V0_2_JP.md`の収集・上限・rollback方式を一般化する。`FOR ... NEXT`の回数、
0始まりindex、0回実行というsemanticsは変更しない。直接入力の`DO`系をerrorにする以前の規定は、本v0.3で
置き換える。
