# MIN0 CORE FORTH 0.1 既知の制限

[英語版はこちらです](KNOWN_LIMITATIONS_0.1.md)

対象：`0.1.0`と`0.1.1`

## 言語と互換性

- Forth標準への完全適合を主張しません。
- ワード集合は教育・実験のため意図的に小さくしています。
- 32ビット、little-endian、64 KiB仮想メモリは参照プロファイルであり、CORE全体の上限ではありません。
- 引用文字列は1文字1バイトです。UTF-8や日本語ソース文字列のtarget profileは未凍結です。
- API、image format、machine identifierは実験中の0.1インターフェースです。

## ホストと実機の境界

- PythonとRubyは実行可能仕様です。実MPU、FPGA、Flash、EEPROM、UART、TPMは含みません。
- 参照端末は任意の制御byteを実端末へ直接流さず、出力を決定的に収集します。
- Viewerは測定済みtraceを表示しますが、編集したsourceを実行しません。
- Spinel packageには現在対応していません。将来のSpinel側runtimeとlibrary対応に依存します。

## 安全上の境界

- 署名seedとHMAC鍵は公開fixtureであり、実配備の安全性を持ちません。
- 安全modelは方針と拒否動作の実験であり、認証ではありません。
- 信頼済みhost service handlerはVMでsandbox化されません。
- 資源枯渇、悪意あるhost code、side channel、fault injection、物理攻撃、build system侵害、
  実運用鍵管理は現在の保証外です。
- 開発modeは意図的にsource定義と実験を許します。W^Xと辞書保護は明示的なsealed safe-runtimeにだけ適用します。

## リリース境界

MIT Licenseは再利用を許可しますが、安全性や特定用途への適合を保証しません。公式repositoryは
<https://github.com/MIN0/min0-core-forth>です。`v0.1.0`は最初の版、`v0.1.1`は導線、package、文書を
改善した保守版です。Forkや改造版には識別できるbuild名またはversion suffixを付けてください。
