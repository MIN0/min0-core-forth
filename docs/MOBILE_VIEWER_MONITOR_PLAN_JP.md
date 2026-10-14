# Mobile Learning／仮想アセンブラViewer 観察・Monitor改良計画

状態：`v0.1.4-rc.1`公開後の次期開発計画。公開済みreleaseの仕様ではない。

## 目的

利用者がFORTHまたは仮想アセンブラを実行したときに、開始前と終了後のstack、colon word内部、loop反復、
登録wordの意味を一つの画面で理解できるようにする。後半では、実行を継続したまま安全な停止点で状態を
観察・変更し、停止、step、継続できる学習用Monitorへ発展させる。

## 第1段階―実行前後のstackを明確にする

- 実行結果の先頭へ「実行前」「停止時」「復旧後または実行後」を常時表示する。
- 左をstack底、右をTOSとして明記する。
- 正常終了、error停止、rollback完了を色と文言で区別する。
- Mobile Learningと仮想アセンブラViewerで同じ用語と表示順を用いる。
- error時には、失敗した瞬間のstackと安全に復旧したstackを混同しない。

表示例：

```text
実行前  <3> 10 20 30
実行後  <2> 10 50
状態    正常終了 / 18 steps
```

## 第2段階―word番号と階層trace

sourceをcompileした順に、利用者定義wordへ実行ごとの通し番号を付ける。番号は各実行を新しいVMから
開始する現行仕様に合わせ、実行ごとに採番し直す。

```text
#1 SQUARE       colon word
#2 SUM-SQUARES  colon word
#3 COUNT-DOWN   colon word
#0 MAIN         定義後の直接実行部分
```

- `#0 MAIN`は最後の直接実行部分を表す。
- 画面でword番号を選ぶと、そのwordの呼出し一覧と内部traceを表示する。
- 同じwordが複数回呼ばれた場合は、word番号に加えて呼出し番号を選べるようにする。
- trace eventにはglobal sequence、word番号、invocation番号、call depth、source位置、token／opcode、
  実行前後stack、return stack、loop frame、出力差分を持たせる。
- 再帰呼出しはcall depthをtree表示する。
- primitive、colon、将来のCODE、未公開候補を種類として区別する。

## LOOPと繰返しの表示

loopを単純に全行表示すると画面とmemoryを圧迫するため、反復単位で折り畳む。

```text
DO ... LOOP  10回実行
├─ iteration 0  I=0
├─ iteration 1  I=1
├─ … 6回省略
├─ iteration 8  I=8
└─ iteration 9  I=9
```

- 初期表示は先頭2回、最後2回、反復回数、最終stackを示す。
- 利用者が選んだ反復だけを展開できる。
- nested loopでは`I`、`J`とloop depthを表示する。
- 実行step上限とは別にtrace event上限を持つ。
- trace上限を超えても実行結果を捨てず、「何件を省略したか」を記録する。
- 無限loopは既存step上限で安全停止し、最後に完了した反復と停止位置を示す。

## 第3段階―短いword説明

検索・分類できる「ワード辞典」を画面へ追加する。

- builtin word：名前、stack effect、短い日本語説明、利用可能な状態、関連word。
- 利用者定義word：通し番号、種類、stack effect comment、source、呼出し回数、最終入出力stack。
- `( n -- n2 )`形式の定義直後commentをstack effectとして抽出する。
- commentがない場合は推測で補わず「未記載」と表示する。
- `WORDS`表示と辞典の登録一覧が食い違わないよう、同じmetadataを使用する。

## 第4段階―バックグラウンド実行と学習用Monitor

現在の同期実行器を、途中で状態を保存して再開できるresumable state machineへ変更する。その後、実行器を
Web Workerへ移し、画面入力と実行を分離する。

追加候補word：

```forth
KEY?     ( -- flag )  入力queueに文字があるか確認する
KEY      ( -- char )  入力が届くまで安全にyieldする
YIELD    ( -- )       画面へ制御を一度返す
BREAK    ( -- )       承認済みMonitor停止点へ入る
```

画面操作：

- 実行
- 一時停止要求
- 1 step
- 継続
- 安全停止
- 入力queueへの文字送信
- 現在word、source位置、stack、loop indexの表示
- 変数一覧、選択、検査付き変更

## 安全規則

- 画面から実行中のJavaScript objectを直接書き換えない。
- 一時停止要求は命令境界または`YIELD`／`KEY`／`BREAK`で受理する。
- 変数変更は停止中だけ受け付け、型、範囲、書込み権限を確認してから反映する。
- `KEY`はbrowser threadをblockせず、入力待ち状態を保存してWorker event loopへ戻る。
- 「安全停止」は現在snapshotを観察可能にして停止する。「ABORT／rollback」は開始前snapshotへ戻す。
  二つを別操作・別表示にする。
- 自動yield間隔と1回の実行chunk上限を設け、sourceが`YIELD`を書かなくても画面操作を失わないようにする。
- Monitor変更はaudit eventとして、変更前、変更後、word、時刻順序を記録する。
- 小容量targetでは長い説明をViewer側へ移しても、停止理由、source位置、stack depth、復旧結果を残す。

## 実装順序

### Phase A―観察性（次回ここから開始）

1. Mobile Learning coreへtop-level／colon内部共通trace eventを追加する。
2. 実行前・停止時・実行後／復旧後stackを結果objectへ明示する。
3. word番号、`#0 MAIN`、invocation番号、call depthを追加する。
4. UIへword／invocation選択と階層traceを追加する。
5. loop反復の折り畳みとtrace上限を追加する。
6. ワード辞典metadataと検索UIを追加する。
7. Node.js試験、browser構造試験、iPhone表示確認を行う。

### Phase B―Monitor基盤

1. interpreterを1 instructionずつ再開可能なstate machineへ分離する。
2. Run／Pause／Step／Continue／Stopの状態遷移試験を作る。
3. Web Workerへ移し、message protocolを固定する。
4. `YIELD`と自動yieldを実装する。

### Phase C―入力と変数操作

1. `KEY?`と入力queueを実装する。
2. 非block型`KEY`待ちを実装する。
3. 学習subsetへ安全な`VARIABLE`、`@`、`!`を追加する。
4. 停止中の変数観察・検査付き変更を実装する。
5. `BREAK`とMonitor auditを追加する。

## Release方針

- Phase Aを次の評価候補として先に完成させる。
- Phase B／CをPhase Aへ無理に混ぜず、既存の同期実行を回帰試験として残す。
- 公開済み`v0.1.4-rc.1`のtagとassetは変更しない。
- RP2350実機実行、物理memory／IO、Pico 2 W live patchは本計画のbrowser段階へ含めない。

## 次回の最初の作業

`viewer/mobile-forth-core.js`のtraceを、top-level tokenだけでなく`executeDefinition`／`runCode`内部でも
記録できるevent形式へ変更する。その前に、現行source例とerror rollbackを固定する回帰試験を追加する。
