# OpenAmer Agent

**自我向上昇するAIエージェント — 経験から学び、スキルを作り、好みを思い出して、どこでもあなたのために働きます。**

**翻訳モデルを切り替える**
`openamer model` を使用して、OpenRouter、OpenAI、DeepSeekなど、さまざまなモデルを切り替えることができます。

## 機能

- ****ターミナルインターフェイス — 完全なTUI（テキストベースのユーザーインターフェイス）で、オートコンプリート、履歴、ストリーミングツール出力が可能****
- ****あなたが住む場所でも**（Telegram、Discord、Slack、WhatsAppなどから１つのゲートウェイ）**
- **時間とともに学習 — メモリ、セルフ・インプロビング・スキル、セッション間の回顧**
- **デリゲート & パラレル化 — サブエージェントを生成してパラレルワークを実行**
- ****自動スケジュール設定** — daily reports、バックアップ、オーディットのための組み込みcron**
- **ローカル、Docker、SSH、クラウド、サーバーレスなど、どこでも実行可能です。**

## **Quick Install**

### **手順**

1. **インストール**
   * `pip install quickinstall` を実行します。
2. **設定**
   * `quickinstall init` を実行して設定を初期化します。
3. **プロジェクトの設定**
   * `quickinstall project init` を実行してプロジェクトの設定を初期化します。
4. **依存関係のインストール**
   * `quickinstall install` を実行して依存関係をインストールします。
5. **サーバー起動**
   * `quickinstall start` を実行してサーバーを起動します。

### **コマンド**

| コマンド | 説明 |
| --- | --- |
| `quickinstall init` | 設定を初期化します。 |
| `quickinstall project init` | プロジェクトの設定を初期化します。 |
| `quickinstall install` | 依存関係をインストールします。 |
| `quickinstall start` | サーバーを起動します。 |
| `quickinstall stop` | サーバーを停止します。 |
| `quickinstall restart` | サーバーを再起動します。 |

### **オプション**

| オプション | 説明 |
| --- | --- |
| `-h` | ヘルプを表示します。 |
| `-v` | バージョン情報を表示します。 |

パワー シェル (`Windows (PowerShell)`):
```powershell
iex (irm https://github.com/openamer/openamer/raw/main/scripts/install.ps1)
```

Linux / macOS:
```bash
curl -fsSL https://github.com/openamer/openamer/raw/main/scripts/install.sh | bash
```

## はじめ方

```bash
openamer              # 話を始めましょう。
openamer setup        # **API キーとプロバイダーの設定**

API キーとプロバイダーの設定は、API を使用するプロジェクトの基盤です。ここでは、API キーとプロバイダーの設定方法について説明します。

**ステップ 1: API プロバイダーの選択**

API プロバイダーの選択は、API キーの取得方法と使用方法に影響します。一般的な API プロバイダーには、以下のものがあります。

*   **Google Cloud Platform**: Google Cloud Platform の API キーは、Google Cloud Console で取得できます。
*   **AWS**: AWS の API キーは、AWS Management Console で取得できます。
*   **Microsoft Azure**: Microsoft Azure の API キーは、Azure Portal で取得できます。

**ステップ 2: API キーの取得**

API キーは、API プロバイダーのウェブサイトまたは管理コンソールで取得できます。API キーは、API キーの値と、API キーの説明 (説明) として表示されます。

**ステップ 3: API キーの設定**

API キーは、API の設定で使用します。API キーは、API の URL に含めます。たとえば、API キーを使用して API を呼び出す場合、API キーは、API の URL のパラメータとして含めます。

**ステップ 4: API キーの保存**

API キーは、安全な場所で保存する必要があります。API キーは、API の設定で使用するため、API キーを安全な場所で保存する必要があります。

**ステップ 5: API キーのテスト**

API キーは、API の設定で使用するため、API キーをテストする必要があります。API キーをテストするには、API の URL に含めることができます。

**ステップ
openamer model        # **モデルを選択してください**

*   **基礎モデル**: 基礎的な翻訳モデル
*   **進んだモデル**: 進んだ翻訳モデル
*   **AIモデル**: AIを使用した翻訳モデル
openamer update       # 最新バージョンにアップデートする
```

## 更新中

OpenAmerは自動的に更新を確認し、ウェルカムバナーに警告を表示します。 最新バージョンを取得するには、openamer updateを実行してください — これはデータのバックアップを実行します。

## **コントリビュート**

貢献は歓迎されています — 開いている問題、プルリクエストを提出する、またはコミュニティに参加する。

## ライセンス

Apache ライセンス 2.0。 {LICENSE} を参照。
