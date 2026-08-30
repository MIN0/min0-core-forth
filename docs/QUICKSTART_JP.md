# MIN0 CORE FORTH Quick Start

[英語版はこちらです](QUICKSTART.md)

このリリースには同等のPython版とRuby版があります。GitHub上でこのページを表示するだけでは、
実行ファイルはPCへ入りません。最初にソース一式を取得してください。

## 0. ソースを取得して最上位を開く

Windowsで最も簡単な手順です。

1. [公式リポジトリの日本語版入口](https://github.com/MIN0/min0-core-forth/blob/main/README_JP.md)で
   **Code → Download ZIP**を選びます。
2. ZIPを展開します。通常は`min0-core-forth-main`というフォルダーになります。
3. エクスプローラーで、`viewer`、`docs`、`workbench`ではなく、`min0-core-forth-main`そのものを開きます。
4. アドレスバーをクリックし、`powershell`と入力してEnterを押します。同じフォルダーで開く場合は
   **ターミナルで開く**でも構いません。
5. 次を実行して最上位にいることを確認します。

```powershell
Get-Location
Split-Path -Leaf (Get-Location)
Test-Path .\requirements.txt
Test-Path .\workbench\min0_forth.py
```

最後の三つは`min0-core-forth-main`、`True`、`True`になるはずです。この文書のコマンドは、すべて
この最上位から実行します。

`False`の場合は、まだ導入コマンドを実行しないでください。例えば現在位置の末尾が`viewer`なら、
一段上へ戻して再確認します。

```powershell
Set-Location ..
Get-Location
Test-Path .\requirements.txt
```

`Could not open requirements file`は、通常はフォルダー位置が違うという意味であり、MIN0 CORE FORTHや
`pip`が壊れているという意味ではありません。

## 必要な環境

- Python 3.12と`cryptography` 50.0.0、または
- Ruby 4.0とOpenSSL 3.x

Pythonを確認して、固定した依存関係を自分の仮想環境へ導入します。

```powershell
python --version
python -m pip install -r .\requirements.txt
```

RubyとOpenSSLを確認します。

```powershell
ruby --version
ruby -ropenssl -e 'puts OpenSSL::OPENSSL_VERSION'
```

Ruby版はRubyに付属するライブラリを使うため、このリリースでは追加のGemや`bundle install`は不要です。

## 5分間で試す

最初に**[日本語版Guided Viewer](https://min0.github.io/min0-core-forth/viewer/value-trace.html)**を開きます。
同じ内容は`viewer/value-trace.html`にあり、単独で動作してトレースや編集ソースを外部へ送りません。

次に、収録した文字出力例を実行します。

```powershell
python workbench/min0_forth.py -z workbench/examples/hello.fth
ruby workbench/min0_forth.rb -z workbench/examples/hello.fth
```

どちらも次の一行だけを表示します。

```text
Hello from MIN0 CORE FORTH
```

`-z FILE`はbanner、prompt、最終stackの表示を抑えます。FORTHプログラム自身の出力はそのまま表示され、
エラーは標準エラーへ出力されて終了状態が0以外になります。

## 対話的に試す

```powershell
python workbench/min0_forth.py
```

または次を実行します。

```powershell
ruby workbench/min0_forth.rb
```

次の順に試せます。

```forth
WORDS
2 3 +
2 3 4 * + .
: SQUARE DUP * ;
WORDS
5 SQUARE .
: GREET ." Hello" ;
GREET CR
BYE
```

最初の`WORDS`は起動時のワードを表示します。`SQUARE`を定義した後の`WORDS`では、利用者が追加した
定義が日本語の区切りの下へ表示されます。同名では最新の検索可能な定義だけを表示し、hidden、失敗、
rollbackされた定義は表示しません。

`BYE`と`EXIT`は、この参照REPLを終了するlauncher commandであり、凍結したCORE wordではありません。

## 通常のファイル実行

`-z`を付けない場合は、版情報と最終DATA stackも表示します。

```powershell
python workbench/min0_forth.py workbench/examples/basic.fth
ruby workbench/min0_forth.rb workbench/examples/basic.fth
```

安全関連demoを試す前に[最初に読む日本語案内](../FIRST_READ_JP.md)を確認してください。収録した鍵は
すべて公開試験用です。Viewerで編集したソースはViewer内では実行されないため、コピーまたは保存して
Python版かRuby版で確認してください。
