# Mobile Learning Monitor実行状態機械 R0

状態：Phase Bの実装契約。公開済み`v0.1.4-rc.1`の仕様ではない。

## 目的

同期実行器を途中停止・再開可能にするとき、画面操作とVM内部状態を直接結び付けない。利用者の要求は
いったん状態機械へ渡し、FORTH命令を一つ完了した境界でだけ確定snapshotを作る。

## 状態

| 状態 | 意味 |
|---|---|
| `idle` | 未開始 |
| `running` | 命令を継続実行中 |
| `pause-requested` | Pause要求済み。現在の命令完了を待つ |
| `paused` | 命令境界で停止。ContinueまたはStepが可能 |
| `stepping` | ちょうど1命令を実行中 |
| `stop-requested` | 安全停止要求済み。次の命令境界を待つ |
| `stopped` | 現在snapshotを保持して終了 |
| `abort-requested` | rollback要求済み。次の命令境界を待つ |
| `aborted` | 開始前snapshotへ復旧して終了 |
| `completed` | 正常終了 |
| `failed` | error停止。停止時snapshotを保持 |

## 操作の意味

- **Run**：開始前snapshotを保存し、`idle`から`running`へ移る。
- **Pause**：`running`から要求状態へ移る。実行途中のJavaScript objectは読まず、次の命令境界で`paused`になる。
- **Continue**：`paused`から`running`へ戻る。
- **Step**：`paused`から1命令だけ実行し、次の命令境界で再び`paused`になる。
- **Stop**：次の命令境界で現在snapshotを保存し、`stopped`になる。開始前へは戻さない。
- **Abort**：次の命令境界で開始前snapshotへrollbackし、`aborted`になる。すでに停止境界にいる場合は即時復旧する。
- **Error**：失敗した命令境界のsnapshotを保持して`failed`になる。観察後にAbortを選べる。

## StopとAbortの違い

```text
開始前 [10]
  ↓ 実行
停止時 [10 20]

Stop  → [10 20]を保持して終了
Abort → [10]へ復旧して終了
```

端末出力や外部IOはsnapshotだけでは巻き戻せない。Abortが保証するのは、最初はMobile Learning VM内部の
data stack、return／loop frame、辞書など、明示的にtransaction対象とした状態に限る。

## snapshot規則

- UIへ渡すのは命令境界で確定したcopyだけで、実行中objectへの参照を渡さない。
- snapshotにはdata stack、型付きreturn frame、loop frame、現在word、invocation、命令番号、source位置を持たせる。
- Pause要求から受理までの間、画面には直前の確定snapshotと「停止要求中」を表示する。
- 継続後も過去の停止snapshotを監査履歴として保持できる形式にする。
- 状態遷移は連番付きeventとして記録し、無効な操作は黙って無視せずerrorにする。

## この段階の実装範囲

`viewer/mobile-monitor-state.js`はVMから独立した状態遷移の正本である。
`viewer/mobile-forth-session.js`は現行MobileForthを利用しながら、top-level tokenとcolon内部命令を
1命令ずつ進める再開cursorを持つ。状態機械は各命令完了後のsnapshotだけを受け取る。

Node.js回帰試験では、算術、colon word、分岐、LOOP、再帰について従来の同期`interpret()`と最終stack、
端末出力、step数が一致することを確認する。また、colon word内部でPauseし、Stepで1命令進め、Continueで
完了できること、Stopが現在状態を保持すること、Abortが開始前のstackと辞書へ戻すことを確認する。

`viewer/mobile-forth-scheduler.js`はsessionを既定100命令、設定可能な上限以内のchunkで駆動し、chunk間で
`setTimeout(..., 0)`を使ってbrowser event loopへ制御を返す。同じchunkを重複予約せず、Pause、Stop、
Abort要求があれば次の命令境界で受理する。Step中はchunk上限にかかわらず1命令で再停止する。

fake scheduler回帰試験では、4命令chunkで無限LOOPを実行し、1 chunk後にPauseを要求して次の1命令で
停止できること、Stepが1命令、Continue後も各chunkが4命令以内であること、Stopが途中stackを保持する
ことを確認する。別の実行ではAbortが途中辞書とstackを復旧しながら表示済み出力を残すことも確認する。

Mobile Viewerにはschedulerを直接接続し、Run／Pause／Step／Continue／Stop／Abort、現在位置、
呼出し履歴、chunk進捗を表示する。画面が参照するのは命令境界で確定したsnapshotだけである。
Web Workerへの分離は次段階とし、この段階ではchunk間の`setTimeout(..., 0)`でbrowserへ制御を返す。

2026-10-15、利用者がPC画面で6操作と表示を確認し、問題なしと判定した。続いて
`docs/MOBILE_WORKER_PROTOCOL_R0_JP.md`へWorker通信規約を固定し、protocol validatorとWorker engineを追加した。
session IDとcommand／event連番により、再送message、順序違反、古いsessionの混入を拒否する。fake port上で
Pause、Step、Continue、Stop、Inspect、Abortと新sessionへの切替を確認した。この時点では実ブラウザWorkerを
まだ起動していなかった。

続いてBlob Worker clientと自己完結HTMLへのWorker source埋込みを実装した。Worker作成不可なら同じengineを
main thread互換モードで動かす。埋込みsourceはNode.jsの実Worker threadで起動・実行確認済みである。
実ブラウザでの目視確認は未実施で、次の確認点とする。
