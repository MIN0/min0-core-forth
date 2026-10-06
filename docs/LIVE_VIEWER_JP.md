# MIN0 CORE FORTH localhost Live Viewer

## 目的

Live Viewerは、入力したFORTH sourceをPython参照実装の新しいVMで実行し、端末出力と
ワード単位のstack遷移をブラウザーで確認するローカル教材である。既存の
`viewer/value-trace.html`は測定済みtraceを読む静的教材として残し、この画面とは分離する。

## 起動

プロジェクト直下で次を実行する。

```powershell
python tools/run_live_viewer.py
```

既定ブラウザーで次のURLが自動的に開く。

```text
http://127.0.0.1:8765/
```

`viewer/live-viewer.html`をfileとして直接開いてもFORTHは実行できない。実行APIは
上記localhost serverが提供するため、address欄が`file:///...`ではなく
`http://127.0.0.1:8765/`であることを確認する。ブラウザーを自動で開きたくない場合は
`python tools/run_live_viewer.py --no-open`とする。

終了は起動したterminalで`Ctrl+C`を押す。portを変える場合は、例えば
`python tools/run_live_viewer.py --port 9000`とする。

## 表示内容

- FORTH source入力欄
- 端末出力
- 最終DATA／RETURN／LOOP stack
- 各source wordのDATA stack実行前／実行後
- 各source word完了時のRETURN／LOOP stack
- VM step数
- エラー名と内容

実行ごとに辞書、memory、stackを含む新しいVMを作る。前回のユーザー定義は次の実行へ
持ち越さない。

## 安全境界

- serverは`127.0.0.1`だけへbindし、LANやInternetへ公開しない。
- POSTは同一originのJSONだけを受理する。
- source上限は4096 UTF-8 byte、HTTP request上限は8192 byteである。
- VMの既存step limitにより、終了しないFORTH codeも決定的に停止する。
- FORTHからOS command、任意file、networkを操作するwordは提供しない。
- source、出力、エラーはDOMの`textContent`として表示し、HTMLとして実行しない。
- requestごとに順番に処理し、無制限なworker threadを作らない。

この版はWindows PC上で実行するlocalhost版であり、iPhone単体実行やLAN接続は対象外とする。
