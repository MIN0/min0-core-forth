# MIN0 CORE FORTH authenticated DEFER switching R0

## 目的

通常の再定義と、実行中の呼出し先差替えを別概念として維持する。既存の`CALL`はコンパイル時のcode addressを
保持し、後から同名wordを定義しても変化しない。動的変更を許す場所だけをkind 7のDEFER entryとして明示し、
停止中の認証済みMonitorからのみ切り替える。

## 実行表現

DEFER entryは固定8-byte XTを維持する。

```text
XT +0  u32  KIND = 7
XT +4  u32  current colon-word XT（0は未割当て）
```

DEFERを含むcolon definitionは、現在のtargetを通常の`CALL`へコピーせず、次をコンパイルする。

```text
ICALL XT+4
```

`ICALL`は呼ばれるたびにslotを読み、XT kind 1とcode payloadを検証して、その時点のcode addressへ進む。
この一段の間接参照により、既に
コンパイル済みのcallerを書き換えずにtargetだけを切り替えられる。slotが0、読取り不能、targetが実行不能なら
fail-closedとする。

R0のtargetはcolon definitionだけに限定する。primitive、constant、variable、CREATE／DOES、definerをtargetに
する一般XT実行は、統一`EXECUTE`意味論を決める段階まで行わない。

## pause中の操作境界

Monitor control planeへruntime dictionaryを接続すると、停止中に次の操作が可能になる。

- observer: IP、三stack、辞書entry、監査記録のcopyを読む。
- monitor: observerと同じ観察に加え、`switch_defer(defer-name, target-name)`を実行する。

切替えには、watchdog解除済みの`paused`状態と、発行済みmonitor sessionの両方が必要である。observer、
profile文字列、偽造／revoke済みsession、DEFER以外のsource、colon以外のtargetは拒否する。

source-levelの`DEFER name`、`' target IS name`、`ACTION-OF name`は`DEFER_SOURCE_R0.md`で追加した。Monitor接続
後のmutationは一般outer interpreterから拒否し、認証済みcontrol sourceだけを`switch_defer`へ変換する。

## resume invariant seal

停止時に次のcontrol-critical stateをsealする。

- IP、累計step、HALT状態
- DATA／RETURN／LOOP stackの全cell
- dictionaryの`HERE`、data `HERE`、`LATEST`
- live dictionary imageのSHA-256

再開前にstack上限、IP／return addressの実行可能性、辞書LINK、DEFER targetを再検証し、sealとも比較する。
Monitor APIを通さないstack変更、辞書追加、DEFER slot書換え等が一つでもあれば再開を拒否する。正規の
DEFER切替えだけが、検証、単一cell更新、監査記録追加、新seal作成の順で完了する。

これは同一process内の悪意あるhostを閉じ込めるsandboxではない。hostの誤操作、Viewer／AI integrationの
誤接続、権限を通らない更新を再開境界で発見する防御である。

## 監査記録

各切替えは次を記録し、observerにもread-onlyで公開する。

- sequence、operation=`defer-switch`
- DEFER名、旧target名、新target名
- 旧／新target XT
- 切替え時の累計stepとIP

R0の監査記録はvolatileであり、署名付き永続logではない。永続化はloaderのtrust／root方針と結合する将来段階
で扱う。

## 実働例

`APPLICATION`には`SERVICE`が既にコンパイルされている。wrapperが`APPLICATION`を二回呼ぶ。

1. `SERVICE -> OLD-SERVICE`で一回目を実行し、stack `[10]`でsafe point停止。
2. Monitorが`SERVICE -> NEW-SERVICE`を切替え、監査recordを一件生成。
3. 同じコンパイル済み`APPLICATION`を再開し、二回目は新targetを呼んでstack `[10, 20]`。

Python／RubyでIP、step、entry payload、監査record、最終stack、typed relocationが一致する。compilerは
`ICALL` operandを`target=dictionary / kind=defer-slot`として記録し、dictionary image側の非zero target XTも
`target=dictionary / kind=defer-target-xt`としてrelocation対象にできる。

```powershell
python -m unittest -v test_monitor_patch.py
ruby test_ruby_monitor_patch.rb
python cross_monitor_patch_check.py
```
