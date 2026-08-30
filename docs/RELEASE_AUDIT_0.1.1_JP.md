# MIN0 CORE FORTH 0.1.1 保守版リリース監査

[英語版はこちらです](RELEASE_AUDIT_0.1.1.md)

状態：Gate A、Gate B、Gate Cすべて合格。`v0.1.1`を公開し、公開物を独立して再取得して検証済みです。

## 対象範囲

`0.1.1`は`0.1.0`のFORTHの意味を変更しません。リポジトリ整理、初心者向け手順、Viewerへの導線、
内部会話記録の公開防止、release tool試験を対象とした保守版です。`v0.1.0`のtagと配布物は履歴として
変更せずに保存しています。

## Gate A：公開前

- 公開allowlist：360ファイル、問題0
- Python：291テスト合格
- Ruby：46テストファイル合格
- Python／Ruby相互検査：49ファイル合格
- 独立した二回の`0.1.1` ZIP生成：バイト単位で一致
- GitHub secret-scanning alerts：0
- GitHub Dependabot alerts：0
- GitHub Pages：HTTPSを強制して構築完了

## Gate B：公開

- [公式v0.1.1リリース](https://github.com/MIN0/min0-core-forth/releases/tag/v0.1.1)
- 公開日時：2026-08-30 19:32:47（日本時間）
- tag commit：`d7647492bc4071d4543e9547f84b485d79462706`
- 配布物：`min0-core-forth-0.1.1.zip`、583705バイト
- SHA-256：`7ccfcbafe09d88d92759eae7cdaa031b03e3b0816f7882016316707f802b43eb`
- draftでもpre-releaseでもない通常リリース

## Gate C：公開後

- 公開ZIPと`SHA256SUMS.txt`を新しいフォルダーへ取得し、SHA-256一致を確認
- ZIP内の監査対象360ファイルと、独立取得したtag付きソースを比較し、欠落、余分、内容差すべて0
- ZIP展開物とtag付きソースの両方で、監査、Python 291、Ruby 46、相互検査49に合格
- 公開Viewerとtag側ViewerのSHA-256が完全一致
- 公開後もsecret scanningとDependabotのalertは0

Windows標準HTTPS clientでは、このPC固有の資格情報／TLS層の問題が再発しましたが、Python同梱の
OpenSSL経路で同じ公開tag付きZIPを取得できました。リリース内容の失敗ではありません。

本監査はMIN0 CORE FORTHだけを対象とし、MSX0-FORTHを変更または公開していません。
