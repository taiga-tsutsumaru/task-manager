# task-manager セットアップ手順

芸能事務所向け Gmail × Notion 案件管理システムのセットアップガイドです。所要時間 約 20 分。

---

## 必要なもの

- **Claude Desktop**（Pro または Max プラン推奨）
  - Free プランでも動作はしますが Connector 利用回数に制限があります
- **Gmail アカウント**（案件のメールを受信しているもの）
- **Notion アカウント**（無料プランで OK。案件DBを置く親ページが書き込み可能であること）
- 所要時間: **約 20 分**

---

## ステップ 1: Gmail Connector の接続

Anthropic 公式の Gmail Connector を Claude Desktop に接続します。

1. Claude Desktop を起動
2. 左下のアイコン →「設定」→「Connectors」を開く
   ![スクショプレースホルダー: 設定 > Connectors 画面]
3. 「Add a Connector」から **Gmail** を選択
4. ブラウザが開いて Google ログイン画面が表示されるので、対象の Gmail アカウントでログイン
5. 「Claude が Gmail を読み取り、ラベルを操作し、下書きを作成する」権限を許可
   ![スクショプレースホルダー: Google 認証画面]
6. Claude Desktop に戻り、Gmail が「接続済み」になっていることを確認

### 動作確認

Claude にこう聞いてみる:

> 直近5件のメール件名を教えて

メール件名が返ってくれば OK。

---

## ステップ 2: Notion Connector の接続

1. Claude Desktop の「設定」→「Connectors」を再び開く
2. 「Add a Connector」から **Notion** を選択
3. ブラウザで Notion にログインし、「Claude が読み書きできるページ/DBを選択」画面に進む
   ![スクショプレースホルダー: Notion 権限選択]
4. **task-manager のホームになる親ページ**（後で作るデータベース群を置く場所）にアクセス権を付与
   - 既存のページでも、新しく専用ページを作っても OK
   - そのページの URL を後で使うので控えておく
5. 「接続」を押し、Claude Desktop に戻る

### 動作確認

Claude にこう聞いてみる:

> Notion で「<ホームページ名>」を検索して

該当ページが見つかれば OK。

---

## ステップ 3: Skill 集をインストール

このリポジトリの `skills/` 配下にある `.md` ファイルをすべて Claude Desktop の Skill フォルダにコピーします。

### Windows

1. エクスプローラーのアドレスバーに以下を貼って Enter:
   ```
   %APPDATA%\Claude\skills\
   ```
   フォルダが無ければ新規作成してください。
2. このリポジトリの `skills/*.md` をすべて上記フォルダにコピー
3. Claude Desktop を一度終了して再起動

### macOS

1. Finder で「移動」→「フォルダへ移動」を選び、以下を入力:
   ```
   ~/Library/Application Support/Claude/skills/
   ```
2. このリポジトリの `skills/*.md` をコピー
3. Claude Desktop を再起動

> ⚠️ 上記パスは Claude Desktop のバージョンによって変わる可能性があります。見つからない場合は、Claude Desktop の **設定 → Skills**（または同等の画面）から「Skill フォルダを開く」相当のボタンで開けます。アプリ側で案内された場所にコピーしてください。

### 確認

再起動後、Claude にこう聞く:

> /tm-help

Skill 一覧が表示されれば成功。`/tm-` で始まる Skill 群が認識されていることを確認してください（`/tm-help`, `/tm-sync`, `/tm-pending`, `/tm-report`, `/tm-setup`, `/tm-add-talent`, `/tm-add-client` 等）。

---

## ステップ 4: 初期化を実行

Claude にこう頼む:

> /tm-setup

聞かれたら **ステップ 2 で控えた親ページの URL** を貼って渡します。

`/tm-setup` は以下を自動で行います:
- 親ページ配下に「task-manager 設定」ページを作成（管理用）
- 親ページ配下に「📋 案件管理」ダッシュボードページを作成（**毎日ここを開きます**）
- 案件DB / タレントDB / クライアントDB / メタ情報DB を作成
- 案件DB に5つのビュー（一覧表 / ステータスボード / ボール別 / 納期カレンダー / タレント別ギャラリー）を作成
- ダッシュボードページに2つの埋め込みビュー（ボール別リスト / 全案件テーブル）を配置
- 設定ページに運用ルールを書き込み
- 動作テスト（ダミー案件で Formula 検証 → 完了後はユーザーが手動削除）

完了すると **ダッシュボードページのURL + 設定ハブのURL + 4 DB のURL** が表示されます。Notion で「📋 案件管理」を開いて、ボール別リストと全案件一覧が見えていれば成功。

---

## ステップ 5: タレントとクライアントの初期登録

Claude にこう頼む（例）:

> /tm-add-talent 山田太郎、エイリアスはタロウとT-ROCK、メアドは taro@example.com

> /tm-add-client 株式会社A、ドメインは example.co.jp と example.com

所属タレント全員 + 主要取引先を一通り登録しましょう（後からいつでも追加可能）。

---

## ステップ 6: 初回 sync の試運転

Claude にこう頼む:

> /tm-sync

初回は「最終sync日時」が空なので、過去 7 日分のメールが取り込み対象になります。

結果レポートが表示されたら:
- 「要確認」に入った件は手動で振り分け
- Notion 案件DBで意図通りに案件が作成されているか確認

意図しない案件化があれば、Notion 上で削除し、AIメモにフィードバックを書いておくと次回 sync で参考にできます。

---

## ステップ 7: 定期実行（毎朝の自動 sync）の設定

毎朝決まった時間に自動で `/tm-sync` を走らせるよう設定します。Claude の **Scheduled Tasks** 機能を使います。

### 7-1. メタ情報DB から ID を控える

`/tm-setup` 完了時に Claude が表示する 4 つの `data_source_id` を控えておきます。後でなくしたら Claude に聞くのが一番楽です:

> 「task-manager の各 DB の data_source_id を教えて」

Claude が「task-manager 設定」配下のメタ情報DBを `notion-fetch` で読んで、以下の4つを返してくれます:

- 案件DB の data_source_id（`DEALS_DSID`）
- タレントDB の data_source_id（`TALENTS_DSID`）
- クライアントDB の data_source_id（`CLIENTS_DSID`）
- メタ情報DB の config レコードの page_id（`CONFIG_PAGE_ID`）

> 💡 補足: `data_source_id` は Notion の URL からは直接見えない内部識別子です。手作業で取得する方法はないので、必ず Claude 経由で取得してください。一度ファイルに控えておけば、以降のスケジュール設定で使い回せます。

### 7-2. Claude にスケジュール設定を依頼

Claude Desktop でこう頼む:

> 毎日朝9時に /tm-sync を実行するスケジュールタスクを作って。タスクIDは tm-sync-daily、プロンプトは下記参照。
>
> （プロンプト本文）
> task-manager の定期メール同期。`C:\path\to\task manager\skills\tm-sync.md` の手順に従って実行する。
> - 案件DB: <DEALS_DSID>
> - タレントDB: <TALENTS_DSID>
> - クライアントDB: <CLIENTS_DSID>
> - メタ情報DB config: <CONFIG_PAGE_ID>
> 完了したら結果サマリ（取得/更新/新規/要確認件数）と要対応案件リストを通知。

Claude が `create_scheduled_task` を呼んでスケジュールが登録されます。承認ダイアログが出たら OK。

### 7-3. 初回手動実行で承認を済ませる（🚨 最重要、絶対にやる）

**この手順を飛ばすと、明日朝の自動実行が「承認待ち」のまま無言で止まります。** 朝メールが反映されてない…と気づくのは午後になってから、という最悪のパターンを避けるため必ず実施してください。

1. Claude Desktop の左サイドバーから **「Scheduled」セクション** を開く
2. `tm-sync-daily` をクリック
3. 画面に出る **「Run now」** ボタンをクリック
4. 実行中に Gmail / Notion コネクタの **権限承認ダイアログが2つ出る** → どちらも「許可」をクリック
5. 「完了」と表示されたら OK

ここまでやれば以降の自動実行は無人で動きます。承認はタスクに紐付いて保存されるので、毎回聞かれません。

### 7-4. 設定の確認・変更

Claude にこう頼めば確認できる:

> scheduled tasks を一覧表示

時間を変えたい場合（例: 朝 8 時に変更）:

> tm-sync-daily の実行時刻を朝 8 時に変更

### 注意: PC・アプリの起動状態

- Claude scheduled task は **Anthropic 側のインフラで実行**されますが、結果通知は Claude Desktop が起動している時に届きます
- アプリが閉じている時に発火した分は、次回起動時に追いついて通知されます
- なので「PC を毎朝必ず開く」を前提に組むのが現実的

### 任意タイミングでの実行

定期実行に加えて、いつでも手動発火できます:

1. **Claude Desktop で `/tm-sync`**
2. **「Scheduled」セクションで `tm-sync-daily` → Run now」**
3. **モバイル版 Claude アプリ**（同じアカウント）から `/tm-sync`

---

## 日常運用の流れ

| いつ | コマンド | 何が起きる |
|------|----------|-----------|
| 朝 | `/tm-pending` | 今返信すべき案件をチェック |
| 朝・昼・夜 | `/tm-sync` | 新着メールを案件DB に取り込み |
| 月曜朝 | `/tm-report` | 先週のサマリと今週のフォーカスを確認 |
| 新規所属/取引先発生時 | `/tm-add-talent` / `/tm-add-client` | マスター追加 |

自然言語で個別操作も OK:
- 「A社の××案件、ステータスを納品済に」
- 「Bさん宛の返信下書き作って」

---

## トラブルシュート

### `/tm-` Skill が認識されない
- `%APPDATA%\Claude\skills\` （Windows）にファイルがあるか確認
- Claude Desktop を完全終了（タスクトレイから）→ 再起動
- ファイル名が `tm-xxx.md` 形式か確認

### `/tm-sync` がエラーになる
- Gmail / Notion Connector が「接続済み」になっているか確認
- メタ情報DB が空になっていないか Notion で確認
- 設定ページが消えていないか確認

### Notion DB の Formula が「計算できません」になる
- `/tm-setup` 時点で日本語プロパティ名の Formula が動かなかった可能性
- 「task-manager 設定」ページのメタ情報DB の「バージョン」が `v1.0-en` になっていれば英語名版で動作中
- 案件DB を一度削除してから `/tm-setup` をやり直すと再構築されます（ただし既存案件データも消えるので注意）

### 同じメールが何度も新規案件化される
- 該当案件の「Gmail Message ID履歴」が空になっていないか確認
- クライアントDB にそのドメインが登録されているか確認

### スケジュールタスクが発火しない / 失敗する
- Claude Desktop の「Scheduled」セクションで `tm-sync-daily` が「Enabled」になっているか確認
- 「Run now」で手動実行 → 承認ダイアログが出れば許可
- アプリが完全に閉じている時に発火予定だった分は、次回起動時に追いついて実行されます
- 失敗が続く場合: Claude にスケジュールタスクの最新実行ログを聞いて、エラー内容を確認

---

## 困ったときの連絡先

セットアップ作業者: <ここに名前/連絡先>

不具合・要望: <ここに連絡手段（Slack / メール）>

Claude Desktop 自体の不具合: https://support.anthropic.com/
