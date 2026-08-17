# OpenAmer Agent

**自我進化的 AI 代理 —— 從經驗中學習、創造技能、記住您的偏好，並在任何地方為您工作。**

使用任何您想要的模型 — OpenRouter、OpenAI、DeepSeek 等。透過 `openamer model` 即可切換 — 無需修改程式碼。

## 功能特點

- **真正的終端機介面 — 具備自動完成、歷史紀錄及串流工具輸出的完整 TUI**
- **就在你使用的地方 — 透過單一閘道整合 Telegram、Discord、Slack、WhatsApp 等多個平台**
- **隨時間學習 — 記憶力、自我提升技能、跨對話回溯**
- **委派與平行化 — 產生子代理以進行平行工作**
- **排程自動化 — 內建用於每日報告、備份及稽核的 cron 服務**
- **隨處運行 — 本地、Docker、SSH、雲端、Serverless**

## 快速安裝

Windows (PowerShell)：
```powershell
iex (irm https://raw.githubusercontent.com/openamer/openamer/main/scripts/install.ps1)
```

Linux / macOS：
```bash
curl -fsSL https://raw.githubusercontent.com/openamer/openamer/main/scripts/install.sh | bash
```

## 入門指南

```bash
openamer              # 開始聊天
openamer setup        # 設定您的 API 金鑰與提供者
openamer model        # 選擇您的模型
openamer update       # 更新至最新版本
```

## 更新中

OpenAmer 會自動檢查更新，並在歡迎橫幅中顯示警告。請執行 `openamer update` 以獲取最新版本 — 系統會先為您的數據建立備份。

## 貢獻

歡迎貢獻 — 提交 issue、發送 pull request 或加入社群。

## 授權許可

Apache License 2.0。請參閱 {LICENSE}。
