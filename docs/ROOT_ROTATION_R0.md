# MIN0 CORE FORTH pinned root rotation R0

## 目的

trust bundleを署名するoffline root自身を、安全な順序で旧鍵から新鍵へ交代する。対象は新規FORTHの
host executable specificationであり、MSX0-FORTHには変更を加えない。

root public keyを永久固定すると、計画的な鍵更新も、古い暗号実装からの移行もできない。一方、imageが
提示した新rootを無条件に信じると、攻撃者が自分の鍵へ置き換えられる。そこで、ROM等に固定する最初の
bootstrap rootと、そこから連なる署名済みroot policy chainを分ける。

## root policy v1

policyは次を署名対象に含める。

- format／version
- unsigned 64-bit `epoch`
- 直前policy payloadの`previous_policy_sha256`
- key-ID順のroot entry
- 必要rootによるEd25519署名集合

root entryは`key_id`、32-byte `public_key_hex`、`active | retired` statusを持つ。同一key IDの公開鍵を
交換すること、既存entryを削除すること、`retired`を`active`へ戻すことを禁止する。

署名messageはdomain-separated policy payload digestである。署名配列の順番やJSON object順には依存
せず、PythonとRubyが同じpayload、digest、signatureを生成する。

## cross-sign規則

各transitionに必要な署名者は次の和集合である。

```text
直前policyのactive roots ∪ 新policyのactive roots
```

このため、新root追加には旧rootと新rootの双方が署名する。旧root退役policyにも、直前までactiveだった
旧rootと、引き続きactiveな新rootの双方が署名する。退役が確定した次policyからは新rootだけで継続する。

```text
epoch 1  old active                  signed: old
epoch 2  old active, new active      signed: old + new
epoch 3  old retired, new active     signed: old + new
epoch 4  old retired, new active     signed: new
```

新root自身の署名を要求することで、誤った公開鍵や、秘密鍵を保有していない鍵を登録してから旧rootを
退役させる事故を防ぐ。これは鍵の所有証明であり、旧rootがすでに侵害されている場合に攻撃者の新rootを
識別する仕組みではない。

## trust bundleを含む正しい順序

root policyだけをepoch 3へ進めると、旧root署名しか持たない現在のtrust bundleが無効になり得る。
正しい順序は次である。

```text
1. old + new activeのroot policyをinstall・検証・commit
2. new root署名のtrust bundleをinstall・検証・commit
3. そのbundleでnormal／recovery imageを検証できることを確認
4. old retiredのroot policyをinstall・検証・commit
5. new root単独署名policyへ進む
```

実働デモではoverlap中に旧root／新root署名bundleを両方受理し、退役後は新bundleだけを受理した。
new root bundle導入前にold rootを退役させ、旧bundleが使えなくなる危険な順序も再現した。

## A/B stateとanti-rollback

policy chain全体をA/B root-state slotへ保存する。

```text
erase inactive root state
write complete policy chain
seal root state with checksum
```

seal前の電源断では旧epoch 1、seal後だけ新epoch 2が可視になる。可視化後、loaderでの利用成功を確認
してからminimum root epochを二record journalへcommitする。journal seal前の電源断ではminimum 1、
seal後だけ2になる。

起動時はchecksum、bootstrap pin、chain link、全署名、minimum epochを毎回検証する。commit済み最新
chainを壊し、minimumを満たす旧slotしか残らない場合は、古いrootへ黙って戻らずfail-closedにする。
この状態からの復旧はprotected recovery経路の責務である。

## 攻撃・事故監査

Python／Rubyの両実装で次を拒否した。

- 新root署名が欠けたtransition
- policy署名の改変
- `previous_policy_sha256`を切ったchain
- 既存key IDの公開鍵交換
- retired rootの再有効化
- minimum epoch確定後の旧policy導入
- checksumと内容が一致しないcommit済みchain

公開fixtureによる4 policyのdigestと全Ed25519 signature、電源断状態、拒否結果は両言語で一致する。

## R0の限界と次作業

- 侵害済み旧rootは、攻撃者所有の新rootをcross-signできる。offline保管、複数人承認、監査が必要。
- threshold signature／緊急recovery rootは未実装。
- policy chainとroot entryは増え続ける。小容量target向けの最大長と安全なcheckpoint圧縮が必要。
- persistent binary parser、section長上限、整数overflow防御は`PERSISTENT_PACKAGE_R0.md`でhost modelを
  実装した。target固定bufferへの移植は未実装。
- 実Flash／EEPROMのerase block、書込み粒度、耐久性で再試験が必要。

persistent parser、root／trust検証、A/B installの統合は`LOADER_STATE_MACHINE_R0.md`へ進んだ。
root退役前に現在のtrust bundleが候補root集合で検証できることを、slot書込み前に確認する。

## 実働ファイル

- `min0_core_forth_root.py`／`.rb`: canonical policy、chain検証、A/B state、minimum epoch journal
- `root_rotation_demo.py`／`.rb`: 4 epoch、bundle移行、電源断、攻撃・事故監査
- `test_root_rotation.py`／`test_ruby_root_rotation.rb`: 固定vectorと回帰
- `cross_root_rotation_check.py`: Python／Rubyのbyte-level照合
