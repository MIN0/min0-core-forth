# MIN0 CORE FORTH integrated loader state machine R0

## 目的

外部package parser、root policy、trust bundle、normal image、recovery imageを、一つの更新順序へ結合する。
対象は新規FORTHのhost executable specificationであり、MSX0-FORTHには変更を加えない。

各部品が個別に正しくても、順番を間違えると現在起動できるimageの署名鍵や、その鍵を認めるrootを先に
失効してしまう。本R0では候補を永続slotへ書く前に、候補を採用しても現在の起動経路が残ることを検証する。

## 四つの永続domain

loaderは次の四domainを独立したA/B状態と最低受入値で管理する。

| domain | 可視状態 | rollback防止値 | 署名・用途 |
| --- | --- | --- | --- |
| root | root policy chain | minimum root epoch | bootstrap rootからのcross-sign |
| trust | trust bundle | minimum trust epoch | 現在activeなrootで署名 |
| normal | normal image | minimum normal generation | normal roleのactive image key |
| recovery | recovery image | minimum recovery generation | recovery roleのactive image key |

更新中という状態を、外部file内のphase fieldやRAM上のactive pointerから決めない。checksum seal済みの可視
epoch／generationと、別journalにcommit済みのminimumを毎回比較して導出する。

```text
visible == minimum  -> stable
visible > minimum   -> <domain>-awaiting-commit
```

同時に二domain以上が未commitならfail-closedとする。一つのtransactionを成功commitまたは明示的に
rejectしてから、次のdomainへ進む。

## package受理の共通順序

```text
bounded package parse
  -> kind／section／canonical JSON
  -> chain／epoch／role／generation
  -> component digest／Ed25519 signature
  -> 現在の起動経路を壊さないか事前検証
  -> inactive slotへtransactional write
  -> candidate boot／利用成功
  -> minimum epoch／generation commit
```

packageの内容に「次はroot更新状態へ移れ」と命令させない。呼び出したloader APIと検証済みpackage kindの
組合せだけが対象domainを決める。

## pre-write ordering guard

### root候補

- installed chainとbyte-level canonical JSONで完全に同じhistoryを持つ。
- policyをちょうど一件だけappendする。
- bootstrap pin、hash link、cross-sign、minimum epochを満たす。
- **候補root集合で、現在のtrust bundleをまだ検証できる。**

最後の検査により、新root署名bundleを導入する前にold rootをretiredへする順番を、root slotへ書く前に
拒否する。

### trust候補

- 現在activeなroot集合で署名とepochを検証する。
- **候補bundleのactive keyだけで、現在選択中のnormalとrecoveryの両方を検証できる。**

これにより、新鍵imageを起動確認する前に旧normal／recovery keyをrevokedへする順番を、trust slotへ
書く前に拒否する。normalだけ残っていてもrecoveryを失う候補は受理しない。

### image候補

- APIで指定したroleと署名identity内の`image_role`が一致する。
- そのroleの現在activeな公開鍵で署名を検証する。
- candidate generationはcommit済みminimumより大きい。
- container、component、allocator、manifestが一つのsigned identityとして一致する。
- signed `execution_profile`がLoader policyと一致し、relocation要件からの再導出結果とも一致する。
- recovery imageは常に`safe-runtime`である。

normal packageをrecovery APIへ渡すrole confusion、正規署名済み旧image、切断packageをslot書込み前に
拒否する。

## 完全rotationの安全な順序

実働デモは次の順序を通す。

```text
stable
  1. old + new root policy       stage -> commit
  2. old + new image-key bundle  stage -> commit
  3. new-key normal image        stage -> boot success -> commit
  4. new-key recovery image      stage -> boot success -> commit
  5. old image keys revoked      stage -> commit
  6. old root retired            stage -> commit
stable
```

初期値はroot/trust epoch 1、normal/recovery generation 1である。完了後はroot/trust epoch 3、両image
generation 2となり、normal slot Bを選択する。途中の各stageでは対象domainだけが
`*-awaiting-commit`となる。

## boot失敗とrecovery

新normal candidateのhealth checkが失敗した場合はcomplete markerを無効化し、minimum generationを進めず
旧normalへ戻す。normal A/Bの両方が検証不能なら、独立role、独立鍵、独立minimumを持つrecoveryを選ぶ。
normalとrecoveryの両方が検証不能ならtotal boot failureとしてfail-closedにする。

現在のhost modelでは実CPU上のhealth check／watchdogをまだ実行せず、`report_boot_success`または
`report_boot_failure`という明示結果で境界を表現する。

## 電源断からの状態導出

root stageの三地点へ電源断を注入した。

| 電源断地点 | visible root | minimum | phase |
| --- | ---: | ---: | --- |
| inactive消去後 | 1 | 1 | stable |
| policy chain書込み後 | 1 | 1 | stable |
| root-state seal後 | 2 | 1 | root-awaiting-commit |

root minimum commitの三地点では、journal seal前までepoch 2／minimum 1のpending状態を再発見し、seal後だけ
epoch 2／minimum 2のstableとなる。RAM上の「最後に実行したstep」を保存しなくても、永続記録から再開点を
判定できる。

## 実働監査

Python／Rubyの両実装で次を確認した。

- root 1→2、trust 1→2、normal/recovery 1→2、trust 2→3、root 2→3の完全sequence
- premature root retirement、premature image-key revocation、root overlap前のnew-root bundleを拒否
- role confusion、image rollback、切断package、root history差替えを拒否
- candidate boot失敗後に旧normal generation 1へ復帰
- normal全損時にrecovery generation 1を選択
- root stage／commit各三地点の電源断状態
- 最終identity、全phase history、全結果がPython／Rubyで一致

## R0の限界

- A/B store、journal、電源断はhost memory modelであり、実Flash／EEPROMのerase block、書込み粒度、
  wear、ECCでは未試験である。
- loader code、公開鍵、minimum journalの物理的capability分離は未実装である。
- action historyは観測用RAM logでありsecurity decisionには使わない。永続監査logは未実装である。
- 一つのdevice内で四domainを別々に更新するmodelであり、device群への配布完了確認は未実装である。
- root／trust commit途中の電源断後はpendingを検出できるが、運用側が同じcommitを再実行するrecovery loopは
  target UI／boot policyとして未実装である。
- R0は現在のnormalとrecoveryを同時に保てるtrust候補だけを受理する厳格policyである。緊急失効時の
  例外経路は別trust anchorと明示的なfactory recovery設計が必要である。

loader操作権限の通常FORTH／Monitor／recovery／provisioner分離は`CAPABILITY_BOUNDARY_R0.md`へ進んだ。
次はMonitor control plane、実行budget、watchdog、safe pointを設計する。その後、実媒体profileで同じ
電源断試験を行う。

## 実働ファイル

- `min0_core_forth_loader.py`／`.rb`: 四domainを結ぶstate machineとordering guard
- `loader_state_demo.py`／`.rb`: 完全rotation、危険順序、boot失敗、電源断監査
- `test_loader_state.py`／`test_ruby_loader_state.rb`: 固定状態と回帰
- `cross_loader_state_check.py`: Python／Rubyの完全結果照合
