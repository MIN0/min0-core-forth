# MIN0 CORE FORTH Mobile Learning（個人学習用試作版）

`viewer/mobile-forth.html` は、ブラウザ内だけでFORTHソースを編集・実行するための、1ファイル完結型教材です。外部ライブラリは使いません。

重要：iPhoneの「ファイル」プレビューはHTMLを表示してもJavaScriptを停止するため、入力欄は見えても実行ボタンは動きません。iPhoneではHTTPSへ配置したWebアプリ版をSafariで開きます。

## 位置づけ

- 正式なMIN0 CORE FORTH処理系はPython版とRuby版です。
- Mobile Learningは、その学習しやすい部分をJavaScriptで再実装した互換サブセットです。
- セキュリティ境界、永続image、Monitor、dictionary capabilityなどの正式機能を検証する用途には使いません。
- 各「実行」は空のVMから開始します。必要なワード定義と呼び出しを同じソース欄へ書きます。

## できること

- 数値、スタック操作、算術、比較、論理演算
- `: name ... ;`によるcolon word定義と`RECURSE`による再帰
- `( ... )`形式のコメントとstack effect表記
- `IF ELSE THEN`、`BEGIN`系、`DO`系の制御構造
- `KEY?`と`KEY`による上限付き実行中入力
- `VARIABLE`、`@`、`!`による検査付き1 cell変数
- `.`, `.S`, `EMIT`, `CR`, `." ..."`による表示
- 実行後のデータスタックと、ワードごとのスタック遷移の確認
- ブラウザ内へのソース保存（iPhoneの表示方法によって使えない場合があります）
- 暴走防止の実行ステップ上限、ソース4096 UTF-8バイト上限

## 未対応

`VARIABLE`以外の汎用メモリ語、`CREATE DOES>`、`DEFER IS`、ファイル、通信、正式なimage／seal／Monitor機構には対応しません。再帰は呼出し深さ64、全体は100,000実行stepで安全停止します。

## iPhoneでの使用

1. `tools/build_mobile_pwa.py`で作ったWebアプリZIPの内容をHTTPSの静的Webサーバーへ配置します。
2. iPhoneのSafariで配置先URLを開きます。
3. 例題を選ぶか、ソース欄へFORTHを書いて「実行」を押します。
4. 共有メニューから「ホーム画面に追加」を選び、「Webアプリとして開く」を有効にします。
5. 初回読込み後は必要ファイルがiPhoneへ保存され、オフラインでも起動できます。
6. 「端末に保存」で下書きをiPhone内へ保存します。

### 実行中入力

例題から「実行中の入力（KEY）」を選んで実行すると、状態が「入力待ち」になります。入力欄へ半角`A`を
入れて「入力を送る」を押すと、`KEY`はbyte値`65`をstackへ積み、処理を再開します。入力待ち中も一時停止、
安全停止、実行前への復旧を使用できます。

### 安全な変数

例題「安全な変数（VARIABLE @ !）」では、`VARIABLE SCORE`が0で初期化した1 cell変数を登録します。
`SCORE`は値そのものではなく、MIN0が発行した検査可能なアドレスをstackへ積みます。`@`は読出し、`!`は
書込みです。任意の数値をアドレスとして渡すと、実メモリへ触れずに`InvalidAddress`で停止し、失敗時の
stackを観察できます。「実行前へ復旧」を選ぶと、値・変数登録・割当位置をまとめて実行前へ戻します。

実行中に「一時停止」を押し、状態が「一時停止」へ確定すると、「安全な変数」表の変更buttonが有効に
なります。変更対象は登録済み変数の1 cell値だけで、名前や論理addressは変更できません。値は10進数または
`0x`形式で入力します。変更はMonitor履歴へ記録され、継続するとFORTHから新しい値を読めます。
「実行前へ復旧」ではMonitorから行った変更も取り消します。

Pause中に入力を保持したい場合は、「一時停止」を押した後、実行状態が「一時停止」へ変わるまで待ってから
入力を送る。要求中は入力欄を無効にし、確定前の送信を防ぐ。「ソースを消去」はsource欄だけを空にする。
実行結果、stack、trace、入力欄、例題選択を初期状態へ戻す場合は「画面を初期化」を使用する。端末へ保存した
sourceは画面初期化では削除しない。

FORTHソースは外部へ送信せず、ブラウザの`localStorage`へ保存します。Webアプリは更新確認以外の外部API通信を行いません。

## 結果をPDFへ保存する場合

印刷時は実行状態、stack、現在位置、呼出し履歴を残し、最大2000件の命令履歴と50件のワード辞典表は
省略します。長い実行履歴を含む結果でも、確認用PDFが数十ページへ膨らまないための表示です。詳細な
命令履歴とワード辞典は画面上に保持されます。

画面上部の`source build`は、自己完結HTMLを生成した時点のsource revisionです。GitHub Pagesへ配置した
commitそのものと一致しない場合がありますが、評価対象ファイルを識別するために使用します。

## PC上での再生成と試験

```powershell
python tools/build_mobile_forth.py
python tools/build_mobile_pwa.py --output "出力先\min0-forth-mobile-pwa.zip"
node workbench/test_mobile_forth.js
python -m unittest workbench.test_mobile_forth workbench.test_mobile_pwa -v
```
