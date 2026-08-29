# MIN0 CORE FORTH digest-bound image envelope R0

## 目的

正しいrelocation manifestを別のCODE／DICTIONARY／DATA imageへ誤適用する事故を、最初の
patchより前に検出する。同時にallocator metadataを同じidentityへ結び付ける。

このR0はintegrity（破損・取り違え検出）の候補であり、authenticity（作成者の真正性）を
保証しない。persistent binary形式もまだ凍結しない。

## envelopeが結び付けるもの

- format、version、Reference32-LE profile、execution profile
- unsigned 64-bit generation
- CODE、DICTIONARY、DATAそれぞれのbase、使用byte数、region limit、SHA-256
- CODE-HERE、header HERE、data HERE、LATEST
- 統合relocation manifestとそのSHA-256
- authentication scheme

これらをcanonicalな配列としてSHA-256へ入力し、`identity_sha256`を作る。componentが1 byte、
allocator値が1 cell、manifestのkindが1文字変わってもidentityは変化する。

## 二段階のdigest

1. component digestは、渡されたraw CODE／DICTIONARY／DATAがenvelope記載のbyte列と同じか
   検査する。
2. identity digestは、component descriptor、allocator metadata、manifest digest、
   authentication状態の組合せが変更されていないか検査する。

manifest digestだけではimageとの組合せを識別できない。component digestだけではLATESTや
HEREの取り違えを識別できない。identityは両者を一組にする。

## allocator検査

- CODE-HEREは`CODE base + CODE size`と一致する。
- header HEREは`DICTIONARY base + DICTIONARY size`と一致する。
- data HEREは`DATA base + DATA size`と一致する。
- LATESTは0、または使用中DICTIONARY内のcell-aligned addressである。
- 各componentはregion limitを越えず、三regionのcapacity範囲は重ならない。

link後は各HEREを新baseと同じ使用byte数から再計算し、LATESTにはDICTIONARY差分だけを加える。
新component digestと新identityを持つ別envelopeを生成する。generationは変更せず保持する。

## 実働試験

68 recordを含む実imageからgeneration 7、role `normal`のsource envelope v5を作り、Python／Rubyで
同じunsigned identityを得た。三領域を`+0x1000`移動すると、新しいcomponent digestとallocator値を反映した別identity
になる。移動後のcolon word、条件分岐、loop、VARIABLE、DOES wordも従来どおり実行できた。

次をpatch前に拒否した。

- 同じmanifestを1 byte異なるCODE imageへ適用
- 別image用envelopeを元imageへ適用
- allocator metadataだけを変更
- manifest recordだけを変更
- authentication必須policyで未認証imageをload

## 悪意ある攻撃との境界

現在の`authentication.scheme`は明示的に`none`である。SHA-256は偶発的破損や取り違えを
検出できるが、攻撃者がimageとdigestを両方作り直すことは防げない。

validatorには`require_authentication` policyを設けた。このpolicyが有効な環境では、scheme
`none`をfail-closedで拒否する。現時点では署名済みschemeを実装していないため、認証必須modeで
受理されるimageはまだ存在しない。この明示的な拒否により、digestを署名と誤認して実機へ
deployすることを防ぐ。

## 次のsecurity検討

- 小規模system向け共有鍵MAC（例: HMAC）の鍵管理と更新方法
- 公開鍵signatureのROM／RAM／実行時間cost
- generation最低受入値を永続化する電源断安全なtrusted storage
- 鍵漏えい・署名鍵紛失時のrecovery
- bootloaderがどこまでをtrusted computing baseとして検証するか

この次段階は`THREAT_MODEL_R0.md`で整理した。認証方式を選ぶ前に「誰が、何を、どの接続経路から
変更できるか」を明確にした。悪意ある再buildは現在もgapだが、rollbackはgeneration最低受入値で
拒否するhost prototypeまで進んだ。
HMACと公開鍵signatureの比較後、generation-based anti-rollbackを`ANTI_ROLLBACK_R0.md`へ実装した。
Ed25519 authentication blockのenvelope統合は`SIGNED_IMAGE_R0.md`まで完了した。
`execution_profile`の署名統合とLoader policyは`IMAGE_EXECUTION_PROFILES_R0.md`へ進んだ。
実CODE、命令境界、typed relocation、capabilityの二重照合は`BYTECODE_VERIFIER_R0.md`へ進んだ。
