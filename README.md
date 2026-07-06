# task-manager

芸能事務所向け Gmail × Notion 案件管理システム。Anthropic 公式の Gmail / Notion Connector に 100% 依存し、Markdown Skill だけで動作。自作の Python / Node コードは 0 行。

## 概要

friend（個人事業の芸能事務所オーナー）の案件管理を、Gmail 受信から Notion 反映まで Claude に任せる仕組み。

- **入力**: Gmail に届いたクライアントからのメール
- **処理**: Claude が Skill を起点に Connector を呼び出し、案件のマッチング・新規作成・更新を判断
- **出力**: Notion 案件DBへの反映、要返信案件のリストアップ、週次レポート

## 設計判断

### なぜ Connector 100% にしたか

1. **メンテナンス負荷ゼロ**: Gmail/Notion API の変更対応は Anthropic 側がやる
2. **デプロイ不要**: friend の端末にコピーするだけ。サーバー運用なし
3. **権限管理が公式仕様**: OAuth スコープと監査ログが公式 Connector 経由
4. **AI が文脈解釈する部分**: Skill 本文の Markdown ロジックで完結。Claude 自身が「曖昧な金額」「ステータス遷移可否」を判断するため、ハードコーディングしたルールエンジンより柔軟

### Skill 設計の原則

- 全 Skill のプレフィックスは `tm-`（task-manager）
- 各 Skill は冒頭で「Notion 設定ページからメタ情報を読む」ことで、ID をファイルに埋め込まない
- friend が DB を作り直しても Skill を書き換えずに動く
- description フィールドは Claude の Skill ディスパッチに直結するため、トリガー語を意識した具体的記述

### Notion スキーマの選択

- 案件 DB 単一構成（請求書 DB は将来分離可能だが MVP では同居）
- タレント名・クライアント名は Select プロパティ（軽量、検索が早い）
- マスタとなるタレントDB / クライアントDB は別に持ち、Select オプション追加時に同期更新
- Formula（タレント取り分・会社取り分）は Notion 側で計算（Skill 側で計算しない）
  - 注: Notion Connector の制約上、Formula が別の Formula を参照できないため、`会社取り分 = 受注金額 * (1 - 還元率)` のように NUMBER で完結する式にする
- **ボール所在** プロパティ（🔴自社対応中 / 🟡クライアント待ち / 🟢タレント待ち / ⚪待機・進行中）で「誰が次に動くか」を可視化
- **案件概要** (不変1行サマリ) + **次回アクション** (上書き式の次の一手) + **次回アクションの期日** で日常運用を支援
- ページ本文に「🎯 重要事項」(人)・「📜 タイムライン」(AI が節目だけ追記) の2セクション

### Notion ビュー構成

`/tm-setup` が自動生成する6つのビュー（案件DB に5、ダッシュボードページに埋め込みで2）:

- 案件DB のタブ:
  - 📋 一覧表（11列フル、table）
  - 📊 ステータスボード（board, GROUP BY ステータス）
  - 🎯 ボール別ビュー（board, GROUP BY ボール所在）
  - 📅 納期カレンダー（calendar）
  - 🎬 タレント別ギャラリー（gallery, GROUP BY タレント名）
- ダッシュボードページの埋め込み（横スクロール回避のため type 変更）:
  - 🎯 ボール別リスト（list, GROUP BY ボール所在）← board だと 4 列横並びで収まらない
  - 📋 全案件一覧（table, 4列のみ）

## ファイル構成

```
task manager/
├── README.md               このファイル（開発者向け）
├── スタートガイド.md          friend 向け手順書（md版、配布のメイン）
├── スタートガイド.pdf         上記の PDF 版（印刷用、Release アセット同梱）
├── build_pdf.py            md → PDF 変換スクリプト
├── USAGE.md                日常リファレンス
├── .gitignore
└── skills/
    ├── tm-setup.md         初回セットアップ（DB + 5ビュー + ダッシュボード + 埋め込み2ビュー）
    ├── tm-sync.md          Gmail → Notion 取り込み（中核、ボール所在判定 + マイルストーン追記）
    ├── tm-pending.md       自社対応中 + 期日直近の案件一覧
    ├── tm-report.md        週次レポート（ボール別内訳含む）
    ├── tm-add-talent.md    タレント追加（Select オプション同期）
    ├── tm-add-client.md    クライアント追加（Select オプション同期）
    └── tm-help.md          ヘルプ
```

## Skill 追加のガイド

新しい Skill を追加する場合:

1. `skills/tm-<name>.md` ファイルを作成
2. YAML frontmatter は `name` と `description` を必須
3. 本文構成:
   - `# 目的`
   - `# 前提コンテキストの取得` (メタ情報DB から ID を読む)
   - `# 手順` (番号付き、ツール名明示)
   - `# 出力フォーマット`
   - `# 判断指針 / エッジケース`
   - `# 完了条件`
4. description にはトリガー語を含める（friend がどう呼ぶか想像する）
5. 既存 Skill との重複を避ける（`/tm-help` を更新）

## PDF 版スタートガイドの再生成

`スタートガイド.pdf` は `スタートガイド.md` から `build_pdf.py` で生成（reportlab 利用、日本語フォント HeiseiKakuGo-W5 内蔵 CID）。

```bash
uv run --with reportlab python build_pdf.py
```

スタートガイド.md を編集したら必ず再生成してリポジトリにコミットする。

## 変更履歴

- **v1.0.8** (2026-07-06): ダッシュボード全面改訂（運用先からの「煩雑で見にくい」フィードバック対応）。設計思想を「全部見せる」→「今日やることだけ見せる」に転換。🔥今すぐ対応（🔴自社ボールのみ FILTER）+ ⏳相手待ち・進行中（完了/中断除外、3列テーブル）の2枠構成に。ビューDSL の FILTER（`=`/`!=`、複数行AND）の動作を実機確認。table 列幅は API 制御不可のため、完了報告でページ全幅化（手動1クリック）を案内。toggle 内 `<page>` タグはレンダリング崩れするため使用禁止を明記
- **v1.0.7** (2026-06-14): 友人セットアップ時の混乱対策。(1) スタートガイド ステップ4: 既存DBを流用しない旨を明記、セットアップ後のサイドバー構造を図示、見つからない時の対処を明文化。(2) 全スキルに「セットアップ未完了の検知」を追加（設定ページが見つからない時点で即中断し /tm-setup を促す。推測でデフォルト値を埋めて続行しない）
- **v1.0.6** (2026-06-14): ドキュメント整理。SETUP.md を削除（スタートガイド.md と内容重複していたため）。配布物は スタートガイド.md / .pdf に一本化。README は開発者向けに専念
- **v1.0.5** (2026-06-14): 引き渡し前最終テストで複数の重大バグを発見・修正。(1) `notion-search` のクエリ仕様: 汎用語（"案件" 等）では結果ゼロになり、データソース名（"案件DB" 等）を渡すと全件返ることが判明。tm-sync/pending/report/add-talent/add-client の全件取得を修正。(2) `最終sync日時` を DATE 型保存していたため人間編集保護が常時誤動作する不具合を修正。`is_datetime=1` の datetime 保存に。(3) `notion-fetch` には `last_edited_time` 相当のフィールドが無い旨、`notion-search` の `timestamp` を使うこと、API 編集では timestamp が更新されない可能性があり保護ロジックは best-effort であることを明記。(4) メタDB config レコードの取得手順を明確化
- **v1.0.4** (2026-06-03): 人間編集の保護ロジック追加。`last_edited_time > LAST_SYNC` の案件は動的プロパティ（ボール所在/次回アクション/期日/返信要否）を AI が上書きせず、競合内容を重要メモに記録するだけにする。「朝直したのに翌朝戻ってる」事故を防止
- **v1.0.3** (2026-05-20): C1-C4 修正。SETUP.md/tm-help.md/tm-setup.md/README.md を Phase 4 状態に同期、Run now の重要性を強調、data_source_id 取得方法を明記、ダッシュボード作成手順を正確化
- **v1.0.2** (2026-05-19): スタートガイドから連絡先セクション削除
- **v1.0.1** (2026-05-19): スタートガイド.md 追加（friend 向け1枚もの）
- **v1.0.0** (2026-05-19): MVP リリース。7 Skill + ドキュメント一式（Phase 4.5 = ダッシュボード + ボール所在 + 案件概要 + 次回アクション + タイムライン）

## 依存

- Claude Desktop（Pro/Max 推奨）
- Anthropic 公式 Gmail Connector
- Anthropic 公式 Notion Connector

## ライセンス

private / internal use only
