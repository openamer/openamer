# OpenAmer Agent

**OpenAmer は壊れないエージェント——そして、使うほどに検証可能な形で向上します。**

自分のマシン上で動作し、すでに使っているチャンネルであなたと出会い、使えば使うほど良くなります。二つの点が際立っています：

1. **壊れません。** 自己アップデートは、他のエージェントを中途半端なインストール状態に残す障害モード——ファイルロック、中断されたインストール、古いリカバリマーカー——に対して強化されています。エージェントは主張する前に検証し、結果を捏造するのではなく実際のエラーを報告します。
2. **使うほどに検証可能な形で向上します。** 記憶はセッションをまたいで持続し、スキルは難しいタスクから抽出され再利用時に洗練され、A2A スウォームはノード間でキュレーションされ署名された漏れのない知識を共有します。スローガンではなく、観察できる学習です。

任意のモデル——OpenRouter、OpenAI、独自のエンドポイント、[その他多数](https://github.com/openamer/openamer/blob/main/website/docs/integrations/providers)を使用できます。`openamer model` で切り替え——コード変更なし、ロックインなし。

## 機能

| 機能 | 説明 |
|---|---|
| **壊れない** | ファイルロック、中断されたインストール、古いリカバリマーカーを乗り越える強化された自己アップデート。エージェントは主張する前に検証し、結果を捏造するのではなく実際のエラーを報告します。 |
| **検証可能な向上** | 記憶はセッションをまたいで持続し、スキルは難しいタスクから抽出され再利用時に洗練され、A2A スウォームはノード間でキュレーションされ署名された漏れのない知識を共有します。 |
| **本物のターミナルインターフェース** | 複数行編集、スラッシュコマンドの自動補完、会話履歴、割り込みとリダイレクト、ツール出力のライブストリーミングを備えた完全な TUI。 |
| **あなたのいる場所で生きる** | Telegram、Discord、Slack、WhatsApp、Signal、CLI——一つのゲートウェイ、あらゆるチャンネルであなたを追いかける一つの会話。音声メモは自動で文字起こしされます。 |
| **スケジュールされた自動化** | 任意のプラットフォームに配信する組み込みの cron スケジューラ。日次レポート、夜間バックアップ、週次監査を自然言語で記述すれば、無人で実行されます。 |
| **委任と並列化** | 並列ワークフローのために隔離されたサブエージェントを起動するか、RPC 経由でツールを呼び出す Python スクリプトを書いて、多段階パイプラインを単一ターンに圧縮します。 |
| **ノート PC だけでなくどこでも動作** | 6 つのターミナルバックエンド——ローカル、Docker、SSH、Singularity、Modal、Daytona。Daytona と Modal はサーバーレス永続化を提供し、エージェントの環境はアイドル時に休止し、要求に応じて復帰します——セッション間のコストはほぼゼロです。 |
| **デフォルトでプライベート** | 電話番号、パスワード、メール、カード番号は保存前にマスキングされます。ノードの OS、ハードウェア、モデルはあなた自身のシステムプロンプトに留まります。 |
| **研究対応** | ツール呼び出しモデルの次世代を訓練するためのバッチ軌跡生成と軌跡圧縮。 |

## クイックインストール

### Linux、macOS、WSL2、Termux

```bash
curl -fsSL https://raw.githubusercontent.com/openamer/openamer/main/scripts/install.sh | bash
```

### Windows（ネイティブ、PowerShell）

```powershell
iex (irm https://raw.githubusercontent.com/openamer/openamer/main/scripts/install.ps1)
```

インストーラーがすべてを処理します：uv、Python 3.11、Node.js、ripgrep、ffmpeg、ポータブル Git Bash。

## はじめに

```bash
openamer              # インタラクティブ CLI——会話を開始
openamer model        # LLM プロバイダーとモデルを選択
openamer tools        # 有効なツールを設定
openamer gateway      # メッセージングゲートウェイを起動（Telegram、Discord など）
openamer setup        # 完全なセットアップウィザードを実行
openamer update       # 最新バージョンに更新
openamer doctor       # 問題を診断
```

## 更新

OpenAmer は自動的に最新状態を保ちます。起動のたびに、より新しいバージョンが利用可能かどうかをバックグラウンドで確認します——もしあれば、ウェルカムバナーがチャット内に `⚠ N コミット遅れています——'openamer update' を実行` と表示します。

```bash
openamer update
```

## ドキュメント

完全なドキュメントは **[OpenAmer Docs](https://github.com/openamer/openamer/blob/main/website/docs/)** にあります。

## コミュニティ

- 💬 [Discord](https://discord.gg/openamer)
- 📚 [Skills Hub](https://agentskills.io)
- 🐛 [Issues](https://github.com/openamer/openamer/issues)

## ライセンス

Apache License 2.0——[LICENSE](LICENSE) を参照。
