---
name: tm-setup
description: task-manager の初回セットアップ。Notion 親ページ配下に「task-manager 設定」ページと案件DB/タレントDB/クライアントDB/メタ情報DBを自動生成する。「セットアップ」「初期化」「task-manager を始める」等のトリガーで起動。通常1回のみ実行。
---

# 目的

friend の芸能事務所向け案件管理システムを Notion 上に構築する。指定された親ページ配下に、運用に必要な 4 つのデータベース（案件DB、タレントDB、クライアントDB、メタ情報DB）と設定ページを一括で生成し、以降の Skill 群が参照する基盤を整える。

このSkillは原則 1 回だけ実行する。再実行する場合は既存「task-manager 設定」ページの存在をユーザーに確認すること。

# 前提コンテキストの取得

このSkillは初回実行のため、メタ情報DBはまだ存在しない。ユーザーから親ページを直接受け取る。

# 手順

## 1. 親ページの確認

ユーザーに以下を尋ねる:

> task-manager のホームになる Notion ページの URL を教えてください。このページ配下に設定ページとデータベースを作成します。

受け取った URL から page_id を抽出（URL末尾の32文字英数字、ハイフンを除いたもの）。

念のため `notion-fetch` で対象ページが取得できることを確認する。失敗したらユーザーに権限・URLを再確認してもらう。

## 2. 「task-manager 設定」ページを作成

`notion-create-pages` で親ページ配下にページを作成:

- title: `task-manager 設定`
- content: 以下の Markdown を埋め込む

```markdown
# task-manager 設定

このページは task-manager Skill 群が参照する設定ハブです。配下のデータベースを直接編集しないでください（必要な編集は Skill 経由で行います）。

## バージョン
v1.0

## 案件ステータス遷移ルール（toggle）
- 引合 → 見積中 / 中断
- 見積中 → 契約締結 / 中断
- 契約締結 → 進行中 / 中断
- 進行中 → 納品済 / 中断
- 納品済 → 入金待ち / 完了
- 入金待ち → 完了
- 完了 → (終端)
- 中断 → 引合 / 見積中 / 契約締結 / 進行中（再開時のみ）

逆行は中断経由でのみ許可。例: 進行中 → 引合 は NG、進行中 → 中断 → 引合 は OK。

## AI 判断ルール（toggle）
- confidence 高: Notion に直接反映
- confidence 中: 反映するが「[AI要確認 YYYY-MM-DD]」を重要メモに追記、こちらの返信要否=true
- confidence 低: Notion に書き込まず、要確認リストに退避してユーザーに提示
- AIメモは追記式（既存内容を保持し「YYYY-MM-DD: ...」形式で追加）
- 重要メモは人手による運用情報。AI は追記のみ、上書き禁止
- Gmail Message ID 履歴は最新 20 件のみ保持。超過時は古い順から切り捨て

## sync 対象ラベル
（メタ情報DBで管理。空文字なら全 INBOX を対象）
```

このページの page_id を `SETTINGS_PAGE_ID` として保持。

## 3. 案件DB を作成（自己参照Relation は二段階）

`notion-create-database`（タイトル `案件DB`、parent: `SETTINGS_PAGE_ID`）を呼ぶ。Connector の DDL は `CREATE TABLE` 構文。日本語プロパティ名を使用。

> **重要な制約**:
> - DDL では Formula が **別の Formula を参照できない**（型エラーになる）。`会社取り分 = 受注金額 - タレント取り分` のような相互参照は不可。代わりに `会社取り分 = 受注金額 * (1 - 還元率)` のように **NUMBER だけで完結する式** で書く。
> - 文字列型は `TEXT` ではなく `RICH_TEXT` を使う。
> - SELECT は `('値':color, '値2':color2, ...)` 形式で初期オプションを指定する（少なくとも 1 オプションは必須）。
> - 自己参照 Relation は CREATE 時には指定できず、必ず CREATE 後に `ALTER` で追加する。

DDL（一段階目: 自己参照以外）:

```sql
CREATE TABLE (
  "案件名" TITLE,
  "案件概要" RICH_TEXT,
  "タレント名" SELECT('未設定':gray),
  "クライアント名" SELECT('未設定':gray),
  "ステータス" SELECT('引合':gray, '見積中':blue, '契約締結':purple, '進行中':orange, '納品済':yellow, '入金待ち':pink, '完了':green, '中断':red),
  "ボール所在" SELECT('🔴 自社対応中':red, '🟡 クライアント待ち':yellow, '🟢 タレント待ち':green, '⚪ 待機・進行中':gray),
  "受注金額" NUMBER FORMAT 'yen',
  "還元率" NUMBER,
  "タレント取り分" FORMULA('prop("受注金額") * prop("還元率")'),
  "会社取り分" FORMULA('prop("受注金額") * (1 - prop("還元率"))'),
  "開始日" DATE,
  "納期" DATE,
  "最終やり取り日" DATE,
  "次回アクション" RICH_TEXT,
  "次回アクションの期日" DATE,
  "こちらの返信要否" CHECKBOX,
  "AIメモ" RICH_TEXT,
  "重要メモ" RICH_TEXT,
  "最新メールへのリンク" URL,
  "Gmail Message ID履歴" RICH_TEXT,
  "請求書発行日" DATE,
  "請求書番号" RICH_TEXT
)
```

作成成功したら data_source_id を `DEALS_DSID` として保持。

二段階目: `notion-update-data-source(data_source_id=DEALS_DSID, statements=...)` で自己参照 DUAL Relation を追加:

```sql
ADD COLUMN "親案件" RELATION('<DEALS_DSID>', DUAL '子案件' '子案件')
```

`<DEALS_DSID>` は実 ID に置換する。DUAL 引数のうち 1 つ目は逆方向プロパティの表示名、2 つ目は内部キー名（自己参照ではどちらも同じで OK）。失敗時は DUAL 部分を削って単方向にフォールバックし、メタ情報DBの `バージョン` を `v1.0-singlerel` にする。

## 3.5. 案件DB のビュー5種を作成

ステータス管理を視覚化するため、案件DBに 5 種類のビューを `notion-create-view` で作成。`database_id` は 案件DB の DB UUID（`notion-create-database` レスポンスの `<database url="https://www.notion.so/<uuid>">` から抽出）、`data_source_id` は `DEALS_DSID`。

### ビュー0: 📋 一覧表（デフォルト・全件閲覧用）

```
name: 📋 一覧表
type: table
configure:
  SHOW "案件名", "案件概要", "ステータス", "ボール所在", "タレント名", "クライアント名", "納期", "次回アクション", "次回アクションの期日", "最終やり取り日", "受注金額"
  SORT BY "最終やり取り日" DESC
```

行ベースで全プロパティを横並び閲覧できる素直なテーブル。Excel感覚で見たい時、検索したい時、CSV エクスポートしたい時に使う。

### ビュー1: 📊 ステータスボード（トレロ風）

```
name: 📊 ステータスボード
type: board
configure:
  GROUP BY "ステータス"
  SHOW "案件名", "ボール所在", "次回アクション", "次回アクションの期日", "タレント名", "クライアント名"
```

ステータス（引合〜完了）でカラム分け。デフォルトの作業画面に最適。

### ビュー2: 🎯 ボール別ビュー

```
name: 🎯 ボール別ビュー
type: board
configure:
  GROUP BY "ボール所在"
  SHOW "案件名", "案件概要", "ステータス", "次回アクション", "次回アクションの期日"
  SORT BY "次回アクションの期日" ASC
```

「誰の対応待ちか」でカラム分け。🔴 自社対応中 のカラムが要対応リストになる。

### ビュー3: 📅 納期カレンダー

```
name: 📅 納期カレンダー
type: calendar
configure:
  CALENDAR BY "納期"
  SHOW "案件名", "ステータス", "ボール所在"
```

納期軸で月表示。先まで見渡せる。

### ビュー4: 🎬 タレント別ギャラリー

```
name: 🎬 タレント別ギャラリー
type: gallery
configure:
  GROUP BY "タレント名"
  SHOW "案件名", "案件概要", "ステータス", "ボール所在", "クライアント名", "納期"
```

タレントごとに案件カードが並ぶ。マネージャー視点で誰が今何をやっているか俯瞰できる。

### 失敗時のフォールバック
ビュー作成APIが失敗した場合（DSLパースエラー等）、ユーザーに「Notion上で『+ View』ボタンから手動で4ビューを作成してください」と案内し、設定ページに作るべきビューのリストを残す。Skill本体は続行（ビューは見せ方なので無くてもデータ操作は可能）。

## 4. タレントDB を作成

`notion-create-database`（タイトル `タレントDB`、parent: `SETTINGS_PAGE_ID`）:

```sql
CREATE TABLE (
  "名前" TITLE,
  "エイリアス" RICH_TEXT,
  "関連メアド" RICH_TEXT
)
```

data_source_id を `TALENTS_DSID` として保持。

## 5. クライアントDB を作成

`notion-create-database`（タイトル `クライアントDB`、parent: `SETTINGS_PAGE_ID`）:

```sql
CREATE TABLE (
  "会社名" TITLE,
  "ドメイン" RICH_TEXT,
  "エイリアス" RICH_TEXT
)
```

data_source_id を `CLIENTS_DSID` として保持。

## 6. メタ情報DB を作成

`notion-create-database`（タイトル `メタ情報DB`、parent: `SETTINGS_PAGE_ID`）:

```sql
CREATE TABLE (
  "キー" TITLE,
  "案件DB_id" RICH_TEXT,
  "タレントDB_id" RICH_TEXT,
  "クライアントDB_id" RICH_TEXT,
  "最終sync日時" DATE,
  "sync対象ラベル" RICH_TEXT,
  "バージョン" RICH_TEXT
)
```

data_source_id を `META_DSID` として保持。

## 6.5. 📋 案件管理ダッシュボードページの作成

ユーザーが日常的に開く「案件管理のホーム」となるダッシュボードページを、親ページ配下に作る。「task-manager 設定」と兄弟関係になる位置。

**親ページの上書きはしない**（ユーザーの既存コンテンツを破壊しないため、必ず新規サブページとして作成）。

### 手順の全体像（重要）

`notion-create-view` で `parent_page_id` を指定すると、**埋め込みビューはページ末尾に追加される**仕様。ヘッダー直下にビューを置きたい場合は以下の4段階で作る:

1. ダッシュボードページを最小内容で作成（タイトルのみ）
2. 埋め込みビュー2つを作成（ページ末尾に追加される）
3. ページを `notion-fetch` して、各埋め込みビューの `<database url="...">` 値を取得
4. `notion-update-page(command="replace_content")` で、取得したURLを含めた最終構造に書き換え

これをやらないと「プレースホルダーテキストの下にビューが無く、ページ末尾にビューが並ぶ」見た目になる。

### 6.5.1. ダッシュボードページの最小作成

`notion-create-pages`（parent: `page_id=<親ページID>`、つまり手順1で受け取ったページ）で以下を作成:

- properties: `title: "📋 案件管理"`
- icon: `📋`
- content: 任意（次の手順で全置換するので何でも良い、空文字列でも可）

このページの page_id を `DASHBOARD_PAGE_ID` として保持。

### 6.5.2. 埋め込みリンクビューを2つ追加

`notion-create-view` を `parent_page_id=DASHBOARD_PAGE_ID` 指定で 2 回呼ぶ。`data_source_id` は `DEALS_DSID`。

> **設計原則（v1.0.7 で全面改訂）**: ダッシュボードは「全部見せる」ではなく **「今日やることだけ見せる、残りは1クリック先」**。
> - **FILTER を必ず使う**（`=` / `!=`、複数 FILTER 行の AND 結合が動作確認済み）。完了・中断案件をダッシュボードに出さない
> - GROUP BY による全グループ縦積みは案件数増で巨大な壁になる → 使わない。🔴 だけ FILTER で切り出す
> - board 型は 4 列横並びで収まらない → 使わない
> - list 型は本文幅に必ず収まる。table 型は列幅合計が本文幅を超えると横スクロールが出る（列幅は API 制御不可）→ table を使う場合は 3 列以下 + 完了報告でページ全幅化を案内

**埋め込みビュー1: 🔥 今すぐ対応**
```
name: 🔥 今すぐ対応
type: list
configure:
  FILTER "ボール所在" = "🔴 自社対応中"
  SORT BY "次回アクションの期日" ASC
  SHOW "次回アクション", "次回アクションの期日"
```

自社が動くべき案件だけの短いリスト。朝ここだけ見れば良い。

**埋め込みビュー2: ⏳ 相手待ち・進行中**
```
name: ⏳ 相手待ち・進行中
type: table
configure:
  FILTER "ボール所在" != "🔴 自社対応中"
  FILTER "ステータス" != "完了"
  FILTER "ステータス" != "中断"
  SORT BY "次回アクションの期日" ASC
  SHOW "案件名", "ボール所在", "次回アクションの期日"
```

アクティブだが自社ボールでない案件。3 列に絞って横スクロールを抑制。

### 6.5.3. ダッシュボードページを fetch してビューURLを取得

`notion-fetch(id=DASHBOARD_PAGE_ID)` を実行。レスポンスのページ本文に以下のような行が2つ含まれる:

```
<database url="https://www.notion.so/<HEX1>" inline="true" data-source-url="collection://<DEALS_DSID>"></database>
<database url="https://www.notion.so/<HEX2>" inline="true" data-source-url="collection://<DEALS_DSID>"></database>
```

順序は作成順 = `<HEX1>` が 🔥 今すぐ対応、`<HEX2>` が ⏳ 相手待ち・進行中。これを `DASHBOARD_VIEW1_URL` / `DASHBOARD_VIEW2_URL` として保持。

### 6.5.4. ページ本文を最終構造に書き換え

`notion-update-page(page_id=DASHBOARD_PAGE_ID, command="replace_content", allow_deleting_content=true, new_str=...)` を以下の内容で実行:

```markdown
# 📋 案件管理

## 🔥 今すぐ対応（こちらのボール）

<database url="<DASHBOARD_VIEW1_URL>" inline="true" data-source-url="collection://<DEALS_DSID>"></database>

## ⏳ 相手待ち・進行中

<database url="<DASHBOARD_VIEW2_URL>" inline="true" data-source-url="collection://<DEALS_DSID>"></database>

---

📖 **完了案件・全案件**は [案件DB](<案件DB の URL>) のタブ（📋一覧表 / 📊ステータスボード / 📅納期カレンダー）で。タレント・クライアント登録は [task-manager 設定](<task-manager 設定ページの URL>)。メール取り込みは Claude で `/tm-sync`（毎朝自動実行あり）。
```

`<DASHBOARD_VIEW1_URL>` / `<DASHBOARD_VIEW2_URL>` / `<DEALS_DSID>` / `<案件DB の URL>` / `<task-manager 設定ページの URL>` は実際の値に置換。

> **注意（実機検証で判明）**:
> - toggle ブロック（`> [!toggle]`）の中に `<page>` タグを入れるとレンダリングが崩れる。リンクは通常の Markdown リンク `[テキスト](URL)` を使う
> - 使い方説明は長々と書かない。末尾に1行で十分（毎日見るページなので説明はノイズになる）

### 6.5.5. 完了報告でページ全幅化を案内（手動1クリック）

table 型ビューの列幅は API から制御できないため、環境によっては ⏳ テーブルがわずかに横スクロールすることがある。完了報告に以下を含めてユーザーに手動操作を案内する:

```
💡 見た目の最終調整（任意・30秒）:
ダッシュボードページ右上の「…」メニュー →「左右の余白を縮小」を ON にすると、
表が画面幅にきれいに収まります。
```

### フォールバック

`notion-create-view` が失敗したら（DSL パースエラー等）、ダッシュボードページの本文は手動作成を促す案内に切り替える:

```markdown
## 🎯 今動くべき案件（ボール別）

Notion 案件DB の「🎯 ボール別ビュー」を直接開いてください: <案件DB のボール別ビュー URL>
```

ビュー無しでも 案件DB そのものは機能するため、Skill 本体は続行する。

## 7. メタ情報DB に初期レコードを投入

`notion-create-pages`（parent: `data_source_id=META_DSID`）で 1 行作成。properties:

- `キー`: `"config"`
- `案件DB_id`: `DEALS_DSID`（UUID 文字列そのまま）
- `タレントDB_id`: `TALENTS_DSID`
- `クライアントDB_id`: `CLIENTS_DSID`
- `sync対象ラベル`: `""` (空文字)
- `バージョン`: `"v1.0"`
- 最終sync日時はこの時点では未設定（Date型は省略すれば null）

## 8. Formula 動作テストとロールバック判断

案件DB にダミー案件を 1 件 `notion-create-pages` で作成して Formula が計算されるか検証:

- properties:
  - `案件名`: `"__formula_test__"`
  - `受注金額`: `100000`（JavaScript number）
  - `還元率`: `0.7`

`notion-fetch(id=<作成された page_id>)` で取得し、`タレント取り分` と `会社取り分` の値を見る。

> **検証時の注意**: Formula 値は `notion-fetch` のレスポンスで `formulaResult://...` の URL 文字列として返ってくる（計算済みの数値そのものは API レスポンスに含まれない）。実値の確認は Notion UI 上で目視するか、`formulaResult://` URL を別途 `notion-fetch` で辿る。テストの合否判定は「`formulaResult://` URL が含まれている = 計算式が登録された」で十分とし、数値の中身は UI で確認する運用にする。

### 検証成功時（formulaResult URL が両 Formula プロパティに付与されている）

**ページの archive / 削除は Notion Connector 非対応** のため、テスト案件 `__formula_test__` は自動削除できない。完了報告時にユーザーに「テスト案件 `__formula_test__` を Notion 上で手動削除してください」と案内する（右側「・・・」メニュー → Delete）。

### 検証失敗時（Formula が日本語プロパティ名のせいで動かない、または別のエラー）

Notion Connector では DB 全体は `notion-update-data-source(data_source_id=DEALS_DSID, in_trash=true)` で削除可能。これで自動ロールバックする選択肢もあるが、誤削除リスク回避のため、ユーザーに状況説明と確認の上で削除指示するのが安全。実装方針:

1. ユーザーに「Formula 検証失敗。案件DB を作り直しますか？」と確認
2. Yes なら `notion-update-data-source(DEALS_DSID, in_trash=true)` で削除し、英語プロパティ名 fallback DDL で再作成
3. No なら状況のみ報告して終了（ユーザー側で対応）

代替として、ユーザーに以下を案内する形式も可:

```
⚠️ 日本語プロパティ名で Formula が動作しませんでした。

英語プロパティ名版で再構築する必要があります。お手数ですが以下をお願いします:

1. Notion を開いて、たった今作成された「案件DB」を **手動でゴミ箱に入れて** ください
   （右上「…」メニュー → 「Delete」、またはページを開いて Delete）
2. 削除が完了したら、もう一度この Skill (/tm-setup) を実行してください
3. 2 回目の実行時、案件DB は英語プロパティ名で作り直されます

タレントDB / クライアントDB / メタ情報DB はそのまま残せます（手動削除不要）。
```

2 回目の実行検知は、メタ情報DBの「バージョン」が既に存在することで行う。バージョンが `v1.0` のまま案件DB が存在しない状態を検知したら、英語プロパティ名版で案件DBのみ再作成:

- title→`deal_name`, タレント名→`talent`, クライアント名→`client`, 受注金額→`amount`, 還元率→`commission_rate`, タレント取り分→`talent_share` (= `prop("amount") * prop("commission_rate")`), 会社取り分→`company_share` (= `prop("amount") * (1 - prop("commission_rate"))`)、その他も英字に
- メタ情報DBの「バージョン」を `v1.0-en` に更新
- メタ情報DBの「案件DB_id」を新しい data_source_id で上書き
- 再度ダミー案件で Formula 検証 → 成功なら完了報告（テスト案件の手動削除案内付き）、失敗ならユーザーに「Notion Connector の Formula サポート範囲外の可能性があります」とエスカレーション

## 9. 完了報告

ユーザーに以下を表示（テスト案件の手動削除指示を必ず含める）:

```
✅ task-manager セットアップ完了

🏠 メインで開くページ:
- 📋 案件管理（ダッシュボード）: <DASHBOARD_URL>
  ↑ 毎日ここを開きます。ボール別ボードと全案件一覧が埋め込み表示されます。

作成したデータベース:
- 案件DB: <URL>
- タレントDB: <URL>
- クライアントDB: <URL>
- メタ情報DB: <URL>

⚙️ 設定ハブページ: <URL>
  ↑ タレント・クライアントの管理、設定変更などはここから。

⚠️ 手動作業のお願い:
案件DB に Formula 動作確認用のテスト案件「__formula_test__」が残っています。
お手数ですが Notion 上で開いて「・・・」メニュー → Delete で削除してください。
（Notion Connector はページ削除に未対応のため自動削除できません）

次のステップ:
1. /tm-add-talent でタレントを登録
2. /tm-add-client でクライアントを登録
3. /tm-sync で初回メール取り込み

スキーマのバージョン: <v1.0 または v1.0-en>

👆 Notion サイドバーに「📋 案件管理」をブックマークしておくと便利です。
```

# 出力フォーマット

完了時の出力は手順 9 の通り。途中失敗時は失敗ステップ・エラー内容・次のアクションを箇条書きで提示する。

# 判断指針 / エッジケース

- 既に「task-manager 設定」ページが親ページ配下に存在する場合: ユーザーに上書きするか中断するか確認。デフォルトは中断。
- 親ページへの書き込み権限がない場合: Notion Connector の権限スコープを再設定するよう案内。
- DUAL Relation 作成が Connector でサポートされていなかった場合: 単方向 Relation で代替し、メタ情報DBの「バージョン」を `v1.0-singlerel` に変更。

# 完了条件

- 4 つの DB（案件 / タレント / クライアント / メタ情報）が「task-manager 設定」ページ配下に作成されている
- メタ情報DB に config レコードが 1 件、各 data_source_id が記録されている
- 案件DB の Formula が正しく計算される（v1.0 または v1.0-en）
- ユーザーに 4 DB の URL が提示されている
