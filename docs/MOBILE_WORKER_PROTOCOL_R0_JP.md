# Mobile Learning Worker通信規約 R0

状態：Phase B内部規約。公開済み`v0.1.4-rc.1`の仕様ではない。

## 目的

Mobile Viewerの画面threadとFORTH実行Workerを分離する。画面は実行中VMへ直接触れず、命令境界で確定した
snapshotだけを受け取る。すべてのmessageにprotocol版、session ID、単調増加する連番を持たせ、終了済みの
古い実行から遅れて届いたmessageを新しい実行へ混入させない。

## envelope

```text
{
  version:   "min0-mobile-monitor/0.1",
  kind:      "command" | "event",
  sessionId: 1～64文字の安全なASCII識別子,
  sequence:  1から増加する整数,
  name:      command名またはevent名,
  payload:   JSON互換object
}
```

payloadはcopyして渡し、関数、循環参照、非有限数、class instance、prototype操作用keyを拒否する。FORTH sourceは
UTF-8で4096バイトまで、chunk sizeは1～10000命令境界とする。

## 画面からWorkerへのcommand

| name | payload | 意味 |
|---|---|---|
| `run` | `{ source, chunkSize? }` | 新sessionを開始する |
| `pause` | `{}` | 次の命令境界で一時停止する |
| `step` | `{}` | pausedから1命令だけ進める |
| `continue` | `{}` | pausedから連続実行へ戻る |
| `stop` | `{}` | 次の命令境界で現在状態を保持して終了する |
| `abort` | `{}` | 次の命令境界で開始前状態へ復旧する |
| `inspect` | `{}` | 実行を進めず最新の確定snapshotを要求する |

Workerはcommandの受信順を検査する。同じsessionで連番が重複・逆行したcommand、session IDが異なるcommand、
現在状態で許可されない操作は実行せず`rejected`を返す。

## Workerから画面へのevent

| name | 意味 |
|---|---|
| `ready` | Worker初期化完了 |
| `accepted` | commandを受理した |
| `update` | scheduler更新と確定snapshot |
| `rejected` | command形式、順序、状態が不正 |
| `fatal` | Workerを継続できない内部error |

`update`には元commandの連番、schedulerのchunk番号・実行数・累計境界数、Monitor状態、確定snapshotを入れる。
trace、辞書、error診断はPause、Stop、Abort、完了、失敗など実行が止まったeventだけに含める。

## 安全規則

- 画面は現在session IDと一致しないeventを表示しない。
- 同一sessionではevent連番が直前以下なら破棄する。
- Workerは受信messageを検証してから状態機械へ渡す。
- command errorは`rejected`として返し、Worker全体を停止しない。
- 予期しない内部errorだけを`fatal`とし、最後の確定snapshotがあれば一緒に返す。
- StopとAbortを統合しない。外部IOや表示済み出力はAbortでも戻らない。
- Worker終了時には未処理commandを別sessionへ引き継がない。

## Worker engine

`viewer/mobile-forth-worker-engine.js`が通信規約とsession／schedulerの間を接続する。新sessionの最初の
`run`はcommand連番1に限定する。以後は同じsession IDで直前+1のcommandだけを受け入れる。別sessionや
重複・逆行した連番は、現在sessionを置き換えず`rejected`にする。

fake message port試験では、無限LOOPを4命令chunkで動かし、Pause、Step、Continue、Stop、Inspect、Abortを
messageだけで操作する。さらに再送連番と古いsessionを拒否し、終了後に新sessionを連番1から開始できることを
確認する。

## Browser clientとfallback

`viewer/mobile-forth-worker-client.js`がBlob URL、Worker、session ID、command／event連番を管理する。画面へ渡すのは
現在sessionと一致し、直前より大きいevent連番だけである。Worker constructorまたはBlob URL作成が利用できない
場合は、同じWorker engineをmain thread上で起動する互換モードへ移る。このため画面側のcommand／event処理は
二重実装しない。

実行途中のWorker異常では、確定前のVM状態を別実行器へ安全に移せない。したがって途中からfallbackで継続せず、
`fatal`として診断停止する。次のRunでは新しいsessionとしてWorkerを作り直せる。

自己完結HTMLにはprotocol、VM、session、scheduler、engineを結合したWorker sourceを文字列として埋め込む。
Run時にBlob URLを作ってWorkerを起動し、終了時には`terminate()`と`revokeObjectURL()`で資源を解放する。
埋込みsourceはNode.jsの別threadでも起動し、message経由の`2 3 +`がstack `[5]`で完了することを確認する。

## 次段階

PCブラウザで「Worker分離モード」と6操作を目視確認する。続いてGitHub Pages評価版を作り、iPhone Safariでも
Worker分離モード、Pause、Step、Continue、Stop、Abortを確認する。

2026-10-15、利用者がPCの自己完結Viewerで無限LOOPを実行し、chunk進行、現在命令位置、確定stack、
`CALL_RETURN`呼出し履歴と6操作を確認し、問題なしと判定した。PC評価は合格とし、次はGitHub Pages評価版と
iPhone Safari確認へ進む。
