## ペルミィ（Permy）サーバサイド：SSOTと作業ルール（最優先）

- SSOT参照順は必ず：spec_rule_v5.md → spec_v5.md → spec_serverside_v3.md →（必要なら）spec_serverside_dev_v4.md / spec_serverside_impl_dev_v2.md
- 破壊操作（reset/filter/rm/全置換/git clean等）は禁止。必要な場合は「事実取得→対象確認→バックアップ方針→実行」の順で、必ずユーザー確認を取る。
- コードは推測で書き換えない。必要なら該当ファイルをユーザーに提示してもらう。
- 動作確認は spec_serverside_v3.md の受け入れ条件を「順番固定・1手ずつ」で進める。
- Windows/PowerShell前提。bashのヒアドキュメント（<<）等は使わない。

### 正しいバックエンド起動（PowerShell）
- backend 直下で .venv を有効化して uvicorn を起動する：
  - .\.venv\Scripts\Activate.ps1
  ## ペルミィ（Permy）サーバサイド：SSOTと作業ルール（最優先）

  - SSOT（Single Source Of Truth）参照順は必ず次のとおりです：`spec_rule_v5.md` → `spec_v5.md` → `spec_serverside_v3.md` →（必要なら）`spec_serverside_dev_v4.md` / `spec_serverside_impl_dev_v2.md`
  - 破壊的操作（reset/filter/rm/全置換/git clean等）は原則禁止。必要な場合は「事実取得 → 対象確認 → バックアップ方針 → 実行」の順で、必ずユーザー確認を取ってください。
  - コードを推測で書き換えないでください。変更が必要な場合は、該当ファイルをユーザーに提示して同意を得てください。
  - 動作確認や手順は `spec_serverside_v3.md` の受け入れ条件に従い、「手順を固定して1手ずつ」進めてください。
  - 環境は Windows / PowerShell 前提です。bash のヒアドキュメント（<<）等は使用しないでください。

  ### 正しいバックエンド起動（PowerShell）

  - `backend` 直下で仮想環境を有効化し、`uvicorn` で起動します：

  ```powershell
  .\.venv\Scripts\Activate.ps1
  $env:REDIS_DISABLED="true"
  uvicorn app.main:app --host 127.0.0.1 --port 8000
  ```

  (起動スクリプトがある場合は `start_radius_memory.ps1` を使ってください)

  ### DB 初期化

  - 以下を実行してください：

  ```powershell
  python -m app.scripts.init_db
  ```

  ## Copilot / AI エージェント向け指示（TalkAssist）

  以下は、このリポジトリで AI コード補助エージェントが生産的に作業するための簡潔な指示です。

  ### プロジェクト構成（要点）
  - バックエンド: `backend/` — API とサービス本体（アプリコードは [backend/app](backend/app) に配置）。
  - フロントエンド: `frontend/` — Flutter アプリ（エントリは [frontend/lib/main.dart](frontend/lib/main.dart)）。

  ### コードスタイル
  - `backend/app` の既存スタイルに従ってください：4 スペースインデント、存在する箇所は型ヒントを使う、小さく責務の明確なモジュールを保つ（参考: [backend/app/main.py](backend/app/main.py)）。
  - 関数は短く保ち、エラーは明示的に返すか例外で扱ってください（参考: [backend/app/errors.py](backend/app/errors.py)）。
  - Flutter/Dart は `frontend/lib` のパターンと `analysis_options.yaml` に従ってください。

  ### アーキテクチャの概要
  - バックエンドは HTTP API で、`routes/`、`services/`、`middleware/` に分割されています（[backend/app](backend/app)）。
  - LLM 統合は [backend/app/ai_client.py](backend/app/ai_client.py) に集約され、設定は [backend/app/config.py](backend/app/config.py) を参照します。
  - 横断的関心事（レート制限、セーフティ、冪等性）はそれぞれ専用モジュールで扱われます（例: [backend/app/ratelimit.py](backend/app/ratelimit.py)、[backend/app/safety_gate.py](backend/app/safety_gate.py)、[backend/app/services/idempotency.py](backend/app/services/idempotency.py)）。

  ### ビルド・実行・テスト（短い手順）

  - バックエンド（Windows/PowerShell 例）:

  ```powershell
  python -m venv .venv
  .venv\Scripts\Activate.ps1
  pip install -r backend/requirements.txt
  # 開発用起動（またはリポジトリの起動スクリプトを使用）
  python backend/main.py
  ```

  - 開発補助スクリプト: ルートの `dev_run.bat`、`start_api.bat` を利用できます。
  - フロントエンド: 標準的な Flutter コマンドを使用します。

  ```powershell
  cd frontend
  flutter pub get
  flutter run
  ```

  ### プロジェクトの慣習（エージェント向けの実務ルール）
  - 最小限かつ焦点を絞った編集を行ってください。公開 API やファイル名は不用意に変更しないでください。
  - バックエンドの振る舞い修正は `backend/app` 下のファイルを優先して編集してください。`routes/`、`services/`、`middleware/` の既存パターンに合わせてください。
  - 新機能追加時は、簡単な README かモジュールドキュメンテーション（docstring）を追加し、手動での検証手順を記載してください。

  ### 統合ポイントとシークレット管理
  - LLM / 外部 API の統合点: [backend/app/ai_client.py](backend/app/ai_client.py)。キーやシークレットはハードコーディングしないでください。設定は [backend/app/config.py](backend/app/config.py) または環境変数を利用してください。
  - Redis / キャッシュ: [backend/app/redis_client.py](backend/app/redis_client.py)。

  ### セキュリティと安全性
  - LLM のプロンプトや応答処理を変更する場合、既存のセーフティチェック（[backend/app/safety_gate.py](backend/app/safety_gate.py)）を保持してください。
  - 資格情報やシークレットをコミットしないでください。必要なら環境変数の利用を明記し、README に追記してください。

  ### テスト・リンターを実行するタイミング
  - バックエンド変更後は、API を起動して影響を受けるルートをスモークテストしてください（サンプルペイロード: [backend/body_ok.json](backend/body_ok.json)）。
  - Python コード変更時は、プロジェクトにテストがあれば実行し、なければ通常の静的チェックを行ってください。

  ### 不明点がある場合
  - 不確かな点があれば、最小の再現ケース（問題のファイルと失敗する入力）を提示して質問してください。修正案とローカルでの検証手順を合わせて提示してください。

  ---
  翻訳／追記しました。日本語表現や CI、コントリビューターワークフローの追加が必要なら教えてください。
