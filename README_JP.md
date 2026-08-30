[Click here to read the English version](README.md)

# MIN0 CORE FORTH

> [!IMPORTANT]
> ## まずは必ず最初にお読みください
>
> `MIN0`は「ミノ」と読み、最後の文字は英字の`O`ではなく数字の`0`です。
> MIN0 CORE FORTHは、FORTHを初めて体験する方と、その奥深い仕組みを調べたい方のための
> 教育・実験用リファレンス実装です。
>
> **[公開目的、安全上の位置付け、公式リリースの見分け方](FIRST_READ_JP.md)**
>
> **[MIT Licenseと安全性の保証は別の約束です](docs/LICENSE_AND_SECURITY_JP.md)**

**MIN0 CORE FORTH 0.1 — 教育・実験用リファレンスリリース**

現在のリリース：`0.1.1`<br>
公式リポジトリ：[日本語版の入口](https://github.com/MIN0/min0-core-forth/blob/main/README_JP.md)<br>
リリースタグ：`v0.1.1`

## まず試してみる

1. **[日本語版Guided Viewer](https://min0.github.io/min0-core-forth/viewer/value-trace.html)**を開きます。
2. PythonまたはRubyで**[5分間のQuick Start](docs/QUICKSTART_JP.md)**を試します。
3. 端末の横に**[ワード・ポケットリファレンス](docs/WORD_REFERENCE_JP.md)**を置きます。`WORDS`に
   表示される全ワードと、`DEFER`による動的切替えの入口を説明しています。
4. **[なぜRubyとPythonで始めたのか](docs/PROJECT_ORIGIN_JP.md)**を読みます。
5. **[日本語文書索引](docs/README_JP.md)**から設計と監査を調べます。

Viewerは単独で動作します。測定済みトレースを表示しますが、編集したソースを実行したり、
トレースをネットワークへ送信したりしません。

## このプロジェクトについて

MIN0 CORE FORTHは、CPU、MPU、FPGA、そのほかの対象に向けたFORTHシステムが育っていくための、
共通の母体を作る実験として始まりました。MSX0-FORTHとは独立しており、リリース済みの
MSX0-FORTHを変更しません。

Python版とRuby版は実行できる仕様であり、最終的な実機ではありません。同じFORTHの動作を二つの
言語で独立して表現することで、実CPUやメモリ制限を決める前に、曖昧さ、思い込み、移植上の誤りを
見つけます。

本プロジェクトはForth標準化団体から独立しており、現時点でForth標準への完全適合を主張しません。
ここでの「CORE」は、将来のさまざまな実装に共通する根を表します。

## リポジトリの構成

| 場所 | 内容 |
| --- | --- |
| `viewer/` | 日本語版と英語版の単独動作するGuided Viewer |
| `workbench/` | Python／Ruby実装、試験、例題、共通ベクトル |
| `docs/` | 言語別の入口文書、仕様書、監査記録 |
| `tools/` | リリース監査と再現可能なパッケージ作成工具 |

最上位には、入口文書、ライセンス、安全方針、版番号、依存関係、パッケージ制御など、
最初に必要なファイルだけを置きます。

## 固定した参照プロファイル

- 2の補数符号付き解釈を持つ32ビットセル
- 32ビットのバイトアドレス
- リトルエンディアンのセル表現
- 8ビット命令コードと32ビット即値オペランド
- 統一64 KiB仮想メモリ参照プロファイル（CORE全体の上限ではありません）
- 論理的に分離したデータ、リターン、ループの三つのスタック
- 最初の実行モデルでは絶対アドレスによる分岐と呼出し
- Forthの真は`0xFFFFFFFF`、偽は`0`
- 不正命令、スタック制限、不正メモリアクセスに対する決定的なエラー

## リリース0.1.1に含まれるもの

- 同じバイトコードと辞書動作を独立して実装したPython版とRuby版
- オーバーフローとアンダーフローを明示的に検査する三つのスタック
- 実行時辞書と対話的なコロン定義
- 条件分岐と回数指定ループ
- `CONSTANT`、`VARIABLE`、`CREATE`、constructor plan、ソースレベルの`DOES>`
- 起動時のワードと利用者の追加定義を区切って表示する`WORDS`
- `EMIT`、`CR`、`TYPE`、`S"`、`."`による文字と文字列の出力
- CODE、DICTIONARY、DATAの分離と型付きrelocationの実験
- バイトコード検証、読出し専用DATA、CODE封印、W^X公開モデル
- `DEFER`と認証済みMonitorによる切替え実験
- 署名image、anti-rollback、A/B導入、recovery、trust rotation、capabilityの各モデル
- 成功、rollback、constructor、文字出力をワード単位で観察できるGuided Viewer
- PythonとRubyの対話実行および無表示ファイル実行launcher

これらの安全関連機能は、実際に動かせる実験です。製品や実機が安全認証を受けたという意味ではありません。

## ホスト実装を動かす

展開したリポジトリの最上位から実行します。

```powershell
python workbench/min0_forth.py
ruby workbench/min0_forth.rb
```

表示を抑えたファイル実行は次のとおりです。

```powershell
python workbench/min0_forth.py -z workbench/examples/hello.fth
ruby workbench/min0_forth.rb -z workbench/examples/hello.fth
```

どちらも次の一行だけを表示します。

```text
Hello from MIN0 CORE FORTH
```

どちらかの対話型launcherで次を試せます。

```forth
WORDS
2 3 +
2 3 4 * + .
2 3 * 4 + .
: SQUARE DUP * ;
5 SQUARE .
BYE
```

Windowsでのフォルダー確認、必要な版、Ruby／Pythonの実行方法、問題発生時の確認は、
**[Quick Start](docs/QUICKSTART_JP.md)**を参照してください。起動時の全ワードについて、stack effect、
使える場所、短い意味を調べるには**[ワード・ポケットリファレンス](docs/WORD_REFERENCE_JP.md)**を使います。

## 検証結果

公開した`v0.1.1`と、独立して取得したタグ付きソースで、次を確認しました。

- Python 291テスト
- Ruby 46テストファイル
- Python／Ruby相互検査49ファイル
- 360ファイルのパスと内容の比較（相違0）
- Viewerのオフライン動作と、トレース文字列を命令として扱わないこと
- パッケージの再現性とSHA-256の一致

完了した証拠は**[0.1.1リリース監査](docs/RELEASE_AUDIT_0.1.1_JP.md)**に記録しています。

## ライセンスと安全上の境界

ソースと文書はMIT Licenseで公開します。著作権表示と許諾表示を残すことを条件として、利用、変更、
Fork、再配布が可能です。ただし、安全性の認証、脆弱性がないという証明、特定用途への適合保証では
ありません。日本語での入口は**[ライセンスと安全性](docs/LICENSE_AND_SECURITY_JP.md)**を参照してください。

収録した署名seedとHMAC鍵は、すべて決定的に作られた公開試験用fixtureです。実機、リリース、更新、
配備には絶対に使用しないでください。実験を運用上の安全機構として扱う前に、
**[既知の制限](docs/KNOWN_LIMITATIONS_0.1_JP.md)**も確認してください。

脆弱性を報告するときは**[日本語の報告案内](SECURITY_JP.md)**に従ってください。未修正の脆弱性、
攻撃手順、秘密鍵、アクセストークン、個人情報を公開Issueへ書かないでください。

## 現在の範囲

本リリースには、実際のMPU、FPGA、Flash、EEPROM、UART、TPM、ハードウェアメモリ保護対象は
含まれません。API、image format、machine identifierは実験中の0.1インターフェースです。将来の
実機版では、メモリ制限、入出力契約、永続化、鍵の保管、ハードウェア固有の保護を改めて評価します。
