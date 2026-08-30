# MIN0 CORE FORTH loader capability boundary R0

## 目的

通常のFORTH source実行権限と、image／署名鍵／rootを変更する権限を分離する。対象は新規FORTHのhost
executable specificationであり、MSX0-FORTHには変更を加えない。

署名済みpackageと安全な更新順序があっても、任意のFORTH wordや無認証Monitor commandからloader APIを
直接呼べれば防御にならない。本R0は、信頼されたboot hostが発行した非直列化sessionだけを更新入口にする。

## capability profile

| profile | 読取り | normal | recovery | trust | root | 追加条件 |
| --- | :---: | :---: | :---: | :---: | :---: | --- |
| runtime | 可 | 不可 | 不可 | 不可 | 不可 | 通常FORTHへ渡す |
| monitor | 可 | 可 | 不可 | 不可 | 不可 | normal boot中だけ開始可 |
| recovery | 可 | 修復のみ | 不可 | 不可 | 不可 | recovery boot中だけ開始可 |
| provisioner | 可 | 可 | 可 | 可 | 可 | 信頼された保守環境だけに保持 |

`runtime`はstatusとboot選択結果を観測できるが、正しい署名packageを持っていても更新を開始できない。
`monitor`はnormal imageを更新できるが、recovery image、trust bundle、root policyには触れない。
`recovery`はnormalが全損してrecovery modeへ入った時だけnormal repairを開始できる。`provisioner`は完全
rotationに必要な全domainを操作できるため、通常のFORTH辞書やsourceへ渡してはならない。

## sessionはprofile文字列ではない

外部入力が`"profile":"provisioner"`と名乗っても権限にはならない。`LoaderAuthority`は起動時にsession
objectを発行し、発行済みobject identityとprofileを内部registryで結び付ける。

- 未発行sessionを拒否する。
- profile名の文字列をsessionの代用にできない。
- revoke後のsessionを拒否する。
- session objectはpersistent package、JSON、FORTH stackへ直列化しない。

これは暗号tokenではなくhost capability modelである。権限の意味は「そのobjectへの参照を持つこと」に
ある。

## transaction ownership

stage成功後は、開始session、domain、imageの場合はslotをvolatile owner recordへ結び付ける。

```text
monitor-A stage normal slot B
        -> owner = monitor-A / normal / B
monitor-B commit normal B  -> 拒否
monitor-A commit normal A  -> 拒否
monitor-A commit normal B  -> 許可、owner解除
```

これにより、同じprofileを持つ別sessionでも、進行中transactionの成功報告や失敗報告を横取りできない。
ownerがある間は別のstageも開始しない。

## 電源断後の引継ぎ

owner recordはsecurity decisionの永続的な真実にはしない。電源断でRAM ownerが失われても、loaderは
sealed visible値とminimum値から`normal-awaiting-commit`等を再発見する。

再起動後は、対象domainを操作できるsessionが`adopt_pending`を明示的に呼び、domainとslotを確認してから
commit／rejectする。runtime sessionによる引継ぎは拒否する。R0ではmonitorまたはrecovery sessionがnormal
pendingを引き継げる。root、trust、recovery pendingはprovisionerだけが引き継げる。

## normal全損時の専用repair入口

通常のA/B installは「現在起動できるnormalの反対slot」を選ぶため、normalが全損すると開始できない。
そこでintegrated loaderへ`stage_normal_repair_package`を追加した。

```text
normal A/B検証不能
  -> protected recovery boot
  -> recovery capabilityでgeneration 2 normal packageを検証
  -> 空のnormal slot Bへrepair write
  -> B seal後にnormal candidateが可視
  -> 同じrecovery sessionがboot成功をcommit
  -> normal generation 2 / stable
```

repairでもrole、active署名鍵、component identity、minimum generation、transactional writeを省略しない。
R0はminimumと同じgenerationの再書込みを許さず、より新しいgenerationだけを受理する。

## 実働監査

Python／Rubyで次を一致確認した。

- 4 profileすべてがstatusを読める。
- runtimeによるnormal更新を拒否。
- monitorによるroot、trust、recovery更新を拒否。
- recoveryによるtrust更新と、normal boot中のrepairを拒否。
- recovery mode中のMonitor更新を拒否。
- profile文字列、未発行session、revoke済みsessionを拒否。
- 別Monitorによるcommit横取りと、ownerが指定したslot以外のcommitを拒否。
- normal全損時、recovery sessionがslot Bへgeneration 2を修復。
- 再起動後、runtimeのpending引継ぎを拒否し、Monitorの明示引継ぎを受理。

拒否15項目、owner状態、repair結果、再起動引継ぎ結果は両言語で一致した。

## R0の限界

- Python／Ruby process内のobject capability modelであり、同processの任意codeに対する強いsandboxではない。
  untrusted codeへ`LoaderAuthority`や生の`Min0CoreForthLoader`参照を漏らせば迂回できる。
- 実targetではmemory protection、別CPU mode、ROM call gate、MPU／PMP、別microcontroller等からprofileに
  合う分離方式を選ぶ必要がある。
- session発行前の人間／device認証、physical-presence button、timeout、試行回数制限は未実装である。
- ownerはvolatileで、永続監査logではない。誰が何を承認したかの署名済みaudit recordは未実装である。
- recovery repairは新しいgenerationだけを受理する。同世代の再書込みを安全に許すには、repair counterや
  signed repair authorizationを別に設計する必要がある。
- Monitorの停止要求、実行budget、watchdog、無対話実行中の安全な切替えは次段階である。

この次段階は`MONITOR_CONTROL_R0.md`で実働化した。Monitor control planeをdata planeから分け、pause要求、
safe point、budget／watchdog、明示確認後の再開をPython／Rubyで一致確認している。

## 実働ファイル

- `min0_core_forth_capability.py`／`.rb`: profile、session発行、revoke、owner、pending引継ぎ
- `capability_boundary_demo.py`／`.rb`: 許可／拒否、normal修復、再起動監査
- `test_capability_boundary.py`／`test_ruby_capability_boundary.rb`: 固定回帰
- `cross_capability_boundary_check.py`: Python／Ruby完全結果照合
