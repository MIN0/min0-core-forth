# まずは必ず最初にお読みください！

## 名前について

このプロジェクトの正式名称は **MIN0 CORE FORTH** です。

```text
MIN0 CORE FORTH
^^^^
最後の文字は英字のOではなく、数字の0です。
読み方は「ミノ・コア・フォース」です。
```

`MIN0`は、開発者が以前から使ってきたニックネーム「みの」に由来します。数字の`0`には、コンピューターの
世界と、ゼロから育てる新しいFORTHの共通母体という意味も重ねています。

## MIN0 CORE FORTHが大切にすること

> **Forthの自由さを失わせず、危険な力を使うときだけ本人がはっきり自覚できる設計にする。**  
> **通常利用者に安全な道と、理解した開発者が明示的に開く道を分ける。**

これは、MIN0 CORE FORTHの安全機構が目指す中心原則です。利用者からForth本来の力を取り上げるのではなく、
普段は間違いが事故へ直結しにくい道を用意し、コード領域の書換えや動的な実行先変更などの強い力には、意図が
分かる名前、権限、記録、確認を伴わせます。初めて触る方は安全な道から始め、必要になったときに内部を学びながら
一段ずつ深く進めます。

## このリリースの目的

MIN0 CORE FORTHのPython版とRuby版は、FORTHを知らない方にも自由に触っていただくための、教育・研究・
個人実験用リファレンス実装です。

- FORTHを実際に動かしてみる
- Python版とRuby版を読み比べる
- stack、辞書、`CREATE`、`DOES>`の動きをGuided Viewerで観察する
- sourceを変更し、自分のwordや実験を追加する
- Forkして別のCPU、MPU、FPGA向けの子FORTHを育てる
- 面白かったことを周囲へ紹介し、画面や動画で共有する

利用者による研究、改造、Forkを妨げるためのシステムではありません。安全機構は、自由な開発版と、将来の
正式運用機で承認済みimageだけを導入する仕組みを分離するために研究しています。

## 現在の位置付け

**MIN0 CORE FORTH 0.1は、教育・実験用公式リファレンス版です。製品運用向けの安全性は保証しません。**

- Python／Ruby上で動くhost executable specificationです。
- A/B更新、署名、recovery、capabilityは将来の実機向け設計を観察する実働模型です。
- repositoryに含まれる秘密鍵seedは公開fixtureであり、試験専用です。
- 公開fixture鍵による署名は、実際の製品や配布物の安全性を証明しません。
- 実Flash／EEPROM、実CPUの保護mode、TPM等での安全性は未検証です。
- API、保存format、word setは実験の進展により将来の版で変更される可能性があります。
- Viewerはofflineで動作し、現在networkやAIへtraceを送信しません。

## ここを見てください：ライセンスと安全性

本リリースはMIT Licenseです。利用、改造、Fork、再配布を広く認めますが、MIT Licenseは安全性認証や
無欠陥の保証ではありません。

> **利用条件と安全性の根拠・限界を確認したい方は、**  
> **▶ [`LICENSE_AND_SECURITY.md`](docs/LICENSE_AND_SECURITY.md)を最初に確認してください。**

そこから、実際の`LICENSE`全文、公開前後の監査計画、監査結果、既知の制限、脅威model、非公開の
脆弱性報告方法へ進めます。「何でも安全」と主張するのではなく、確認済みと未確認を分けて公開します。

## Forth標準との関係

MIN0 CORE FORTHは独立した教育・研究プロジェクトであり、Forth標準化団体による公式実装ではありません。

本プロジェクト名の`CORE`は、さまざまなCPUやFPGA向けFORTHの共通母体という設計思想を表します。現時点で
Forth標準への完全適合を主張しません。標準word setへの対応状況は、実装と試験が整った段階で別表として
明示します。

## Fork版と公式版

Forkや改造版が動作することは、問題ではなく本プロジェクトの目的の一つです。ただし、利用者が原版と改造版を
区別できるよう、公式1stリリースでは次を用意する予定です。

- `MIN0 CORE FORTH 0.1`という固定version
- 公式repositoryのrelease tag
- 配布artifactのSHA-256一覧
- Python／Ruby共通test vectorとcross-language試験結果
- release notesと、既知の制限一覧
- 起動画面、Viewer、生成traceに実装名とversionを表示
- `RELEASE_SECURITY_AUDIT_PLAN.md`の公開直前・公開後監査を完了した記録

内容を変更したForkは、その変更を隠さず、独自のbuild名またはversion suffixを付けることを推奨します。

公式repositoryは <https://github.com/MIN0/min0-core-forth> です。公式1stリリースは`v0.1.0`、
利用者による実行確認を反映した保守版は`v0.1.1`です。各版のrelease notesと監査記録から、
公開内容と確認結果を追跡できます。

## 安全機構を試す方へ

認証必須profileでは、改変後に元の署名を付けたimage、署名なしimage、未知の鍵で署名したimage、古い
generationを拒否する実験があります。ただし、現在のfixture鍵は公開されているため、この動作を実運用の
security保証として使用しないでください。

通常のFORTH体験やGuided Viewerの利用に、root rotationや署名鍵の知識は必要ありません。興味を持った方だけ
security demoへ進める構成を目指します。

## 最初に試す順番

1. **[Guided Viewerを開く](https://min0.github.io/min0-core-forth/viewer/value-trace.html)**。案内に沿って`VALUE:`と`ANSWER`の動きを見る。
2. **[Quick Start](docs/QUICKSTART.md)**に従い、Python版またはRuby版で[`hello.fth`](workbench/examples/hello.fth)を実行する。
3. [README](README.md)の実行例と[設計文書](docs/)を読み、好きなwordを追加する。
4. 興味があれば[実装・試験用workbench](workbench/)で署名、A/B更新、recovery、capabilityのdemoを試す。

## 今後整理する事項

- Forth標準word setとの対応表

これは今後の互換性説明をより明確にするための作業であり、`0.1.1`の利用を妨げる項目ではありません。
