# Windows開発環境での全体試験手順

この手順は、MIN0 CORE FORTHのPython版、Ruby版、両実装の相互一致をWindows 11の通常PowerShellで
まとめて確認するための開発記録である。Codexの制限付きWindows sandboxではRubyを起動できない場合が
あるため、Rubyを含む最終判定には利用者が開いた通常PowerShellを使用する。

## 現在確認している環境

- Windows 11
- Python 3.14系
- Ruby 3.4.11 x64-mingw-ucrt
- Ruby同梱JSON 2.9.1
- OpenSSL 3.6.4

Ruby 4.0とJSON 3.0の組合せでは、現在の`JSON.parse`呼出しにある`create_additions:`が受理されない。
将来はMIN0側をJSON 2.x／3.xの両方へ対応させる。それまではRuby 3.4系を開発試験の基準とし、
`0.1.4-rc.4`のWindows release gateではRuby 3.4.11、JSON 2.9.1、OpenSSL 3.6.4を使用する。

## 1. 通常PowerShellを開く

Codex内のterminalではなく、Windowsから通常のPowerShellを開く。MIN0 CORE FORTHのrepository最上位、
つまり`docs`、`tools`、`workbench`が見えるdirectoryへ移動する。

```powershell
Get-Location
Test-Path .\tools\run_all_checks.py
Test-Path .\workbench\min0_forth.py
Test-Path .\workbench\min0_forth.rb
```

三つの`Test-Path`がすべて`True`でなければ、まだ試験を開始しない。

## 2. PythonとRubyを単独確認する

```powershell
python --version
ruby --version
ruby -rjson -e "puts JSON::VERSION"
```

次に、PythonがRubyを子processとして起動できることを確認する。

```powershell
python -c "import subprocess; r=subprocess.run(['ruby','--version'],capture_output=True,text=True); print(r.returncode); print(r.stdout); print(r.stderr)"
```

正常時は戻り値`0`とRubyのversionが表示される。`3221225506`または`0xC0000022`はWindowsの
access deniedであり、FORTHの試験失敗ではなく実行環境の制限として扱う。

## 3. 全体試験を一度だけ実行する

repository最上位から次を実行する。

```powershell
python tools\run_all_checks.py
```

この一つのcommandが次を順番に実行する。

1. Pythonの`unittest`一式
2. `ruby test_ruby_*.rb`によるRuby単体試験
3. Python版とRuby版を別processで実行して結果を比較する相互試験

Pythonは全体の進行と結果集計にも使われるが、Ruby sourceをPythonで解釈するわけではない。Ruby単体試験と
相互試験のRuby側は、どちらも`ruby.exe`が実行する。

## 4. 最後のSUMMARYを判定する

成功時は末尾に次が表示される。

```text
ALL CHECKS PASSED
```

失敗時は途中の長い出力だけで判断せず、末尾の`FAILED (...)`に並ぶ名前を最初に確認する。同じ根本原因が
Ruby単体試験と相互試験へ波及し、複数件に見える場合があるためである。

2026年10月10日のRuby 3.4再試験では、Python 357件とRuby 48 test fileがすべて成功し、相互試験は
50件中48件が成功した。残った次の2件は言語仕様やRuby環境の失敗ではなく、demoを相対pathで探す際の
working directory不一致である。

```text
cross_region_memory_check.py
cross_split_dictionary_check.py
```

0.1.3-rc.1では、一括試験工具が相互試験を`workbench`から起動するよう修正した。通常PowerShellで
同じ全体試験を再実行し、この2件を含む`ALL CHECKS PASSED`を確認する。

## 5. 結果を保存する

PowerShellの先頭command、各試験の出力、最後の`SUMMARY`を一つのUTF-8 text fileへ保存する。最低限、
実行日、Python version、Ruby version、JSON version、実行したcommit、末尾の成功／失敗一覧が追跡できる
状態にする。長い出力を確認するときも、最終判定は必ず`SUMMARY`と最初の原因errorを組み合わせて行う。

