# MIN0 CORE FORTH Mobile Learning（個人学習用試作版）

`viewer/mobile-forth.html` は、iPhoneなどのブラウザ内だけでFORTHソースを編集・実行するための、1ファイル完結型教材です。通信、PC上のserver、外部ライブラリは使いません。

## 位置づけ

- 正式なMIN0 CORE FORTH処理系はPython版とRuby版です。
- Mobile Learningは、その学習しやすい部分をJavaScriptで再実装した互換サブセットです。
- セキュリティ境界、永続image、Monitor、dictionary capabilityなどの正式機能を検証する用途には使いません。
- 各「実行」は空のVMから開始します。必要なワード定義と呼び出しを同じソース欄へ書きます。

## できること

- 数値、スタック操作、算術、比較、論理演算
- `: name ... ;`によるcolon word定義
- `IF ELSE THEN`、`BEGIN`系、`DO`系の制御構造
- `.`, `.S`, `EMIT`, `CR`, `." ..."`による表示
- 実行後のデータスタックと、ワードごとのスタック遷移の確認
- ブラウザ内へのソース保存（iPhoneの表示方法によって使えない場合があります）
- 暴走防止の実行ステップ上限、ソース4096 UTF-8バイト上限

## 未対応

メモリ語、`CREATE DOES>`、`DEFER IS`、ファイル、通信、正式なimage／seal／Monitor機構には対応しません。

## iPhoneでの使用

1. iPhone用ZIPを「ファイル」アプリへ保存して展開します。
2. `MIN0_FORTH_MOBILE.html`をタップして開きます。
3. 例題を選ぶか、ソース欄へFORTHを書きます。
4. 「実行」を押し、端末出力、最終スタック、スタック遷移を確認します。
5. 「端末に保存」で下書きを保存します。保存できない表示環境では、ソースを長押ししてコピーしてください。

iOSの「ファイル」プレビューがJavaScriptを止める場合は、共有メニューからSafariなどJavaScriptを実行できる表示先を選びます。HTML自体はオフラインで動作し、外部へ通信しません。

## PC上での再生成と試験

```powershell
python tools/build_mobile_forth.py
node workbench/test_mobile_forth.js
python -m unittest workbench.test_mobile_forth -v
```
