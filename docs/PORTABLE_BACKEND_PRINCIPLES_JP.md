# MIN0 CORE FORTH 移植可能backend開発原則

## 目的

この文書は、MIN0 CORE FORTHの仮想assemblerを現在のRP2350だけでなく、将来のCPU、未知のCPU、
FPGA実装へ移植するときにも維持する基本原則を定める。個々の命令形式やregister名よりも上位にある
開発判断の基準であり、設計案が競合した場合は、まずこの原則へ立ち返る。

中心となる考え方は、利用者が記述する仮想命令の意味と安全性を共通に保ち、CPUやFPGAに固有の
実現方法をbackend内部へ閉じ込めることである。

## 迷ったときに優先する順序

1. FORTHから見える意味とstack contractを壊さない。
2. 失敗時に呼出し前の状態を回復できるようにする。
3. memory capabilityと検査を迂回する直接アクセスを許さない。
4. backend固有の高速化より、共通仕様との一致と検証可能性を優先する。
5. 実装詳細を共通仕様に取り込まず、対象ごとのbackend profileへ分離する。
6. 最適化は基準実装との一致を試験できる場合にだけ採用する。

## すべてのbackendが守る共通契約

次の性質はCPU、命令セット、OS、FPGA構成が変わっても維持する。

- `V0`から`V3`は物理register名ではなく、仮想assemblerの32-bit作業registerである。
- `IN`は固定されたentry frameから値を読み、CODE本体の実行中にFORTH DATA stackを移動しない。
- `OUT`は結果を一時領域へ置き、正常終了時だけstack contractを一度に確定する。
- CODE本体で使用する入力数と、正常終了後に残す出力数はstack contractで明示する。
- 検査、命令実行、memory access、結果確定のいずれかが失敗した場合、FORTH DATA stackを
  呼出し前の状態に保つ。
- `LD32`と`ST32`はcapability、範囲、alignment、権限を検査し、生の任意memory accessを許さない。
- `ST32`は正常終了まで未確定とし、失敗時にはstackとmemoryの両方を開始前の状態に保つ。
- execution contextは、入力、出力、capability、未確定write、statusを結び付ける基準点として扱う。
- 呼出し元が保存を期待する状態はbackendが保存・復元する。
- 未解決relocation、未検証helper、検査不能な命令を含む生成物は実行可能として公開しない。

共通契約は「どのように実現するか」ではなく「外部から何が保証されるか」を規定する。

## backendごとに定める実装profile

次の項目は対象ごとに異なってよい。ただし、選択理由、保存範囲、失敗経路、検証方法をbackend文書へ
記録する。

- 仮想registerを割り当てる物理registerまたはFPGA内の保持領域
- execution contextの保持場所とhelperへの受渡し方法
- 呼出し規約、戻り先の保持、関数入口と復帰方法
- 保存・復元するregister、frameの大きさ、stack alignment
- 分岐、比較、定数load、rotateなどを実現する命令列
- helper call、trap、異常終了、transaction破棄の実現方法
- machine code、microcode、hardware state machineの配置と公開方法
- instruction cache、data cache、W^Xなど対象固有の実行準備

RP2350 backend R0の`V0-V3 = r4-r7`、contextを保持する`r8`、比較値を保持する`r9/r10`、`lr`、
`BL`、`BX lr`、32-byte
function frameは、この実装profileに属する。これらはARMを理解する重要な具体例だが、MIN0全体の
固定仕様ではない。

## FPGAと未知のCPUへの適用

未知のCPUでは、まずそのCPUのABI、register構成、alignment、call／return、memory保護機能を調べ、
共通契約を満たすbackend profileへ翻訳する。既存CPUのregister名やframeをそのまま模倣する必要はない。

FPGAでは`lr`や`BX lr`に相当する命令が存在しないことがある。その場合も、次の問いに答えられれば
同じ原則を適用できる。

- 開始時の入力と終了時の出力をどこに保持するか。
- execution contextをどのhardware blockが保持し、どの経路で参照するか。
- 呼出し元へ戻る状態または完了通知をどこに保持するか。
- memory accessを実行する前にcapability、範囲、alignment、権限をどこで検査するか。
- 途中失敗時に未確定writeを破棄し、開始前の状態をどう保証するか。

CPU命令列ではなくhardware state machineで実現しても、外部から観察されるstack contractと安全性が
一致すればMIN0 backendとして扱える。

## 読者に応じた情報の三層

### 利用者と学習者

仮想assemblerの書き方、stack contract、実行結果、安全なmemory accessを具体例で説明する。
物理registerやmachine encodingを知らなくても利用できる入口を維持する。

### 移植担当者

共通契約、backend profileの作成項目、基準実装との適合試験、異常終了時の保証を説明する。
新しいCPUやFPGAへの移植はこの層から開始する。

### backend開発者と監査者

ABI、register割当、frame、machine encoding、relocation、helper、W^X、逆解析、実機試験など、対象固有の
詳細を記録する。RP2350の`r4-r10`、`lr`、32-byte frame、`BL`、`BX lr`の説明はこの層の具体例である。

初学者向け説明と専門的な詳細は分離するが、相互に参照できるようにする。簡単な説明のために保証を
曖昧にせず、専門資料だけに重要な安全条件を隠さない。

## 新規backendの適合条件

新しいbackendは、機械語やhardwareが動作しただけでは完成としない。少なくとも次を確認する。

1. 仮想命令の正常結果が基準実装と一致する。
2. 入力数と出力数が異なる場合も、CODE本体実行中のDATA stack位置が変化しない。
3. 未初期化register、未定義label、未設定outputなどの不正sourceを実行前に拒否する。
4. memoryの範囲外、未整列、権限違反、整数桁あふれを物理access前に拒否する。
5. 各失敗点でstackと未確定memory writeが開始前の状態に戻る。
6. 呼出し元が保存を期待するregister、stack、戻り先を破壊しない。
7. relocationと生成物を独立した手段で検査し、未解決部分を実行不可に保つ。
8. simulatorまたはreference model、独立逆解析、対象実機の順に検証する。
9. 共通適合試験に加え、対象固有のABI、alignment、cache、実行保護を試験する。
10. 実装profile、既知の制限、実行許可条件を文書化する。

将来はこの一覧を共通conformance test suiteとして自動化し、CPU backendとFPGA backendの双方へ
同じ合否基準を適用する。

## 変更してよい範囲と変更手順

backend profileは、実装、逆解析、runtime helper、実機試験から得た知見によって変更できる。
例えばregister割当、helper方式、frameサイズ、命令選択、最適化方法は今後変わり得る。

一方、共通契約を変更する場合は単なるbackend改良として扱わない。理由、互換性、安全性、基準実装、
適合試験、既存backendへの影響を確認し、仕様revisionとして明示する。安全性を弱める変更や、特定CPUの
都合を共通仕様へ持ち込む変更は原則として採用しない。

この区別により、実装を改善する自由と、MIN0として守るべき核の安定性を両立する。
