# OpenAmer Agent

**自我进化的 AI 智能体 —— 从经验中学习，创造技能，记住你的偏好，并在任何地方为你工作。**

随心选择任何模型 —— OpenRouter、OpenAI、DeepSeek 等等。通过 `openamer model` 即可切换 —— 无需修改代码。

## 功能特性

- **真正的终端界面 —— 具备自动补全、历史记录和工具输出流的完整 TUI**
- **就在你所在的地方 —— 一个网关即可连接 Telegram、Discord、Slack、WhatsApp 等多种平台**
- **随时间学习 —— 记忆力、自我提升技能、跨会话召回**
- **委派与并行化 —— 创建子代理以并行工作**
- **定时自动化 — 用于每日报告、备份和审计的内置 cron**
- **随处运行 —— 本地、Docker、SSH、云端、无服务器 (serverless)**

## 快速安装

Windows (PowerShell)：
```powershell
iex (irm https://raw.githubusercontent.com/openamer/openamer/main/scripts/install.ps1)
```

Linux / macOS:
```bash
curl -fsSL https://raw.githubusercontent.com/openamer/openamer/main/scripts/install.sh | bash
```

## 入门指南

```bash
openamer              # 开始聊天
openamer setup        # 设置您的 API 密钥和提供商
openamer model        # 选择您的模型
openamer update       # 更新至最新版本
```

## 更新中

OpenAmer 会自动检查更新并在欢迎横幅中显示警告。运行 `openamer update` 以获取最新版本 —— 该操作会先备份您的数据。

## 贡献

欢迎贡献 —— 提交 issue、提交 pull request 或加入社区。

## 许可证

Apache License 2.0。请参阅 {LICENSE}。
