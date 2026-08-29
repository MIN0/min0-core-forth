# MIN0 CORE FORTH trust bundle and key rotation R0

## 目的

normal／recovery image署名鍵を安全に追加・失効し、鍵漏えい時にその鍵で署名されたimageを拒否する。
同時にrecovery image自身を新鍵へA/B更新する。対象は新規FORTHのhost executable specificationであり、
MSX0-FORTHには変更を加えない。

## trust hierarchy

```text
offline root private key
        |
        | signs
        v
trust bundle (epoch, role, active/revoked image keys)
        |
        | selects public key by role + key_id
        v
normal / recovery signed image envelope v4
```

実機にはroot public keyをpinする。image署名鍵は直接固定せず、root署名済みtrust bundleから選ぶ。
image署名鍵が漏れた場合、新しいbundleでそのkey IDを`revoked`にできる。

root private keyは通常image build hostから分離したoffline保管を前提とする。root自身の計画的な交代は
`ROOT_ROTATION_R0.md`のcross-signed policy chainへ進んだ。ただしrootがすでに侵害された場合、
攻撃者は任意鍵をactiveにできるため、cross-signだけでは侵害を識別できない。

## trust bundle v1

bundleは次を持つ。

- format／version
- unsigned 64-bit `epoch`
- pinned rootを選ぶ`root_key_id`
- key entryのcanonical key-ID順配列
- root Ed25519 signature

key entryは次の4 fieldだけを持つ。

```text
key_id
role            normal | recovery
public_key_hex  32-byte Ed25519 raw public key
status          active | revoked
```

roleとstatusを含むbundle payload全体をdomain-separated messageとしてroot署名する。key追加、role変更、
activeへの戻し、revokedへの変更はいずれもroot署名なしには成立しない。duplicate key ID、unknown role、
unknown status、余分fieldを拒否する。

revoked entryをすぐ削除せずbundleへ残すことで、「そのkey IDは未知」ではなく「明示的に失効済み」と
いう状態を署名対象に保てる。

## bundle epochと二段journal

古い正規bundleを戻してrevoked鍵を再びactiveにする攻撃を防ぐため、bundleにmonotonic epochを持つ。

bundle本体はA/B trust slotへ次の順序で書く。

```text
erase inactive trust slot
write root-signed bundle
seal trust slot with checksum
```

minimum accepted trust epochは、image generationと同様に二record journalへ書く。

```text
erase next epoch record
write sequence + epoch
seal epoch record
```

bundle slot seal前の電源断ではepoch 1が可視、seal後はepoch 2が可視になる。ただしminimum epochは
loaderでの利用成功後にcommitし、epoch record seal後だけ2へ進む。

checksumはtorn write検出用で、攻撃者への認証はroot signatureが担当する。

## 正しいrotation順序

鍵を安全に替えるにはoverlap期間が必要である。

```text
epoch 1: old normal active, old recovery active
epoch 2: old + new normal active, old + new recovery active
         -> new normal imageを検証・起動
         -> new recovery imageをA/B更新・起動
epoch 3: old normal revoked, new normal active
epoch 4: old recovery revoked, new recovery active
```

新鍵をactiveにしただけでは旧鍵を直ちに失効しない。新鍵で署名された実imageが対象deviceで起動できる
ことを確認してから旧鍵をrevokedにする。

## normal key rotationの実働結果

epoch 2のoverlap中は、old normal keyで署名したgeneration 8とnew normal keyで署名したgeneration 9を
両方受理した。epoch 3ではold key entryをrevokedにし、generation 8の署名自体が正しくても拒否した。
new keyのgeneration 9は引き続き受理した。

key revocationとgenerationは別条件である。十分新しいgenerationでもrevoked keyなら拒否する。

## recovery image自身の更新

recovery A/B storeへ既存transactional installerを`required_image_role=recovery`で適用した。

- A: recovery generation 1、old recovery key
- B candidate: recovery generation 2、new recovery key
- trust bundle: epoch 2でold／new両recovery keyがactive

8書込み地点へ電源断を注入し、complete-marker seal前の7地点ではA／generation 1、seal後だけB／
generation 2を選んだ。Bのboot成功後にrecovery minimumを2へcommitした。

その後epoch 4でold recovery keyをrevokedにしても、new keyで署名されたBは起動できた。

## 危険な順序

recovery generation 2を導入する前にepoch 4へ進め、old recovery keyをrevokedにすると、Aの
generation 1は署名が正しくても起動不能になる。この失敗を実働で再現した。

したがって「new key追加 → new recovery導入 → boot成功 → generation commit → old key失効」の順序は
単なる運用推奨ではなく、recoverabilityを維持する必須transactionである。

## 攻撃監査

次を拒否した。

- pinned rootとは異なる秘密鍵で署名した偽bundle
- root署名後にkey statusを変更したbundle
- minimum epoch 4の状態へepoch 1 bundleを再導入
- revoked normal keyで署名されたimage
- revoked recovery keyしか存在しない旧recovery image

## host modelの限界

- root public key自体のrotationは`ROOT_ROTATION_R0.md`でhost modelまで実装した。
- root key紛失・侵害時のmulti-root／threshold recoveryは未実装。
- keyの有効開始・終了時刻は持たない。小規模targetに信頼時計がないため、R0は明示epochを使う。
- bundle配布fileのpersistent binary parserとsize上限は`PERSISTENT_PACKAGE_R0.md`でhost modelまで実装した。
- minimum epoch storageの実Flash atomicity、wear、ECCはtarget依存。
- revocation理由、署名日時、監査log、device群への反映確認は未実装。
- epoch commit後に唯一のcurrent bundleが破損した場合のroot-level factory recoveryは未実装。

## 実装と確認

- `min0_core_forth_trust.py`／`.rb`: canonical bundle、root署名、active key解決、epoch journal
- `trust_rotation_demo.py`／`.rb`: 四epoch、normal rotation、recovery A/B更新、攻撃監査
- `test_trust_rotation.py`／`test_ruby_trust_rotation.rb`: vectorと順序回帰
- `cross_trust_rotation_check.py`: Python／Ruby bundle署名・状態遷移照合

bounded persistent input parserとの統合は`LOADER_STATE_MACHINE_R0.md`へ進んだ。候補bundleが現在の
normal／recovery両imageを検証できなければ、trust slotへの書込み前に拒否する。
