# MIN0 CORE FORTH W^X publication R0

## 目的

`W^X`は、一つの物理領域を通常書込み可能（Writable）と実行可能（eXecutable）に同時にしない方針である。
MIN0 CORE FORTHでは、Forthの作成・改造の自由と、正式runtimeで承認済みCODEだけを動かす境界を分ける。

> Forthの自由さを失わせず、危険な力を使うときだけ本人がはっきり自覚できる設計にする。  
> 通常利用者に安全な道と、理解した開発者が明示的に開く道を分ける。

## R0の公開経路

```text
受領したimage component
          |
          v
  envelope・digest・manifest・bytecode検証
          |
          v
 STAGING-CODE rw,nx ── componentを配置 ── 再検証
          |
          | 検証済みsnapshotだけをprivileged program
          v
 runtime CODE rx, programmable=true
          |
          | 固定dispatchをprogramし、boundary policyを導入
          v
 runtime CODE       rx, programmable=false, sealed=true
 runtime DICTIONARY rw, write-protected, structure sealed
```

`programmable=true`はordinary `!`が書けるという意味ではない。loaderだけが使うhost-side program経路であり、
CODE regionの通常permissionは最初から`rx`である。seal後はそのprogram経路も閉じる。

## stagingとruntimeの分離

stagingとruntimeは別々の`RegionMemory` objectとbyte storageを持つ。公開後にstagingの先頭byteを`0xFF`へ変更しても、
runtime CODEは変化せず、既に公開した`READ-ANSWER`は7を返す。stagingには`x`がないため、そのaddressを命令として
fetchすることもできない。

runtimeでは次を拒否する。

- Forthの`!`またはhost通常writeによるCODE変更
- loader program APIによるseal後の再program
- operand途中、DATA、未検証addressからの実行
- digest・manifest・bytecode検証に通らないcomponentの公開
- `standard-build` imageのsafe-runtimeへの公開
- 通常`!`、host write、loader programによるDICTIONARY構造変更

## 固定primitive dispatch

outer interpreterは各operandなしprimitiveに`opcode, HALT`の固定2-byte slotを割り当てる。実行時にはslotを選んで
入るだけで、opcodeを書き換えない。全slotはpublish中に一度だけprogramされ、内容を照合したうえでopcodeとHALTの
両addressをverified extra entryへ登録する。

これによりCODE封印後も数値入力と`+`、stack操作、DATA access等のprimitiveを対話実行できる。

## 実働確認

```powershell
python -m unittest -v test_w_x_publish.py
ruby test_ruby_w_x_publish.rb
python cross_w_x_publish_check.py
```

PythonとRubyで次が一致する。

- staging permissionは`rw`で、命令fetchは拒否
- runtime CODEは`rx`、`programmable=false`、`sealed=true`
- 公開後の`READ-ANSWER 2 3 +`はstack `[7, 5]`
- staging変更後もruntime bytesは不変
- runtime write、runtime reprogram、改変image公開を拒否

## R0の範囲

- 連続したCODE／DICTIONARY／DATAの3-region reference layoutを対象とする。
- host objectを自由に変更できる攻撃者に対するprocess sandboxではない。
- 実Flash／EEPROMのerase単位、A/B slot、instruction cache同期、MPU page permissionはtarget adapterの責務である。
- development compilerがartifactを作る場所の自由は保つ。ここで保証するのは、safe-runtimeへ入る公開境界である。
- DICTIONARYの表示permissionはMonitor DEFER gateのため`rw`だが、通常writeは追加capability層で保護される。
  詳細は`DICTIONARY_CAPABILITY_R0.md`を参照する。
