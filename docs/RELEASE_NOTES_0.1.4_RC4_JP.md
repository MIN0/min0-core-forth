# MIN0 CORE FORTH 0.1.4-rc.4 評価版ノート

[English version](RELEASE_NOTES_0.1.4_RC4.md)

候補版：`0.1.4-rc.4`（ローカル、未公開）

本候補は`0.1.4-rc.3`向けに準備したSafe VARIABLEと明示的Monitor停止点を保持し、公開前にWindowsの
Ruby基準を訂正します。さらに、機器別利用案内と次のCapability Tour方針を加えます。

## Safe VARIABLEとBREAK

- `VARIABLE`は専用領域へ0で初期化した1 cellを登録します。
- 検査付き`@`と`!`は登録済み論理addressだけを受け付けます。
- Pause確定中は変数を観察し、検査付き32ビット編集を行い、Abortで開始前へ戻せます。
- `BREAK ( -- )`は確定命令境界で停止し、継続、1命令、安全停止、実行前復旧を利用できます。

## Windows Ruby基準

- release基準はRuby 3.4系とOpenSSL 3.xです。
- Windows Gate AではRuby 3.4.11 x64-mingw-ucrtを使用します。
- Ruby 4.0とJSON 3.0の組合せにはpersistent metadata parserの`JSON.parse` option互換対応が残るため、
  今回のrelease基準とは主張しません。
- 本候補のRuby launcherに`bundle install`や追加Gemは不要です。

## 最初の利用案内

- 日本語の最初の案内で、公開上の利用可否と実機確認済みかどうかを区別しました。
- Windows PCとiPhone Safariは確認済みです。Mac、Linux、RasPi 5 browser、Android、tabletは
  browser互換と考えられますが未評価です。
- Pico 2 Wはbrowser環境を持たないため、Mobile Learningを直接実行できません。
- 次の最優先作業は、Safe VARIABLE、`CREATE DOES>`、仮想assemblerを一か所で体験するCapability Tourです。

## 明確に含めない範囲

- 任意memory address、配列・構造体、永続変数、一般IOはまだ提供しません。
- 生成したRP2350機械語をPico 2 Wでは実行しません。
- 本版は評価候補であり、正式`0.1.4`ではありません。

公開済みtagとassetは変更しません。未公開の`v0.1.4-rc.3` tagも移動しません。
