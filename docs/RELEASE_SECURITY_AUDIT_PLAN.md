# MIN0 CORE FORTH release security audit plan

Status: 1st releaseの必須gate。GitHub公開作業と同じ一連の作業として実施する。

## 原則

公開後の確認だけでは、秘密鍵や個人情報がGit履歴へ入った事故を取り消せない。
そのため、次の三段階をすべて完了して初めてrelease完了とする。

1. 公開直前監査（公開を止められるgate）
2. GitHubへ公開・release作成
3. 公開後監査（GitHub上の実物と配布物の再確認）

## Gate A: 公開直前監査

- 作業directory全体をコピーせず、公開許可listからclean staging directoryを作る。
- `document_work/`、会話記録`.docx`、`__pycache__/`、Codex session参照、個人PCの絶対pathを除外する。
- source、設定、test vector、生成物、Git履歴をsecret scanする。
- Ed25519 seed、root／recovery key、HMAC keyが公開fixtureだけであることを確認する。
- fixtureは再現可能な固定値、`TEST`／`fixture`名、実運用禁止の説明を三点とも満たす。
- API key、password、access token、実運用証明書、署名host情報がないことを確認する。
- 未修正で実際の利用者へ影響する脆弱性が見つかった場合は公開せず、修正と再試験を先に行う。
- Python全試験、Ruby全試験、cross-language試験、Viewer試験をclean stagingから実行する。
- release artifactをstagingから再生成し、SHA-256一覧を作る。
- `FIRST_READ.md`、既知の制限、fixture鍵の警告、製品securityを保証しない位置付けを確認する。
- `SECURITY.md`に、対象versionと非公開の脆弱性報告方法を記載する。

Gate Aに一件でも未解決の重大項目があれば、GitHub公開を行わない。

## Gate B: GitHub公開

- clean stagingだけを新しいrepository／releaseへ反映する。
- source license、version tag、release notes、artifact、SHA-256一覧を揃える。
- secret scanning／push protectionを可能な範囲で有効にする。
- private vulnerability reportingまたは同等の非公開連絡経路を用意する。
- 実運用の署名鍵を使う場合、そのprivate keyはrepository、release asset、CI logへ渡さない。

## Gate C: 公開後監査

- 公開repositoryを別のclean directoryへcloneし、公開者の作業directoryを参照せずbuild／testする。
- GitHub上の全tracked file、tag、release assets、release notesを再確認する。
- 公開archiveを展開し、除外対象、秘密情報、個人情報、絶対pathがないことを再scanする。
- 公開artifactのSHA-256がrelease一覧と一致することを確認する。
- Viewerがofflineで、外部networkやAIへtraceを送らないことを再確認する。
- fixture鍵で署名したものを実運用署名済みartifactと誤認させる表示がないことを確認する。
- GitHubのsecurity alert、secret scanning alert、依存関係alertを確認する。
- 問題を見つけた場合はreleaseを安全版へ差し替えるだけで済ませず、影響範囲、Git履歴、鍵失効の要否を判定する。

## 完了報告

release完了時には、少なくとも次を利用者へ報告する。

- 公開repository URL、release tag、artifact名
- Gate A／B／Cの結果
- 実行したPython／Ruby／cross-language試験数
- secret／privacy scanの結果と除外したfile
- fixture鍵だけが含まれ、実運用秘密鍵を含まないこと
- 残る既知の制限と、製品運用向けsecurityを保証しない範囲
- release artifactのSHA-256

この監査はMIN0 CORE FORTHを対象とし、独立して発展するMSX0-FORTHのrepositoryやreleaseを変更しない。
