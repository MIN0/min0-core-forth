# MIN0 CORE FORTH 0.1.4-rc.2 評価版ノート

[英語版はこちらです](RELEASE_NOTES_0.1.4_RC2.md)

候補版：`0.1.4-rc.2`（ローカル、未公開）

本評価更新版は、公開済み`v0.1.4-rc.1`のブラウザ学習・仮想アセンブラ機能を保持し、その後PCとiPhoneで
評価したMobile Learningの観察、実行制御、上限付き入力機能を追加します。

## Mobile実行観察

- 実行前後のDATA stack、top-levelとcolon定義内部、word／呼出し番号、source位置、型付き呼出し履歴、
  検索可能なword辞典を表示します。
- LOOP履歴は通常まとめて表示し、必要な場合だけ全反復を展開できます。
- chunk実行により、長い処理でも定期的にブラウザへ制御を返します。

## Monitor実行制御

- Run、一時停止、1命令、継続、安全停止、実行前への復旧を、明示的な状態機械と確定命令境界snapshotで
  扱います。
- 安全な停止点で、現在word、次の命令、source位置、caller履歴を観察できます。
- 通常はBlob Workerで実行を分離し、Workerを作れないブラウザでは同じengineによる互換モードを使います。

## 上限付き入力

- `KEY? ( -- flag )`は上限付きtransactional入力queueを消費せず確認します。
- `KEY ( -- byte )`はUTF-8 byteを1個消費し、空ならbusy loopを行わず`waiting-input`へ入ります。
- queueと1回の入力は最大256 UTF-8 byteです。不正入力は実行sessionを変更せず拒否します。
- Pause中に入力しても勝手に再開しません。安全停止は現在snapshotを保持し、実行前復旧は開始前のstack、
  dictionary、queueへ戻します。

## 評価済み環境

- 開発workspaceのPython／JavaScript集中回帰試験に合格しています。
- PC画面で実行観察、入力、拒否、安全停止、復旧、画面初期化を確認しました。
- GitHub PagesをiPhone Safariで開き、1 byte入力、Pause中2 byte入力、容量超過拒否、安全停止、復旧、
  画面初期化を確認しました。

## 明確に含めない範囲

- 安全な`VARIABLE`、`@`、`!`、停止中の変数変更、`BREAK`は今後のPhase Cです。
- 生成したRP2350機械語をPico 2 Wでは実行しません。実MPU設定とlive patchも将来作業です。
- Viewer CODE定義は通常のFORTH dictionaryへ登録しません。
- 本版は評価候補であり、正式`0.1.4`ではありません。

公開前にPython／Ruby全体Gate A、release allowlist監査、再現可能package、公開物の再取得、Gate C確認を
完了させます。公開済みtagとassetは変更しません。
