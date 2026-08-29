# MIN0 CORE FORTH Monitor control plane R0

## 目的

無対話でFORTH applicationが動作している最中でも、信頼されたMonitorが停止を要求し、安全な状態を観察して
から実行を再開できる土台を定める。R0は対話consoleや動的word差替えそのものではなく、その前提となる
execution controlである。

control planeはbytecode VMの外側に置く。FORTH source、DATA stack、memory、trace、ViewerやAIの説明文は、
pause／resume権限として扱わない。

## safe point

safe pointは、直前のVM命令が完全に終了し、次のopcodeをまだfetchしていない境界である。

```text
命令Nを完了 -> safe point（pause・budget・watchdog確認） -> 命令N+1を開始
```

R0では命令の途中で停止しない。このため、pause時のIP、DATA／RETURN／LOOP stackは一貫したVM状態として
観察できる。pause要求が命令実行中に到着した場合、遅くともその一命令の完了後に受理する。

## 停止理由

| reason | 意味 | 再開条件 |
| --- | --- | --- |
| `pause-requested` | Monitorの明示的停止要求 | そのまま次のsliceを開始可 |
| `budget-exhausted` | 今回許可した命令数を消費 | 新しい正のbudgetを与える |
| `watchdog-expired` | host health checkが失敗 | Monitorが明示的にlatchを解除 |
| `halted` | FORTHが`HALT`を実行 | 通常は終了。新しいentry準備が必要 |

`budget`は一回の`run_slice`で実行できる命令数であり、時間ではない。処理速度に依存しない決定的な防波堤と
して使う。watchdogはhost／target固有のclock、heartbeat、外部supervisor等を接続する場所であり、R0 test
では再現可能なhealth predicateで模擬する。

watchdog作動後は自動再開しない。原因を確認せず同じ処理へ戻るloopを避けるため、Monitor capabilityによる
`clear_watchdog`を必須とする。

同じsafe pointで複数条件が成立した場合の優先順位は、`pause-requested`、`budget-exhausted`、
`watchdog-expired`の順とする。これによりPython／Rubyと将来targetで停止理由が揺れない。

## capability境界

`MonitorControlAuthority`は起動hostだけが保持し、文字列ではなく発行済みsession objectを権限として使う。

| profile | 状態観察 | pause要求 | run／resume | watchdog解除 |
| --- | --- | --- | --- | --- |
| observer | 可 | 不可 | 不可 | 不可 |
| monitor | 可 | 可 | 可 | 可 |

- profile名文字列、未発行session、偽造session、revoke済みsessionは拒否する。
- sessionはJSON、package、FORTH memory／stackへ直列化しない。
- observerへ返すstackはcopyであり、観察側からVM stackを変更できない。
- safe-point observerとwatchdog callbackはtrusted host APIである。利用者source、trace文字列、AI出力をcallback
  として実行してはならない。

同一process内でhost自身がVM objectへ直接触れることまで防ぐ強いsandboxではない。実機ではMPU privilege、
別core、memory protection、物理watchdog等のどれで境界を作るかをtarget profileで定める。

## 実働確認

test programは次の6命令である。

```text
LIT 1  / LIT 2 / ADD / NOP / NOP / HALT
```

Python／Rubyの両実装で次を一致確認した。

1. `ADD`完了後、3命令目のsafe pointでpauseし、IP=`11`、DATA stack=`[3]`。
2. budget 1で`NOP`を一つだけ実行し、IP=`12`。
3. watchdogで次の`NOP`を一つ実行後に停止し、IP=`13`。明示解除前の再開は拒否。
4. 解除後に`HALT`へ進み、累計6命令。命令の重複・欠落なし。

実行方法:

```powershell
python -m unittest -v test_monitor_control.py
ruby test_ruby_monitor_control.rb
python cross_monitor_control_check.py
```

## R0でまだ行わないこと

- OS thread、割込み、network経由の非同期pause signal
- 実時間deadlineや物理watchdog device
- Monitorの認証protocol、対話console、`MFORTH -z`との統合
- pause中のdictionary更新、`DEFER`差替え、transactional patch
- fault発生後の自動継続（VM fault時は`faulted`として再開を拒否する）

pause中のread-only観察、認証済み`DEFER`切替え、再開前のstack／dictionary invariant検査は
`MONITOR_PATCH_R0.md`で実働化した。image更新は引き続きloader transactionとして別経路に保つ。
