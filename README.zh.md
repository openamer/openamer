# OpenAmer Agent

**自我完善的AI代理人——从经验中学习，创造技能，记住你的偏好，和在任何地方为你工作。**

**使用 OpenRouter 翻译**
我可以使用 OpenRouter 等模型进行翻译。您可以通过在命令行中使用 `openamer model` 命令切换模型。

## **功能**

- **实时终端接口 —— 支持自动完成、历史记录和流式工具输出的完整TUI**
- **在你生活的世界里——Telegram、Discord、Slack、WhatsApp等等都从一个入口**
- ****学习过程中不断改进** —— 内存、自我提高技能、跨会话回忆**
- ****子代理** & **并行化** — **并行工作** 的 **子代理****
- ****定期自动化** — 内置 cron 日常报告、备份、审计**
- **支持所有环境 — 本地、Docker、SSH、云、无服务器**

## 快速安装

Windows (PowerShell):
```powershell
iex (irm https://github.com/openamer/openamer/raw/main/scripts/install.ps1)
```

Linux / macOS
```bash
curl -fsSL https://github.com/openamer/openamer/raw/main/scripts/install.sh | bash
```

## **开始使用**

```bash
openamer              # 开始聊天
openamer setup        # **设置 API 密钥 & 供应商**

1. **获取 API 密钥**
   - 请访问 <https://console.cloud.google.com/apis/credentials> 并登录您的 Google Cloud 帐户。
   - 点击“创建凭据”并选择“API 密钥”。
   - 选择您的项目并点击“创建 API 密钥”。
   - 复制 API 密钥并保存在安全的地方。

2. **设置 API 供应商**
   - 请访问 <https://console.cloud.google.com/apis/library> 并登录您的 Google Cloud 帐户。
   - 搜索并选择您想要使用的 API 服务（例如 Google Maps API）。
   - 点击“启用”以启用 API 服务。
   - 点击“创建凭据”并选择“API 密钥”或“服务帐户密钥”。
   - 选择您的项目并点击“创建 API 密钥”或“创建服务帐户密钥”。
   - 复制 API 密钥并保存在安全的地方。
openamer model        # **翻译工具**
openamer update       # **更新到最新版本**
```

## **更新**

OpenAmer自动检查更新并在欢迎信息中显示警告。 运行openamer update即可获取最新版本 —— 它会先备份您的数据。

## **参与贡献**

### **如何参与**

1. **创建一个新分支**: 在 GitHub 上创建一个新的分支，例如 `feature/new-feature`。
2. **提交代码**: 将你的代码提交到新分支中。
3. **创建一个 Pull Request**: 在 GitHub 上创建一个 Pull Request，描述你的代码更改。
4. **等待反馈**: 等待其他开发者审查和反馈你的代码。
5. **合并代码**: 如果你的代码被接受，会被合并到主分支中。

### **如何编写 Pull Request**

1. **描述你的代码更改**: 在 Pull Request 中描述你的代码更改，包括你解决了哪些问题或添加了哪些新功能。
2. **提供测试**: 提供测试用例，确保你的代码正确工作。
3. **提供文档**: 提供相关文档，例如 README、API 文档等。

### **如何参与社区**

1. **参与讨论**: 在 GitHub 上参与讨论，回答问题和提供帮助。
2. **报告 bug**: 如果你发现 bug，报告给我们。
3. **提供反馈**: 提供反馈，帮助我们改进项目。

### **参与协议**

1. **开源协议**: 项目使用 [MIT License](https://opensource.org/licenses/MIT)。
2. **版权**: 项目所有权归 [Your Name](https://yourname.com) 所有。
3. **贡献者协议**: 参与者必须同意 [Contributor Agreement](https://yourname.com/contributor-agreement)。

### **联系我们**

如果你有任何问题或反馈，请联系我们：[your email](mailto:your email)。

**贡献**

欢迎贡献 — 打开问题，提交拉取请求，或加入社区。

## **许可证**

许可证是一种法律文件，规定了软件或其他作品的使用、复制、修改和分发的权利和限制。它通常由软件开发者或作品的所有者创建，用于保护他们的作品权益。

许可证可以分为几种类型，包括：

* **自由和开源许可证**：允许用户自由地使用、复制、修改和分发软件或作品。
* **专有许可证**：限制了软件或作品的使用、复制、修改和分发的权利，通常需要支付许可费或获得许可方可使用。
* **共享许可证**：允许用户共享软件或作品，但可能需要遵守一定的条件或限制。

一些常见的许可证包括：

* **GPL（GNU通用公共许可证）**：是一种自由和开源许可证，允许用户自由地使用、复制、修改和分发软件。
* **MIT许可证**：是一种自由和开源许可证，允许用户自由地使用、复制、修改和分发软件。
* **Apache许可证**：是一种自由和开源许可证，允许用户自由地使用、复制、修改和分发软件。

在使用软件或作品之前，用户应该仔细阅读许可证，了解其使用、复制、修改和分发的权利和限制。

Apache License 2.0。见 {LICENSE}。
