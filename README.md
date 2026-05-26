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

## ファイル構成

```
task manager/
├── README.md               このファイル（開発者向け）
├── SETUP.md                friend 向けセットアップ手順
├── USAGE.md                日常リファレンス
├── .gitignore
└── skills/
    ├── tm-setup.md         初回セットアップ
    ├── tm-sync.md          Gmail → Notion 取り込み（中核）
    ├── tm-pending.md       要返信案件一覧
    ├── tm-report.md        週次レポート
    ├── tm-add-talent.md    タレント追加
    ├── tm-add-client.md    クライアント追加
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

## 変更履歴

- **v1.0** (2026-05-19): MVP リリース。7 Skill + ドキュメント一式

## 依存

- Claude Desktop（Pro/Max 推奨）
- Anthropic 公式 Gmail Connector
- Anthropic 公式 Notion Connector

## ライセンス

private / internal use only
