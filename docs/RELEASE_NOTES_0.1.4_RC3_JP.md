# MIN0 CORE FORTH 0.1.4-rc.3 評価版ノート

[English version](RELEASE_NOTES_0.1.4_RC3.md)

候補版：`0.1.4-rc.3`（ローカル、未公開）

本評価更新版は、公開済み`v0.1.4-rc.2`のMobile実行観察、停止・再開、上限付き入力を保持し、
安全な1 cell変数と明示的なMonitor停止点を追加します。

## Safe VARIABLE

- `VARIABLE`は専用領域へ0で初期化した1 cellを登録します。
- `@`と`!`は登録済み論理addressだけを受け付けます。任意の数値や失効したaddressは
  `InvalidAddress`で停止し、検査前のstackを保持します。
- Pause確定中は登録済み変数の名前、論理address、現在値を画面で確認できます。
- 停止中の値変更は32ビットcell範囲、session状態、登録名を検査し、変更履歴を残します。
- 「実行前へ復旧」は値だけでなく変数定義と割当位置も開始前へ戻します。

## BREAK

- `BREAK ( -- )`はcolon wordまたはmainの確定命令境界でMonitorへ一時停止します。
- 停止画面では現在word、命令番号、source位置、caller履歴、次token `BREAK`を確認できます。
- 継続は`BREAK`直後から再開します。1命令、安全停止、実行前復旧も通常のPauseと同じ規則です。
- Monitorのない同期reference実行では、停止要求を黙って無視せず`BreakUnavailable`を返します。

## 診断表示

- 実行前復旧後に残る命令履歴とword辞典は、復旧前に何が起きたかを調べる観察記録であると明示します。
- VM状態の復旧と診断記録の保持を分離し、記録まで消す操作は「画面を初期化」とします。

## 評価範囲

- Safe VARIABLE、Pause中編集、`BREAK`はPC Viewerで自動試験と実画面確認に合格しています。
- iPhone SafariでSafe VARIABLE、Pause中編集、`BREAK`の実画面確認に合格しました。
- 利用者の通常Windows PowerShellでPython、Ruby、言語間の全体試験に合格しました。
- 再現可能packageと公開後Gate Cはrelease工程で確認します。

## 明確に含めない範囲

- 任意memory address、配列・構造体、永続変数、一般IO accessはまだ提供しません。
- 生成したRP2350機械語をPico 2 Wでは実行しません。実MPU設定とlive patchも将来作業です。
- 本版は評価候補であり、正式`0.1.4`ではありません。

公開済みtagとassetは変更しません。
