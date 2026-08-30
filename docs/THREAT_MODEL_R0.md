# MIN0 CORE FORTH threat model R0

## 位置付け

対象は新規FORTH（MIN0 CORE FORTH）であり、MSX0-FORTHは対象外である。本書は暗号方式を決定する
前の脅威整理で、現在のhost prototypeと将来の小規模MPU／FPGA targetを扱う。

R0の優先目標はintegrity、authenticity、availability、recoverabilityである。imageやsourceの
confidentiality（秘匿）は現在提供しない。物理攻撃を完全に防ぐこともR0の達成条件にしないが、
鍵方式を選ぶ際の重要な制約として残す。

## 守る資産

1. 実行されるCODEが承認された内容であること
2. DICTIONARYのword、link、XT、descriptor、constructor plan
3. DATA初期値とallocator位置
4. CODE-HERE、header HERE、data HERE、LATEST
5. relocation manifestとtarget profile
6. 将来のgeneration counter、recovery image、認証鍵
7. Monitorの停止・再開・差し替え権限
8. Viewer／traceが示す観測結果の正確性

## 信頼境界

```text
build source / toolchain
          |
          v
 image作成・署名host  -- 秘密鍵（将来）
          |
   [配布媒体・通信境界]
          |
          v
 boot/update loader  -- 公開鍵または共有鍵（将来）
          |
   [検証済みimageだけをinstall]
          |
          v
 FORTH runtime -- Monitor -- host I/O
          |
          v
 trace / Viewer / AI解説（観測データ境界）
```

R0ではbuild hostを信頼する。将来のloader自身、鍵storage、最低generation値は、imageから独立した
trusted computing baseに置く必要がある。検証対象imageの中に「自分を正しいと判定する鍵」まで
置けば、攻撃者がimageと一緒に交換できるためである。

## 想定する主体

- A0 操作ミスや媒体故障。悪意はないが、古い版・別target版・破損fileを投入する。
- A1 imageを差し替えられる攻撃者。正規の秘密鍵は持たない想定。
- A2 Forth sourceやMonitor commandを入力できる利用者。image更新権限とは分離すべきである。
- A3 network経由の相手。network機能を持つprofileでのみ登場する。
- A4 実機を長時間占有し、Flash読出しやprobe接続ができる物理攻撃者。
- A5 build hostまたは署名鍵を侵害した攻撃者。端末側検証だけでは完全に防げない。

## 入口

- persistent imageの読込み・更新
- Forth source、起動script、無対話実行file
- Monitor／debug port／serial console
- host I/O driverと将来のnetwork packet
- EEPROM／Flashへの保存と電源断
- traceに含まれるword名・comment・error文字列
- Viewer／AIへ渡す観測データ

## 脅威一覧

| ID | 脅威 | 現在の状態 | 必要な次対策 |
| --- | --- | --- | --- |
| T01 | componentの偶発破損 | SHA-256で拒否 | persistent parserでも同じ順序を維持 |
| T02 | manifest・allocator・別imageの取り違え | identityとtransactional linkerで拒否 | envelope保存形式へ統合 |
| T03 | 攻撃者が改変imageと新digestを一緒に作る | Developmentではgap、signed profileではEd25519で拒否 | 秘密鍵保護・失効 |
| T04 | 未認証imageをdeploymentへ投入 | 認証必須policyは拒否、正規署名imageは受理 | persistent loaderへ統合 |
| T05 | 古い正規imageへのrollback | identity内generationと最低受入値で拒否 | trusted stateの永続化・電源断対策 |
| T06 | 無限loopによるCPU占有 | host VMはstep limitで停止 | 実機watchdog／実行budget profile |
| T07 | stack・allocator・memory越境 | 現VM／辞書は上限検査 | target portでも同じ例外意味を維持 |
| T08 | malformed persistent fileによるparser攻撃 | bounded containerとcanonical JSONで15種を拒否 | target固定buffer・fuzzing |
| T09 | 更新途中の電源断 | A/B slotとsealed markerのhost modelで旧imageへ復帰 | 実媒体・書込み粒度で再試験 |
| T10 | Monitor経由の無断停止・差し替え | loader更新はcapability分離、停止制御は未実装 | Monitor認証・safe point・watchdog |
| T11 | Viewer／AIへのprompt injection | traceは観測データ指定、Viewerはtext表示 | AI接続時も命令channelと分離 |
| T12 | 物理読出し・共有鍵抽出 | R0範囲外 | 鍵方式選択時に影響を評価 |
| T13 | build host・image署名鍵侵害 | root署名bundleで鍵を失効可能 | offline root保護・監査 |
| T14 | normal／recovery domain混同 | v4 role、別key、別generation、capabilityで拒否 | target物理分離 |
| T15 | 古い／偽造trust bundle | root署名、epoch、二重journalで拒否 | root rotation・実媒体試験 |
| T16 | root policyの偽造・切断・巻戻し | cross-sign、hash chain、epoch、A/B stateで拒否 | 複数人承認・実媒体試験 |
| T17 | 正しい更新物を危険な順番で適用 | integrated loaderが現在のtrust／両imageをpre-write検証 | capability分離・実媒体試験 |

## 実働境界監査

`security_boundary_demo.py`／`.rb`は現在の実imageに対して次を確認する。

- T01 component corruption: blocked
- T02 manifest tamper: blocked
- T03 malicious rebuild in Development: accepted（gap）
- T04 malicious rebuild with authentication-required policy: blocked
- T05 old valid image rollback: blocked by minimum accepted generation
- T06 infinite execution: blocked by step limit

Python／Rubyの結果を一致させ、「未実装の防御を成功扱いしない」ことを回帰試験へ固定する。

## 仮profile

### Development Profile

- digest-bound identityを検査する。
- authentication `none`を許す。
- 対話的開発と教材用途に限定し、deployment用の安全性を主張しない。

### Controlled Device Profile候補

- authentication必須。
- 少数の所有者と閉じた更新経路を想定する。
- HMACの小ささは利点だが、実機から共有鍵が漏れると署名能力まで失う。

### Distributed Image Profile候補

- authentication必須。
- 実機には検証用公開鍵だけを置き、秘密署名鍵を配布しない。
- 公開鍵方式のROM、RAM、検証時間をtargetごとに評価する。

profile名と方式は未凍結である。HMAC／公開鍵signatureのどちらかを全targetへ一律に強制しない。

## deployment前のP0条件

1. 認証schemeと鍵の保存・更新・失効方針
2. generation最低受入値を電源断に耐えて保存するtrusted state
3. 電源断に耐えるloader transactionとrecovery path
4. persistent parserの入力上限と破損監査
5. loader／鍵／最低generation値を置くtrust anchor
6. Monitor更新権限と通常のForth対話権限の分離

## 次の作業

実装を選ぶ前に、代表的な三環境についてHMACと公開鍵signatureを比較する。

1. 一人の開発者が手元の一台を更新する小規模実験機
2. 複数台へ同じimageを配るcontrolled device
3. 不特定利用者へimageを公開するdistributed system

比較結果は`AUTH_COMPARISON_R0.md`へ保存した。HMACはcontrolled per-device用途のoptional候補、
Ed25519はdistributed imageの第一候補とした。generation-based anti-rollbackは
`ANTI_ROLLBACK_R0.md`、authentication block統合は`SIGNED_IMAGE_R0.md`まで完了した。
transactional installのhost modelは`TRANSACTIONAL_INSTALL_R0.md`、独立recovery pathは
`RECOVERY_PATH_R0.md`まで完了した。root署名trust bundle、image key rotation／revocation、recovery A/B
更新は`TRUST_ROTATION_R0.md`まで進んだ。root key自身のcross-signed rotationは
`ROOT_ROTATION_R0.md`まで進んだ。bounded persistent parserは`PERSISTENT_PACKAGE_R0.md`、parser、root／trust、
normal／recovery A/B installの統合は`LOADER_STATE_MACHINE_R0.md`、通常FORTH、Monitor、recovery、
provisioner間のhost capability分離は`CAPABILITY_BOUNDARY_R0.md`まで進んだ。次はMonitor control plane、
safe point、watchdogとtarget物理分離である。
