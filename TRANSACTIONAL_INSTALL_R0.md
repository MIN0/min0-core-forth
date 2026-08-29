# MIN0 CORE FORTH A/B transactional install R0

## 目的

署名済みimageの更新途中に電源が切れても、途中まで書かれたimageを起動せず、直前の正常imageへ
戻る。対象は新規FORTHのhost executable specificationであり、MSX0-FORTHには変更を加えない。

## active pointerを使わないboot選択

単一の`active=A/B`値だけで起動先を決めると、その1 byte／1 wordが破損しただけで正しいslotを
見失う。R0では起動時にA/B両slotを走査する。

起動候補には次をすべて要求する。

1. sealed complete markerがある。
2. markerのidentityがenvelope identityと一致する。
3. marker checksumが正しい。
4. component、allocator、manifest、identityが正しい。
5. Ed25519署名がimage外trust storeで検証できる。
6. generationがminimum accepted generation以上である。

候補からgeneration最大、同generationならmarker sequence最大を選ぶ。marker sequenceとchecksumは
書込み整合性と順序を表すもので、攻撃者への認証ではない。認証はEd25519 identityが担当する。

## inactive slotへの書込み順序

candidate全体をRAM上でpreflight検証してから、現在選択されていないslotを次の順序で更新する。

```text
1. erase inactive slot
2. write CODE
3. write DICTIONARY
4. write DATA
5. write envelope
6. verify staged image from the slot
7. write complete-marker body (sequence + identity)
8. seal complete marker with checksum
```

既存markerは最初のeraseで失われる。新markerは最後まで書かず、marker本文だけでは起動候補にしない。
slot上の実byte列を再検証した後にだけsealする。

## install中のpower-loss行列

各durable operationの直後に電源断を注入した。

| 電源断位置 | reboot時の選択 | trusted generation |
| --- | --- | ---: |
| inactive erase後 | A / generation 7 | 7 |
| CODE後 | A / generation 7 | 7 |
| DICTIONARY後 | A / generation 7 | 7 |
| DATA後 | A / generation 7 | 7 |
| envelope後 | A / generation 7 | 7 |
| staged検証後 | A / generation 7 | 7 |
| marker本文後 | A / generation 7 | 7 |
| marker seal後 | B / generation 8 | 7 |

seal後はBが完全かつ正規署名済みなので起動候補になる。ただし、この時点ではBのboot成功がまだ
確認されていないため、minimum generationは7のままである。Bが起動失敗した場合はB markerを
quarantineし、Aへ戻れる。

## trusted generationの二重journal

minimum generationも単一cellへ上書きしない。二recordのうち古いvalid recordを残し、他方へ
次の順序で書く。

```text
1. erase next trusted record
2. write sequence + generation
3. seal record with checksum
```

起動時はchecksumが正しいrecordのうちsequence最大を読む。generation 7から8へのcommitで電源断を
注入すると、erase後は7、本文後も7、seal後だけ8になった。最新recordのchecksumを壊した試験では
旧record 7へ戻った。

trusted generationのcommitは、新slotのEd25519検証だけでなく、実際のboot成功報告後に行う。
commit途中で電源が切れてminimum値が7のままでも、sealed Bは再びgeneration 8として起動できる。

## 失敗・破損試験

- Bのboot失敗報告: BをquarantineしA／generation 7へ戻る。
- complete後・commit前のB component破損: signature／digest検査でBを除外しAへ戻る。
- marker checksum破損: Bをincompleteとして除外しAへ戻る。
- 正規署名済みgeneration 6: inactive slotを消去する前のpreflightで拒否し、Aは不変。
- trusted journal最新record破損: 旧valid recordを採用する。

## 明示的に残るrecovery境界

generation 8をtrusted minimumへcommitした後で、唯一のgeneration 8 slotが破損すると、Aの
generation 7は正規署名済みでもanti-rollbackにより起動できない。この場合、R0は`BootError`として
停止し、「A/Bだから必ず回復できる」とは主張しない。

次段階では、少なくとも次のいずれかが必要である。

- commit前にもう一方へ同generationのlast-known-goodを用意する。
- current generation以上の独立recovery imageを保護領域へ置く。
- 通常更新鍵とは別のrecovery trust anchorとphysical-presence条件を設ける。

古いAを無条件に起動するfallbackはanti-rollbackを破るため採用しない。

## checksumのsecurity境界

marker／journal checksumは、電源断・torn write・偶発破損の検出用であり、秘密を持たない。攻撃者は
再計算できる。しかしslot imageを変更すればEd25519署名が失敗し、generationを下げればpolicyで
拒否される。物理攻撃者によるmarker消去などのDoSは、このchecksumだけでは防げない。

## host modelの限界

- 各step後の状態をdurableと仮定し、実Flashのprogram unit、erase block、0→1制約をまだ扱わない。
- marker／recordの途中書込みは「本文あり・sealなし」で模擬し、bit単位のtorn writeではない。
- quarantine marker自身の電源断journalは未実装である。失敗時にBを再試行する可能性は残るが、
  未認証imageを起動することにはならない。
- wear leveling、bad block、ECC、write enduranceはtarget依存である。
- 実boot codeのwatchdogとboot-success判定は未実装である。

## 実装と確認

- `min0_core_forth_install.py`／`.rb`: A/B store、slot marker、trusted journal、boot選択
- `transactional_install_demo.py`／`.rb`: 全power-loss注入、破損、rollback、recovery境界
- `test_transactional_install.py`／`test_ruby_transactional_install.rb`: policy回帰
- `cross_transactional_install_check.py`: Python／Ruby状態遷移照合

post-commit corruptionにも耐えるrecovery image／recovery trust pathは`RECOVERY_PATH_R0.md`へ進んだ。
