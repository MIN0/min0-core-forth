# 安全方針

[英語版はこちらです](SECURITY.md)

## 対象リリース

現在の安全レビュー対象は`0.1.2`です。MIN0 CORE FORTHは教育・実験用リファレンス実装であり、
製品向け安全認証済みruntimeではありません。MIT Licenseは著作権上の許可であり、安全性を認証しません。

## 脆弱性を報告する

未修正の脆弱性、攻撃手順、秘密鍵、access token、個人情報を公開Issueへ書かないでください。
公式repositoryの非公開報告窓口を使用してください。

<https://github.com/MIN0/min0-core-forth/security/advisories/new>

通常の利用質問、文書の誤り、すでに公開済みの設計議論は公開Issueで扱えます。

## 公開試験鍵

repository内のEd25519 seedとHMAC鍵は、すべて決定的に生成した公開試験用fixtureです。実機、release、
update、deploymentの署名や認証には絶対に使用しないでください。fixture署名は例題の経路が動くことだけを示します。

## 対象外

参照試験はbytecode構造、型付きrelocation、署名image実験、anti-rollback、A/B導入、recovery、capability、
W^X、service登録、stack limit、失敗時rollbackを扱います。side channel、fault injection、hostやcompilerの
侵害、物理攻撃、DoS、将来のhardware portのバグに対する耐性を証明しません。

詳細は[既知の制限](docs/KNOWN_LIMITATIONS_0.1_JP.md)を参照してください。
