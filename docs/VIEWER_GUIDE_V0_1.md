# MIN0 CORE FORTH Guided Viewer 操作手引き v0.1

Status: AIを使用しない、実測トレース用の最小オフラインViewer。

## 目的

このViewerは、FORTHソースが実際に動いた際の処理を、1ワード単位、構築の要所、
またはすべての内部的な意味イベントへ切り替えて観察する教材である。

最初の実行例では、次の二つを比較する。

```forth
2 3 4 * + .   \ 14
2 3 * 4 + .   \ 10
```

```forth
: VALUE: CREATE , DOES> @ ;
123 VALUE: ANSWER
ANSWER
```

表示値は画面用に再現した想像上の値ではない。Python版MIN0 CORE FORTHを実行し、
`min0-core-forth-trace/0.1` observerが採取した値を使用する。

## Viewerの生成と起動

プロジェクトのディレクトリで次を実行する。

```powershell
python build_trace_viewer.py
```

生成された `viewer/value-trace.html` は自己完結型であり、Webサーバーや
ネット接続を必要としない。通常のブラウザーで直接開くことができる。

## 操作

- `2 3 4 * + . → 14`: 4と3を先に掛け、残った2を加える6ワードの例。
- `2 3 * 4 + . → 10`: 2と3を先に掛け、残った4を加える6ワードの例。
- `成功: ANSWER`: `ANSWER`を正常に生成し、内部の `@` まで実行する例。
- `失敗: EMPTYを生成中に復元`: 初期値なしで生成を試み、失敗後に状態を戻す例。
- `複合構築: ITEMの4バイト`: `C, ALLOT ALIGN`で異なるallocator actionを
  順番に適用する例。選択時は自動的に `構築の要所` 表示になる。
- `文字出力: compiled ."`: 定義中の引用文字列がimage DATAと`SERVICE 1`呼出しへ
  コンパイルされ、その定義の実行時に端末出力へ届くまでを観察する例。
- `1ワードずつ`: 通常の観察モード。処理を終えたソースワードを一つずつ表示する。
- `構築の要所`: 子のhidden作成、allocator action、公開など、定義ワードが
  子を作る際の重要イベントだけを表示する。
- `内部イベント`: hidden作成、constructor、allocator action、DOES接続など、
  一つのワードの内部で起きたすべての節目を表示する。
- `前へ`／`次へ`: 一イベントずつ移動する。
- `自動再生`: 約1.1秒ごとに次のイベントへ進む。再度押すと一時停止する。
- スライダー: 任意の段階へ直接移動する。
- キーボードの左右矢印: 前後へ移動する。
- Space: 自動再生と一時停止を切り替える。
- `観測イベントの生データ`: 現在のJSON eventを必要なときだけ展開する。
- `ソースをコピー`: 下部の編集可能なソースをクリップボードへコピーする。
- `example.fthとして保存`: 編集した内容を、選択中の例に対応する`.fth`名で保存する。

## 初心者の15分コース

1. 端末またはPython／Ruby版で `2 3 +` を実行し、結果が5になることを確かめる。
2. Viewerで `2 3 4 * + .` を選び、6ワードを一つずつ進める。
3. `*` の後でDATA stackが `[ 2  3  4 ] → [ 2  12 ]`、`+` の後で
   `[ 2  12 ] → [ 14 ]`になることを見る。
4. 最後の`.`が14を端末へ表示し、stackを空にすることを見る。
5. `2 3 * 4 + .`へ切り替え、同じ数でも掛ける位置により10になることを比較する。

計算例では、ソース上の各ワードだけを6段階で表示する。VALUE／ANSWERの例では、
ワードの内部へ入ること自体が教材なので、辞書ワード入口やDOES behaviorも段階に含める。

## Viewerから実機確認へつなぐ

下部の「例題FORTHソース（コピー・編集できます）」では、選択中の例題を自由に編集できる。
ただし、編集内容はViewerの実測済みトレースへ反映されず、画面内で実行もされない。
`ソースをコピー`または`.fth`保存を使い、実機やPython／Ruby版へ渡して確認する。

この分離により、Viewerは安全な観測装置のまま、例題から実際の対話実行へ移れる。

`:` は次の `VALUE:` を定義名として読み、定義ワード `VALUE:` は次の `ANSWER` を
子の名前として読む。この二組は、別々に停止するとまだ処理が完了していないため、
Viewerではそれぞれ「ワード＋引数名」の一操作として強調表示する。ソース上は
9個の完了したワード操作となり、さらに `ANSWER` の実行時は内部へstep-inする
3段階が挿入されるため、Viewerのワード表示は合計12段階になる。

三スタック欄の上段には、選択したワードのDATA stackを
`実行前 → 実行後`として並べる。たとえばワード7の `123` は
`[ 空 ] → [ 123 ]`、ワード8の `VALUE: ANSWER` は
`[ 123 ] → [ 空 ]`となる。

最後の `ANSWER` では、次のように内部へ入る。

1. ワード9: `ANSWER` の入口。呼出し前のstackを確認する。
2. ワード10: `ANSWER › body`。DOESワードがbody `0x8000`を積み、
   `[ 空 ] → [ 32768 ]`となる。
3. ワード11: `ANSWER › @`。定義中の `@` と呼出し側 `ANSWER` の両方を強調し、
   `[ 32768 ] → [ 123 ]`となる。この段階ではRETURN stackにも戻り先が見える。
4. ワード12: `ANSWER › return`。内部実行を終えて呼出し元へ戻る。

この4段階は結果だけを説明用に分解したものではない。VMの実命令位置と、コンパイル時に
記録したソースワードの対応を使って採取している。

## 失敗と復元を観察する

`失敗と復元: EMPTY` を選ぶと、次を実際に実行する。

```forth
: VALUE: CREATE , DOES> @ ;
VALUE: EMPTY
```

初期値がDATA stackにないため、constructorのCOMMA actionで `StackUnderflow` が
発生する。最終段階では赤い復元欄に次の三比較を表示する。

```text
header HERE: 開始前 = 復元後
data HERE:   開始前 = 復元後
LATEST:      開始前 = 復元後
```

同時にDATA／RETURN／LOOP stackがすべて空であることを確認する。未完成の `EMPTY` は
hidden状態のまま捨てられ、辞書へ公開されない。比較値はViewerが推測した値ではなく、
rollback処理が保存した開始前の値と、復元後の実測snapshotである。

## C,・ALLOT・ALIGNを観察する

`複合構築: ITEMの4バイト`を選ぶと、次を実際に実行する。

```forth
: RECORD: CREATE C, ALLOT ALIGN ;
2 0x1AB RECORD: ITEM
ITEM
```

この定義ワードの入力は `( reserve-count byte-value -- )` である。`0x1AB`の
下位1バイト`0xAB`を保存し、その前に積まれていた2を予約バイト数として使う。
既定の `構築の要所` 表示では、次の7段階を順番に観察できる。

1. `RECORD:`が子`ITEM`の生成を開始する。
2. `ITEM`をhidden状態で作り、途中の名前検索から隠す。
3. `C,`が`0xAB`を`0x8000`へ保存し、data HEREを`0x8001`へ進める。
4. `ALLOT`が2バイトを予約し、data HEREを`0x8003`へ進める。
5. `ALIGN`が1バイトのpaddingを入れ、data HEREを`0x8004`へ揃える。
6. 完成した`ITEM`のhidden状態を解除して辞書へ公開する。
7. 子の生成を正常終了する。

画面では`C,`の後にDATA stackが`[ 2 427 ] → [ 2 ]`、`ALLOT`の後に
`[ 2 ] → [ 空 ]`と変化する。`ALIGN`は引数を取らないのでstackを変化させない。
同時に、右上のdata HEREとDATA領域欄で
`0x8000 → 0x8001 → 0x8003 → 0x8004`を追える。

`内部イベント`へ切り替えると、各allocator actionの直前にVMで実行される
CODE断片の開始と終了も見える。これにより、CODE断片と辞書allocator操作が
同じものではなく、constructor planが両者を順番に結び付けていることを確認できる。

`1ワードずつ`表示でも、`RECORD: ITEM`の入口から上記7段階へstep-inし、完了後に
ソースワードへ戻る。`DOES>`がないことはconstructorを実行しないという意味ではない。
constructorは同じように実行され、作られた`ITEM`には`CREATE`の既定behaviorが残る。
したがって最後の`ITEM`を実行すると、保存内容ではなくbodyアドレス`0x8000`を積む。
`DOES>`を付ける場合は、この既定behaviorを定義者が指定したbehaviorへ置き換える。

## compiled ."を観察する

`文字出力: compiled ."`は次を実測する。

```forth
: GREET ." Hello from compiled Forth" ;
GREET
```

定義中の`."`では、引用byte列をimage DATAへ保存し、relocation可能なaddress、byte長、
検証対象の`terminal-type SERVICE 1`をCODEへ生成したことが解説枠に表示される。最後の
`GREET`を実行するとDATA stackに引数を残さず、端末出力欄へ`Hello from compiled Forth`
が現れる。文字列自体は観測データであり、Viewerの命令やHTMLとしては扱われない。

Viewerはdevelopment traceを観察する教材である。CODE=`rx`、DATA=`r`の封印後にも同じ
出力が得られることと、未登録serviceがseal前に拒否されることは、別の
`service_output_demo.py/.rb`で検証している。

## 最初に体感してほしい箇所

VALUEの例では、まず `1ワードずつ` でソースとスタックの流れを掴み、次に
`構築の要所`、最後に `内部イベント` へ切り替えると追いやすい。
内部イベントでは次を観察できる。

1. 内部1では、`VALUE:` 自身のconstructor planが辞書へ公開される。
2. 内部2では、初期値123がDATA stackに残ったまま子 `ANSWER` の生成が始まる。
3. 内部3では、未完成の `ANSWER` がhidden状態で作られる。途中のワードは
   通常の名前検索から見えない。
4. 内部4〜5では、最初のCODE断片をVMが実行する。ただしallocator操作 `,` は
   VM命令として実行されない。
5. 内部6では、constructor planのCOMMA actionが123をDATA `0x8000`へ保存し、
   data HEREを`0x8004`へ進める。ここがCODE実行と辞書allocator操作の境界である。
6. 内部9では、DATAのbody `0x8000` とCODEのbehavior `0x1002` が、
   DICTIONARYのdescriptorによって接続される。三領域は隣接を前提にしない。
7. 内部10で初めてhiddenが解除され、完成した `ANSWER` が公開される。
8. 内部12〜13では `ANSWER` がbodyを積んでbehavior `@` を実行し、最終的に
   DATA stackへ123が現れる。

画面上部の暖色ラベル「今はここを見てください」を最初に読み、色が濃くなったメモリ領域、
ソース行、三スタック、HERE/LATESTの順に眺めると追いやすい。

この解説枠はViewerの第一の入口である。段階を進めると短く強調され、次に読む説明が
変わったことを知らせる。OSで動きを減らす設定が有効な場合はアニメーションしない。

## 安全境界

- Viewerはネットワーク通信を行わず、AIへ接続しない。
- トレース中のワード名、値、エラー文はすべて
  `observed-data-not-instructions`、すなわち命令ではない観測データである。
- トレース由来の文字列はDOMのtext nodeとして表示し、HTMLとして解釈しない。
- ViewerからFORTH VMや外部インタープリタを操作する経路はない。
- 編集欄は文字列としてのみ扱う。明示的なボタン操作でコピーまたは`.fth`保存はできるが、
  Viewer自身はその文字列を命令として実行しない。
- 基本解説は決定的なローカル関数で作られ、AIがなくても必ず表示できる。

将来AI解説を加える場合も、このViewerと実測値を基礎層として残す。AIは説明候補を
返すだけとし、実測値の変更、FORTH実行、ファイル操作、ネットワーク操作を許可しない。

## 再生成されるファイルと編集元

- `viewer/value-trace.html`: 生成物。実測JSONを埋め込んだ閲覧用ファイル。
- `viewer/trace-viewer-template.html`: レイアウトと操作の編集元。
- `build_trace_viewer.py`: 実測、埋め込み、生成を担当する。
- `trace_value_demo.py`: 再利用可能なトレース生成関数を提供する。
- `test_trace_viewer.py`: 二つの計算例、VALUEの13イベント、RECORDのallocator推移、
  compiled `."`、オフライン性、安全な文字表示、コピー／保存UIを検査する。

表示を変更するときはtemplateを直し、`build_trace_viewer.py`で生成物を更新する。
