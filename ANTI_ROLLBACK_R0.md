# MIN0 CORE FORTH anti-rollback generation R0

## 目的

正規署名を持つimageであっても、現在より古い版へ戻すrollbackを拒否する。対象は新規FORTHの
MIN0 CORE FORTH host prototypeであり、MSX0-FORTHには変更を加えない。

## image envelope v2

`generation`は0から`2^64-1`までのunsigned 64-bit整数である。負数、上限超過、整数以外を拒否し、
最大値から0へのwrapは許さない。generationを導入したため、旧schemaを同じversionとして解釈せず、
image envelope versionを1から2へ進めた。

後続のEd25519 authentication block統合では、認証鍵を選ぶ`key_id`もidentityへ結び付けるため、
envelopeをv3へ進めた。さらにnormal／recovery roleを結び付けるv4が現在の実装である。

generationはcomponent descriptor、allocator、manifest digest、authentication schemeとともに
`identity_sha256`へ含める。したがってgenerationだけを書き換えてもidentity検査と、そのidentityを
対象にしたMAC／署名検査に失敗する。

relocationは配置だけを変える操作であり、releaseの新旧を変えない。link後のenvelopeは新しい
component digestとidentityを持つが、generationは元imageからそのまま保持する。

## 最低受入generation

loaderは`minimum accepted generation`をinstall対象imageの外にあるtrusted stateへ保持する。

- candidateが最低値より小さい: rollbackとして拒否する。
- candidateが最低値と同じ: 再起動、検証、同版再導入のため受理する。
- candidateが最低値より大きい: 導入候補として受理するが、検査時点では最低値を進めない。

最低値をimage自身の中だけに置くと、攻撃者が古いimageと古い最低値を一緒に戻せる。そのため、
実機ではROM root、保護Flash、secure element、OTP／monotonic counterなど、targetごとに適切な
trust anchorが必要になる。

## commit-after-success

新generationの署名・identity・layoutを検査しただけではtrusted stateを変更しない。完全な書込みと
導入成功が確認された後にだけ`commit(generation)`を行う。途中で電源断や書込み失敗が起きた場合、
最低値を先に進めて再試行可能な旧slotまで起動不能にする事故を避けるためである。

今回の実験では最低値7に対しgeneration 8をpreflightし、失敗時は7のまま、成功commit後だけ8へ
進めた。その後はgeneration 7を拒否した。`TrustedGeneration`はこの規則のin-memory modelであり、
永続化の安全性までは提供しない。

## 署名との順序

実機loaderでは概念上、構文・長さ境界、component／identity、署名、generation policy、導入、commit
の順に扱う。認証されていないgeneration値でtrusted stateを進めてはならない。

実働試験ではgeneration 6、7、8の全identityに正しいEd25519署名を付けた。三署名すべての検証に
成功したうえで、最低値7がgeneration 6だけを拒否した。これは「署名が正しい」と「十分新しい」を
別々の条件として扱う試験である。後続作業で署名値をauthentication blockへ統合し、同じ規則を
loader API内で検証するところまで完了した。詳細は`SIGNED_IMAGE_R0.md`に保存した。

## recoveryとdowngrade

通常更新へ`--force-old`のようなdowngrade bypassは設けない。誰でも使える例外はanti-rollbackを
無効化するためである。factory recoveryや署名鍵事故への復旧が必要な場合は、別trust anchor、
物理presence、別署名keyなどを使う独立した認証経路として設計する。

generation枯渇時もwrapしない。`2^64-1`へ到達する前に、新しいtrust domainへの明示的migrationを
必要とする。

## resilienceとの関係

[NIST SP 800-193](https://csrc.nist.gov/pubs/sp/800/193/final)はplatform firmware resilienceを
保護・検出・回復の観点から扱う。本R0のgeneration検査は保護／検出の一部に相当するが、回復と
電源断耐性を満たすにはA/B slot、last-known-good、atomic commitが別途必要である。

## 実装と確認

- `min0_core_forth_image.py`／`.rb`: envelope v4、role／generation identity、minimum policy、Ed25519 block
- `min0_core_forth_generation.py`／`.rb`: image外trusted stateのin-memory model
- `anti_rollback_demo.py`／`.rb`: 正規署名済み旧image、失敗／成功commit、範囲境界
- `cross_anti_rollback_check.py`: Python／Rubyのidentity、signature、状態遷移一致

## 未実装と次作業

1. A/B slotとcomplete markerを用いたtransactional installを模擬する。host model完了。
2. trusted generationを二重化・checksum・sequence付きにし、各書込み位置の電源断を試験する。
   host model完了。
3. 実媒体のerase／program粒度とatomicityへ移植して再試験する。
4. key rotation／revocationとfactory recoveryの別trust pathを仕様化する。

host modelの詳細は`TRANSACTIONAL_INSTALL_R0.md`に保存した。

現段階ではdeployment-safe bootloaderを完成したとは主張しない。
