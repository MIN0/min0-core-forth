# MIN0 CORE FORTH HMAC-SHA256／Ed25519比較 R0

## 目的

`THREAT_MODEL_R0.md`のT03（攻撃者が改変imageへ新digestを付け直す）に対し、共有鍵MACと
公開鍵signatureのどちらを、どのMIN0 CORE FORTH profileへ使うべきか比較する。これはhost上の
実験であり、target実装方式やpersistent認証blockはまだ凍結しない。

## 標準上の位置付け

- HMACは共有秘密鍵を使うmessage authentication codeである。
  [NIST FIPS 198-1](https://csrc.nist.gov/pubs/fips/198-1/final)に規定され、NISTは内容を
  SP 800-224へ移す計画を案内している。
- EdDSAは[NIST FIPS 186-5](https://csrc.nist.gov/pubs/fips/186-5/final)のdigital signature
  方式に含まれる。
- Ed25519の鍵・署名・検証形式とtest vectorは
  [RFC 8032](https://www.rfc-editor.org/info/rfc8032/)に記載される。

実装は独自暗号演算を書かず、Python `cryptography`とRuby OpenSSLを利用した。確認環境は
Python 3.12.13／cryptography 50.0.0、Ruby 4.0.3／OpenSSL 3.6.2である。

## 認証対象

両方式とも、次のdomain-separated messageを認証する。

```text
"MIN0-CORE-FORTH-IMAGE-AUTH-R0\0" || raw(identity_sha256)
```

実測message長は57 byteである。MIN0 CORE FORTH image以外の同じdigestへ署名を流用しにくくする
ため、用途名をmessageへ含めた。test keyは再現可能な公開fixtureであり実機へ使用してはならない。

## 実働結果

同一の実image identityへHMAC-SHA256 tagとEd25519 signatureを生成し、Python／Ruby間で
byte単位に一致した。

| 項目 | HMAC-SHA256 | Ed25519 |
| --- | ---: | ---: |
| 実機側key | 32-byte以上の秘密鍵 | 32-byte公開鍵 |
| 作成側key | 同じ秘密鍵 | 32-byte seed相当の秘密鍵 |
| tag／signature | 32 byte | 64 byte |
| 改変identity | 拒否 | 拒否 |
| wrong key | 拒否 | 拒否 |
| 検証実機のkeyで新認証値を作れるか | 作れる | 作れない |

host上の参考測定ではHMAC検証は数microsecond、Ed25519署名・検証は数十〜百数十microsecond
程度だった。ただしPython／Ruby／PC上の値であり、小規模MPUやFPGAの時間・ROM・RAMを
予測する値ではない。target実装を選ぶ際は別測定が必要である。

## 鍵漏えい時の差

### HMAC

検証する実機自身が秘密鍵を必要とする。その実機から鍵を抽出された場合、攻撃者は改変imageに
有効なtagを付けられる。全台で同じ共有鍵を使うと、一台の侵害が全台へ広がる。

per-device keyなら影響を一台へ限定できるが、署名hostは全device keyを安全に管理し、deviceごとに
異なるtagを生成する必要がある。少数controlled deviceでは成立し得る。

### Ed25519

実機は公開鍵だけで検証できる。実機の公開鍵が読まれても、それだけでは署名を生成できない。
秘密署名鍵をoffline hostなどへ隔離でき、同一署名imageを複数deviceへ配布できる。

ただし公開鍵を保存するloader自体が書換え可能なら、攻撃者は公開鍵ごと交換できる。公開鍵または
そのroot hashは、検証対象imageから独立したtrust anchorへ置く必要がある。

## profile別のR0推奨

### Development Profile

authentication `none`を許す。digestによる破損・取り違え検出だけを提供し、deployment用途と
誤認させない。

### Controlled Device Profile

HMAC-SHA256をoptional候補とする。条件はper-device key、鍵抽出riskの受容、host側key管理、
key rotation／recovery手順である。fleet全体の共通HMAC keyは推奨しない。

### Distributed Image Profile

Ed25519を第一候補とする。実機は公開鍵だけを保持し、秘密署名鍵は配布しない。複数台・一般公開に
おける侵害範囲と運用がHMACより明確である。

MIN0 CORE FORTHの母体はschemeを固定せず、`none`、optional HMAC、公開鍵signatureをprofileで選ぶ。

## 認証block統合前に完了したこと

unsigned 64-bit generationをcomponent、allocator、manifestと同じidentityへ含め、loaderが保持する
最低受入generationと比較するhost prototypeを実装した。正しく署名された古いimageも拒否し、
導入成功時だけtrusted stateを進める。詳細は`ANTI_ROLLBACK_R0.md`に保存した。

## 次の作業

1. generationを含むidentityのEd25519署名をauthentication blockへ格納する。完了。
2. key ID、署名長、unknown scheme、改変署名をfail-closedで検査する。完了。
3. persistent loader transactionと電源断安全なtrusted stateへ進む。

通常更新にdowngrade bypassを設けず、factory recoveryは独立した認証経路として扱う。
署名image統合の詳細は`SIGNED_IMAGE_R0.md`に保存した。
