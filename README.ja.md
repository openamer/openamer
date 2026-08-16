# OpenAmer Agent

**自己改善するAIエージェント — 経験から学び、スキルを構築し、あなたの好みを記憶して、あらゆる場所であなたのために働きます。**

OpenRouter、OpenAI、DeepSeekなど、お好みのモデルを自由にご利用ください。`openamer model` で切り替え可能で、コードを変更する必要はありません。

## 機能

- **本物のターミナルインターフェース — オートコンプリート、履歴、ストリーミングツール出力を備えた完全なTUI**
- **あなたが使っている場所で — Telegram、Discord、Slack、WhatsAppなどを、一つのゲートウェイから**
- **時間の経過とともに学習 — メモリ、自己改善スキル、セッションを跨いだリコール**
- **委任と並列化 — 並列処理のためにサブエージェントを生成します**
- **スケジュール済みオートメーション — 日次レポート、バックアップ、監査のための組み込みcron**
- **どこでも動作します — ローカル、Docker、SSH、クラウド、サーバーレス**

## クイックインストール

Windows (PowerShell):
```powershell
iex (irm https://github.com/openamer/openamer/raw/main/scripts/install.ps1)
```

Linux / macOS:
```bash
curl -fsSL https://github.com/openamer/openamer/raw/main/scripts/install.sh | bash
```

## はじめに

```bash
openamer              # チャットを始める
openamer setup        # APIキーとプロバイダーの設定
openamer model        # モデルを選択してください
openamer update       # 最新バージョンにアップデートしてください
```

## 更新中

OpenAmerは自動的にアップデートを確認し、ウェルカムバナーに警告を表示します。最新バージョンを取得するには `openamer update` を実行してください。実行前にデータのバックアップが自動的に行われます。

## 貢献する

コントリビューションを歓迎します。オープンイシューの作成、プルリクエストの送信、またはコミュニティへの参加をお願いします。

## ライセンス

Apache License 2.0。{LICENSE} を参照してください。
