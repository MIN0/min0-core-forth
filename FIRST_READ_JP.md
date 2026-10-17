# まずは必ず最初にお読みください

[英語版はこちらです](FIRST_READ.md)

## 名前について

正式名称は**MIN0 CORE FORTH**です。`MIN0`は「ミノ」と読み、最後は英字のOではなく数字の0です。
以前から使ってきたニックネームと、ゼロから新しいFORTHの共通母体を育てる考えに由来します。

## 中心となる設計原則

> Forthの自由さを失わせず、危険な力を使うときだけ本人がはっきり自覚できる設計にする。<br>
> 通常利用者に安全な道と、理解した開発者が明示的に開く道を分ける。

Forth本来の力を取り上げるのではなく、普段は間違いが事故へ直結しにくい道を用意します。実行領域の
書換えや動的な呼出し先変更などの強い操作には、意図が分かる名前、権限、検証、記録を伴わせます。

## このリリースの目的

Python版とRuby版は、教育、研究、個人実験のためのリファレンスシステムです。

- FORTHを動かし、スタックと辞書を観察する
- 二つの独立した実行可能仕様を比較する
- Viewerで`CREATE`、constructor plan、`DOES>`を観察する
- 自分のワードを定義し、変更する
- CPU、MPU、FPGAなどへ向けた子FORTHをForkして育てる
- 実演、画面、動画を共有する

MIN0 CORE FORTHはMSX0-FORTHから独立しています。このリリース作業はMSX0-FORTHを変更しません。

## 現在の位置付け

**MIN0 CORE FORTH 0.1は教育・実験用の公式リファレンス版であり、製品向け安全認証済みruntimeでは
ありません。**

- PythonとRubyはホスト上で動く実行可能仕様です。
- A/B更新、署名、recovery、capabilityは将来の実機に向けた実働模型です。
- 収録された署名seedとHMAC鍵は、すべて公開試験用fixtureです。
- fixtureの署名は実製品や実リリースの真正性を証明しません。
- 実Flash、EEPROM、CPU保護mode、TPM、物理攻撃は検証していません。
- API、保存形式、ワード集合は将来の実験版で変わる可能性があります。
- Viewerはオフラインで動き、ネットワークやAIへトレースを送りません。

## どの機器で使えるか

「誰でも使える」と「その機器で実機確認済み」は別です。Mobile Learningは公開Webページであり、
GitHubアカウントや専用アプリを必要としませんが、ブラウザを持たないPico 2 Wでは直接実行できません。

| 機器 | 利用可否 | 現在の確認状況 | 利用方法と注意点 |
| --- | --- | --- | --- |
| Windows PC | 利用可能 | 実機確認済み | Chrome／Edgeなどで公開URLを開く |
| Mac／Linux PC | 原則利用可能 | 未評価 | 新しいSafari／Chrome／Firefoxなどを使う |
| Raspberry Pi 5 | ブラウザ版として原則利用可能 | 未評価 | Raspberry Pi OSのChromiumなどで開く。GPIOを直接操作する版ではない |
| Raspberry Pi Pico 2 W | 直接利用不可 | 対象外 | ブラウザと画面を持たない。将来は専用FORTH firmwareとMonitor接続の対象になる |
| iPhone | 利用可能 | Safari実機確認済み | HTTPSの公開URLをSafariで開く。「ファイル」アプリのHTML previewでは実行しない |
| Androidスマートフォン | 原則利用可能 | 未評価 | 新しいChromeなどで開く。すべての機種を保証するものではない |
| iPad／Android tablet | 原則利用可能 | 未評価 | Safari／Chromeなどで開く |

**[MIN0 CORE FORTH Mobile Learningを開く](https://min0.github.io/min0-core-forth/viewer/mobile-forth.html)**

各端末のFORTH sourceと下書きは、その端末のブラウザ保存領域に置かれます。FORTH sourceを外部serverや
AIへ送信しません。初回読込みにはnetworkが必要ですが、Webアプリを保存した端末ではoffline起動も
利用できます。Mobile Learningは学習用JavaScript subsetであり、正式なPython／Ruby reference実装の
全機能を備えたものではありません。

## ライセンスと安全性

本プロジェクトはMIT Licenseです。利用、変更、Fork、再配布を広く認めますが、安全性の認証や、
欠陥が存在しないという保証ではありません。

**[ライセンスと安全性](docs/LICENSE_AND_SECURITY_JP.md)**から、正式なライセンス、完了した監査、
既知の制限、脅威model、非公開の脆弱性報告方法を確認してください。

## Forth標準との関係

本プロジェクトはForth標準化団体から独立しており、標準化団体による公式実装ではありません。
「CORE」は将来の実機に共通する母体を表し、現段階ではForth標準への完全適合を主張しません。

## 公式版とFork

Forkや改造版を歓迎します。変更した配布物には固有のbuild名またはversion suffixを付け、原版の
監査結果を変更後のコードにも自動的に成立する証拠として扱わないでください。

公式リポジトリは[日本語版の入口](https://github.com/MIN0/min0-core-forth/blob/main/README_JP.md)です。
最初の版は`v0.1.0`、現在おすすめする
保守版は`v0.1.2`です。タグ、ZIP、SHA-256一覧、release notes、既知の制限、監査記録を公開しています。

公開済み評価用pre-release `v0.1.3-rc.1`、`v0.1.4-rc.1`、`v0.1.4-rc.2`には、互換性改善、
ブラウザ学習環境、仮想アセンブラbackend、Mobile Monitorと入力制御が段階的に含まれます。
次回候補`v0.1.4-rc.4`はSafe `VARIABLE`、検査付き`@`／`!`、Pause中の変数編集、`BREAK`に加え、
Ruby 3.4.11をWindows試験基準として明記した公開前候補です。正式版かつ安全レビュー済みの推奨基準が
必要な場合は`v0.1.2`を利用してください。

## 次回リリース候補を確認する場所

目的ごとに次の場所を確認します。

1. **実際に触る**：上記の[Mobile Learning](https://min0.github.io/min0-core-forth/viewer/mobile-forth.html)
   を開き、画面上部の`source build`を確認する。
2. **公開前の合否を見る**：**[0.1.4-rc.4候補監査](docs/RELEASE_AUDIT_0.1.4_RC4_JP.md)**で
   Gate A、Gate B、Gate Cのcheck欄を確認する。
3. **変更内容を読む**：**[0.1.4-rc.4 release notes](docs/RELEASE_NOTES_0.1.4_RC4_JP.md)**を読む。
4. **公開後の配布物を取得する**：GitHubの
   **[Releases](https://github.com/MIN0/min0-core-forth/releases)**で`v0.1.4-rc.4`を選び、
   ZIPと`SHA256SUMS.txt`を確認する。公開前は一覧に表示されない。
5. **開発中の最新内容を見る**：公式repositoryの`main`を見る。ただし、`main`は公開releaseより先の
   実験を含む場合があり、固定版が必要な場合は必ずtagとrelease assetを使う。

## 次の最優先作業：MIN0 Capability Tour

次の開発では、立ち上げたViewerの一か所から次の三つを体験できる**MIN0 Capability Tour**を作る。

1. Safe `VARIABLE`、`@`、`!`、Pause中編集を実際に操作する。
2. `CREATE DOES>`がwordを作る過程、成功、失敗、rollbackを検証済みtraceで理解する。
3. 仮想assemblerのreference実行、生成code、disassembly、現在の実機未対応範囲を確認する。

各項目は「試す内容」「最小source」「期待結果」「内部で起きること」「現在の制限と次段階」を同じ順番で
示す。PC、browser、Python／Ruby、Mobile、Picoのどこまで確認済みかも明記する。

## おすすめの順番

1. 上の機器別一覧で、自分の端末が実機確認済みか未評価かを確認する。
2. [Mobile Learning](https://min0.github.io/min0-core-forth/viewer/mobile-forth.html)を開く。
3. [日本語版Guided Viewer](https://min0.github.io/min0-core-forth/viewer/value-trace.html)を開く。
4. [日本語版Quick Start](docs/QUICKSTART_JP.md)を試す。
5. [日本語文書索引](docs/README_JP.md)を読む。
6. 安全関連実験は、明記された限界が自分の実験に適している場合だけ試す。
