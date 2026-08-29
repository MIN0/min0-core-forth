# MIN0 CORE FORTH Ed25519 signed image envelope R0

## 目的

攻撃者がimageを改変し、新しいSHA-256 digestまで作り直す攻撃を、image外のtrusted public keyで
拒否する。対象は新規FORTHのMIN0 CORE FORTH host prototypeであり、MSX0-FORTHには変更を加えない。

## envelope v3 authentication block

```text
authentication:
  scheme:        "ed25519"
  key_id:        "fixture-ed25519-01"
  signature_hex: 128 lowercase hex characters
```

`scheme`と`key_id`はcanonical identityへ含める。`signature_hex`はそのidentityへ署名した結果なので、
循環を避けてidentity計算から除外する。identityにはgeneration、三componentのdigestと配置、allocator、
manifest digestも含まれるため、それらのいずれかを変更すると署名検証に失敗する。

`key_id`をidentityへ含めたことで、攻撃者は署名を保ったまま検証鍵の選択だけを差し替えられない。
このidentity schema変更を旧v2と同じversionとして扱わず、envelopeをv3へ進めた。

後続の独立recovery pathでは`image_role`（`normal`／`recovery`）もidentityへ追加し、envelopeをv4へ
進めた。v3は署名block統合段階、v4が現在のschemaである。

## trust store

loaderは`key_id -> 32-byte Ed25519 public key`の対応をimage外から受け取る。image自身が持参した
公開鍵を無条件に信頼すると、攻撃者が自分の鍵と署名を一緒に置けるためである。

次をfail-closedで拒否する。

- unknown `key_id`
- trust storeなし
- public keyが32-byte raw keyでない
- wrong public key
- unknown authentication scheme
- authentication blockの余分・不足field
- 64-byteでない、またはlowercase hexでないsignature

現在の公開fixture keyは相互照合用であり、deployment keyとして使用してはならない。

## 検証順序

概念上の順序は次のとおりである。

1. envelopeの型、version、profile、整数・長さ境界を検査する。
2. component digest、allocator、manifest、identityを検査する。
3. image外trust storeから`key_id`に対応する公開鍵を選ぶ。
4. domain-separated message上のEd25519 signatureを検証する。
5. 正規署名を確認後、minimum generationと比較する。
6. installを実行し、成功後だけtrusted generationをcommitする。

認証されていないgenerationでtrusted stateを進めてはならない。本実装でも署名検査後にrollback
policyを適用する。

## relocation境界

relocationはcomponent bytes、base、allocator、identityを変更する。したがって署名済みsource imageを
実機loaderがrelocationし、その結果を未署名imageとして保存する処理は認めない。

R0では次のbuild-host手順を採用する。

```text
source components -> target layoutへlink -> target identityを作成 -> Ed25519署名 -> 配布
```

署名済みenvelopeを`link_image_envelope`へ渡すと、署名を正しく検証した後でも「build-hostでの再署名が
必要」として拒否する。実験ではunsigned sourceをtargetへlinkし、target identityへ再署名したimageが
Python／Ruby双方で検証に成功した。generationは配置変更では進めない。

## 実働監査

正規署名imageを受理し、次の12ケースを拒否した。

1. componentを1 byte改変
2. signatureを1 nibble改変
3. signature長を破壊
4. key IDだけを改変
5. unknown authentication scheme
6. authentication blockへ余分な公開鍵fieldを追加
7. 正しく署名されているがunknown key ID
8. trusted key IDへwrong public keyを設定
9. trust storeを渡さない
10. secure modeへunsigned imageを投入
11. 正規署名済みだがminimum generationより古い
12. 署名後に再署名なしでrelocation

Python／Rubyはv4 normal signed identity
`e28fa460007f8d8e5a21d2359b527ba8c2af55f6c6926e52d191261544169dbe`、signature、全拒否結果、
最終配置へ再署名したidentityまで一致した。

## 実装

- `min0_core_forth_image.py`／`.rb`: signed envelope構築、trust-store検証、relocation境界
- `signed_image_demo.py`／`.rb`: 正常系、10拒否ケース、target再署名
- `test_signed_image.py`／`test_ruby_signed_image.rb`: 固定vectorとpolicy回帰
- `cross_signed_image_check.py`: Python／Ruby byte単位相互照合

## 当時未実装だった後続項目

- persistent binary parserとfile length上限は`PERSISTENT_PACKAGE_R0.md`でhost modelまで進んだ。
- trust store永続化とkey rotation／失効は`TRUST_ROTATION_R0.md`まで進んだ。
- root rotationは`ROOT_ROTATION_R0.md`まで進んだ。
- A/B slot、complete marker、電源断atomicityは`TRANSACTIONAL_INSTALL_R0.md`のhost modelまで進んだ。
- boot ROMからloader自身までのchain of trust

したがって、これは署名検証部のhost executable specificationであり、deployment-safe bootloaderの
完成を意味しない。transactional installとpower-loss試験は`TRANSACTIONAL_INSTALL_R0.md`へ進んだ。
