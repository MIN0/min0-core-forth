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

### 停止位置と呼出し履歴の表示

Pause、`BREAK`、`KEY`待ち、安全停止で実行が止まったときは、data stackだけでなく「どこで止まり、
どのwordから呼ばれて現在位置へ来たか」を確認できなければならない。画面には独立した
「実行位置／呼出し履歴」paneを設け、必要なら別窓へpop-outできるようにする。

```text
停止理由：Pause要求（instruction境界で受理）
現在位置：#7 FILTER-SAMPLE  invocation 12  token 18/31  source 9:14

呼出し履歴（新しいframeが上）
→ #7 FILTER-SAMPLE   return: #5 READ-SENSOR token 24
  #5 READ-SENSOR     return: #2 SAMPLE-LOOP token 11
  #2 SAMPLE-LOOP     return: #0 MAIN token 6
  #0 MAIN            entry
```

- frameを選ぶと、そのwordのsource、停止token、呼出しtoken、data stack snapshot、loop frameを表示する。
- 再帰では同じword名でもinvocation番号とcall depthで区別する。
- return stackにはreturn先だけでなくloop制御値などが入る場合があるため、全cellをアドレスと推測しない。
  `CALL_RETURN`、`LOOP_FRAME`、`EXCEPTION_FRAME`などの型付きframeとして保持・表示する。
- Mobile Learningでは生のmemory addressを持たないため、`wordId`、`invocationId`、token index、source位置を
  論理return addressとして保存する。
- native targetでは停止snapshotのreturn addressをsymbol／word range mapへ照合し、word名とoffsetを表示する。
  対応表にない値はword名を捏造せず、`unknown address`として16進表示する。
- Pauseを受理したinstruction境界のsnapshotだけをUIへ渡し、実行中に変化しているstackを直接読まない。
- 継続後も直前の停止snapshotを履歴として残し、「現在実行中の状態」と混同しない表示にする。
- trace上限で古いeventを省略しても、現在のcall chainと再開に必要なreturn frameは失わない。

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

2026-10-15進捗：項目1の共通trace eventを実装した。`#0 MAIN`、definition、colon内部を区別し、
colon eventにはword名、invocation ID、call depth、instruction位置、実行前後stack、return／loop stack、
出力差分、成功／errorを記録する。入れ子colon wordと、stackを壊さず失敗する`/MOD`の回帰試験を追加した。
画面の表でも場所、呼出し番号、内部命令、errorを確認できる。

同日の次段階で、利用者定義wordへ`#1`からの通し番号を付け、各traceにsource行・列を追加した。
traceは既定2000件を上限とし、先頭半分と末尾半分を保持して中間の省略件数を表示する。これにより、
長いloopでもmemory使用量を固定しながら停止直前のeventを残す。loopを反復単位でまとめる表示、
word／invocation選択UI、短いワード辞典は未実装であり、次の作業とする。

さらにword番号とinvocation番号による表示選択UIを追加した。LOOP frameには固有loop ID、nest depth、
反復番号を持たせ、既定表示では各loopの先頭2反復と末尾2反復を残して中間を1行へ折り畳む。
「LOOPの全反復を表示」で展開でき、各eventにはloop ID、反復番号、`I`の値を表示する。
入れ子loopは異なるloop IDで区別される。残るPhase Aの中心は、より詳細なword／invocation階層表示と
短いワード辞典metadata／検索UIである。

続いてbuiltin／制御wordの共有metadataと検索可能なワード辞典UIを追加した。名前、分類、stack effect、
短い説明、利用可能な局面を表示する。利用者定義wordでは定義名直後の`( ... -- ... )`commentを抽出し、
通し番号、source、呼出し回数、直近の入出力stackも表示する。commentがなければ推測せず「未記載」とする。
`WORDS`も同じbuiltin metadataを名前一覧の正本として利用する。

さらに実行状態を、正常時は「実行前→正常終了後」、error時は「実行前→エラー停止時→安全復旧後」として
結果objectと画面の両方で分離した。error発生時は停止stackと辞書・word情報を診断用結果へ保存した後、
VM内部のstack、loop／return状態、辞書を実行前snapshotへrollbackする。従来の`dataStack`は互換性のため
error停止時を返し、新しい`finalDataStack`は安全復旧後を返す。端末へすでに表示した文字は外部作用なので
取り消せないことも画面へ明記する。残るPhase AはPC／iPhoneでの実画面確認と最終評価である。

2026-10-15、Windows PCの自己完結Mobile Viewerで正常例`2 3 +`とerror例`7 0 /MOD`を利用者が
目視確認し、問題なしと判定した。Phase AのPC実装・自動試験・PC画面確認は完了とする。iPhoneでの
同一表示確認は次の評価版を配置するときに行い、Phase Bはこの確認を待たず設計・実装を開始できる。

### Phase B―Monitor基盤

1. interpreterを1 instructionずつ再開可能なstate machineへ分離する。
2. Run／Pause／Step／Continue／Stopの状態遷移試験を作る。
3. return stackを型付きframe化し、現在word、caller、logical return位置を停止snapshotへ保存する。
4. 「実行位置／呼出し履歴」paneとframe選択表示を追加する。
5. Web Workerへ移し、停止snapshotを含むmessage protocolを固定する。
6. `YIELD`と自動yieldを実装する。

2026-10-15進捗：Run／Pause／Step／Continue／Stop／Abortの状態遷移を
`docs/MOBILE_MONITOR_STATE_MACHINE_R0_JP.md`へ固定し、VMから独立した
`viewer/mobile-monitor-state.js`と回帰試験を追加した。Pause、Stop、Abortの要求は次の命令境界で受理し、
Stepは1命令後に再停止する。Stopは現在snapshotを保持し、Abortは開始前snapshotへ復旧する。
続いて`viewer/mobile-forth-session.js`へtop-level／colon内部を1命令ずつ進める実行cursorを分離し、
この状態機械へ接続した。同期実行と算術、colon、分岐、LOOP、再帰の結果・出力・step数が一致し、実際の
FORTH sourceでPause→Step→Continue、Stop、Abort、error観察後Abortを確認した。次はbrowser event loopへ
制御を返すchunk schedulerを追加し、その後Viewerの操作ボタンへ接続する。

さらに`viewer/mobile-forth-scheduler.js`を追加し、1 chunkの命令数を制限してchunk間でbrowser event loopへ
制御を返すようにした。fake schedulerで無限LOOPを動かしながらPause、Step、Continue、Stopを受理し、
全chunkが設定上限以内であることを確認した。Abortでは途中辞書とstackを復旧し、出力済み文字は保持した。
続いてschedulerを自己完結Mobile Viewerへ接続した。Run／Pause／Step／Continue／Stop／Abort、状態、
実行前／現在／error停止時stack、現在word・命令位置、型付きcall frame、chunk進捗を表示する。実行中は
source編集と再Runを無効化し、traceとワード辞典はPauseなどの確定停止点で更新する。次はPC画面確認後、
Web Workerへの分離とmessage protocol固定へ進む。

2026-10-15、利用者がPCで画面操作を確認し、問題なしと判定した。Worker通信規約R0、message validator、
session／schedulerへ接続するWorker engineを追加した。commandはsession IDと厳密な連番で検査し、古いsession、
再送、順序違反、状態に合わない操作を実行せず`rejected`として返す。fake message port試験まで完了した。
次は自己完結HTML内にWorker sourceを組み立て、Blob Workerを起動するbrowser adapterを追加する。

続いてBlob Worker clientを追加し、自己完結HTMLへWorker sourceを埋め込んだ。画面はWorker client経由で
commandを送り、session ID不一致と重複・逆行eventを破棄する。Worker作成不可の場合は同じengineを使う
main-thread互換モードへ移る。埋込みsourceはNode.jsの実Worker threadで`2 3 +`を実行し、stack `[5]`を
返すことを確認した。次はPCブラウザで実際の「Worker分離モード」と6操作を目視確認する。

2026-10-15、利用者がPC画面で無限LOOPのchunk進行、現在位置、`CALL_RETURN`履歴と6操作を確認し、
問題なしと判定した。Blob Worker版のPC実装・自動試験・実画面確認は完了した。次はGitHub Pages用評価版を
準備し、iPhone Safariで同じ操作と表示を確認する。

2026-10-17、GitHub Pages上のiPhone Safari実機試験で`Worker分離モード`を確認した。正常加算、0除算の
安全なerror停止、無限LOOPのRun／Pause／Step／Continue／Stop／Abort、`SPIN`の現在位置、
`CALL_RETURN`履歴、実行前stackへの復旧がすべて期待どおり動作した。これによりPhase BのPC／iPhone
実画面確認を合格とする。確認用PDFが命令履歴2000行により79ページになったため、印刷時は実行状態と
呼出し履歴を残し、詳細traceとword辞典表を省略する。画面上の情報は省略しない。

### Phase C―入力と変数操作

1. `KEY?`と入力queueを実装する。
2. 非block型`KEY`待ちを実装する。
3. 学習subsetへ安全な`VARIABLE`、`@`、`!`を追加する。
4. 停止中の変数観察・検査付き変更を実装する。
5. `BREAK`とMonitor auditを追加する。

2026-10-17、Phase Cの最初の小単位として、最大256 UTF-8 byteのtransactional入力queue、非消費型
`KEY? ( -- flag )`、Worker protocol 0.2の`input` commandを追加した。まだ待機型`KEY`と画面入力欄は
未実装である。次はWorkerをblockしない`waiting-input`停止点を定義する。

続いて`KEY ( -- byte )`、`waiting-input`停止点、入力後のRun／Step復帰、待機中のPause／Stop／Abort、
Viewer入力欄、送信button、queue byte数表示を追加した。空queueでは命令位置とstep数を進めず、次chunkも
予約しない。

同日、PC Viewerで例題`実行中の入力（KEY）`を目視確認した。`A`送信後に数値`65`と文字`A`を表示し、
6 stepsで正常終了、実行前後のstackはともに`<0>`、入力queueは0へ戻った。基本的な`KEY`待機・消費・
終了処理を合格とする。続いてPause中入力、複数回入力、容量超過、Stop／Abortの自動回帰試験を追加し、
すべて合格した。Viewerには例題`2文字入力（Pause確認）`を追加した。次は同じ操作をPC画面で確認する。

PC画面では容量超過の拒否と入力待ち維持、入力待ち中の安全停止、実行前復旧を確認し、3項目を合格とした。
残る画面確認はPause中の`AB`送信、Pause維持、Continue後の`AB`出力とqueue 0である。

最初の`AB`画面確認では最終出力とstackは正しかったが、Pause確定を待つ操作が分かりにくく、sourceだけを
消す「消去」も画面初期化と誤解しやすかった。Pause要求中は入力を無効化して確定待ちを表示し、buttonを
「ソースを消去」と「画面を初期化」へ分離した。改善版でPause維持と全体初期化を再確認する。

## Release方針

- Phase Aを次の評価候補として先に完成させる。
- Phase B／CをPhase Aへ無理に混ぜず、既存の同期実行を回帰試験として残す。
- 公開済み`v0.1.4-rc.1`のtagとassetは変更しない。
- RP2350実機実行、物理memory／IO、Pico 2 W live patchは本計画のbrowser段階へ含めない。

## 次回の最初の作業

Phase Cの残るPC画面確認として、Pause中入力、複数回入力、容量超過、Stop／Abortを確認する。合格後に
iPhone評価版を準備し、同じ入力待ちと復旧をSafariで確認する。公開済みreleaseはPhase Cの評価合格まで
変更しない。
