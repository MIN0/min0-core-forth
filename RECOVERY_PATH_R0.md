# MIN0 CORE FORTH independent recovery path R0

## 目的

normal generationをcommitした後でA/Bのcurrent imageが破損しても、古いnormal imageへrollbackせず、
独立して認証されたrecovery環境からcurrent generationのnormal imageを修復する。対象は新規FORTHの
host executable specificationであり、MSX0-FORTHには変更を加えない。

## envelope v4 image role

envelope v4は次の`image_role`をcanonical identityへ含める。

- `normal`: 通常起動・通常更新用
- `recovery`: protected recovery環境用

roleを書き換えるとidentityとEd25519署名が一致しなくなる。loader APIもnormal slotでは`normal`、
recovery slotでは`recovery`を明示的に要求する。

鍵を分けるだけでなくroleも署名対象にする理由は、鍵設定を誤って両trust storeへ登録した場合にも、
用途の混同を拒否するためである。role追加はidentity schema変更なのでv3を装わずv4へ進めた。

## 二つのtrust domain

| 項目 | normal domain | recovery domain |
| --- | --- | --- |
| role | `normal` | `recovery` |
| key | normal update public key | independent recovery public key |
| generation | normal minimum（例: 8） | recovery minimum（例: 1） |
| storage | A/B writable slot | protected R slot候補 |
| 起動条件 | complete・signed・generation適合 | normal候補がなく、Rがsigned・generation適合 |

normal minimum 8とrecovery minimum 1は比較しない。recovery generation 1を起動することはnormal 8からの
rollbackではなく、別role・別key・別generation journalを持つ別domainへの遷移である。

## boot順序

1. A/B normal slotを走査する。
2. 一つでもpolicyを満たすnormal候補があればnormalを起動する。
3. normal候補がなければprotected Rをrecovery trust storeで検証する。
4. Rも検証できなければtotal boot failureとして停止する。

通常起動できる状態でrecovery repair APIを呼ぶことは拒否する。recovery pathを通常更新の近道や
任意書換えinterfaceとして公開しない。

## current-generation repair

実験ではnormal minimum 8へcommit後、唯一のnormal generation 8 slotを1 byte破損させた。Aに残る
normal generation 7はanti-rollbackで拒否されるため、normal bootは成立しない。その後、Rの
recovery generation 1を独立keyで検証してrecovery modeへ入った。

recovery modeはnormal keyで署名されたgeneration 8 imageを受け取り、通常installerと同じ順序でBへ
修復する。

```text
erase B -> CODE -> DICTIONARY -> DATA -> envelope -> verify
        -> complete-marker body -> marker seal
```

normal trusted generationは8のままで、下げない。修復slotをsealした後、boot選択は自動的にnormal B、
generation 8へ戻る。

## repair power-loss行列

| 修復中の電源断位置 | reboot mode | generation |
| --- | --- | ---: |
| B erase後 | recovery | 1 |
| CODE後 | recovery | 1 |
| DICTIONARY後 | recovery | 1 |
| DATA後 | recovery | 1 |
| envelope後 | recovery | 1 |
| staged検証後 | recovery | 1 |
| marker本文後 | recovery | 1 |
| marker seal後 | normal | 8 |

seal前に何度電源が切れてもRへ戻って修復を再試行できる。seal後だけBがnormal候補になる。

## role・authorization監査

次を拒否した。

- normal generation 7でminimum 8を修復しようとする。
- normal role imageをRから起動する。
- recovery role imageをnormal slotへ書く。両public keyをloaderへ渡した場合でもroleで拒否する。
- signed envelopeのroleだけを`recovery`から`normal`へ変える。
- normal boot可能な状態でrecovery repairを呼び出す。

recovery image自身を1 byte壊し、normal候補もない場合は`BootError`になった。R0はこの状態を隠さず、
total failureとして回帰試験へ固定する。

## security上の意味

古いnormal imageを無条件に起動するemergency flagを設けずにrecoverabilityを追加した。recovery keyを
持つ署名者はrecovery codeを更新できるため強い権限を持つが、その署名をnormal imageとしては使えず、
normal minimum generationも下げられない。

一方、悪意あるrecovery codeが実機上で直接Flash controllerへ触れられるなら、host APIのrole検査だけ
では不十分である。実targetではmemory protection、ROM loader mediation、capability制限などにより、
recovery runtimeが許されたrepair操作だけを行えるようにする必要がある。

## host modelの限界

- 本書のprotected Rは事前provision済みで不変と仮定した。後続のA/B transactional update host modelは
  `TRUST_ROTATION_R0.md`へ実装したが、実protected媒体への移植は未実装。
- recovery keyのrotation／revocation host modelは後続で実装した。private keyの実offline管理は未実装。
- physical-presence button、service jumper、rate limit、監査logは未実装。
- recovery imageのFORTH codeを最小権限へ制限するVM／MPU機構は未実装。
- 実Flash／EEPROMの保護bit、write-once領域、secure elementはtarget依存。
- Rまで破損した場合のROM factory recoveryは未実装。

## 実装と確認

- `min0_core_forth_image.py`／`.rb`: v4 role identityとrequired-role検証
- `min0_core_forth_recovery.py`／`.rb`: normal-first boot、protected R、recovery-only repair
- `recovery_path_demo.py`／`.rb`: post-commit破損、全repair電源断、role混同監査
- `test_recovery_path.py`／`test_ruby_recovery_path.rb`: policy回帰
- `cross_recovery_path_check.py`: Python／Ruby状態遷移照合

recovery image自身のA/B更新と、normal／recovery key rotation・revocationは
`TRUST_ROTATION_R0.md`へ進んだ。
