# OpenAmer Agent

**OpenAmer 是一个不会崩溃的智能体——并且会随着使用而可验证地不断改进。**

它运行在你自己的机器上，在你已经使用的渠道中与你相遇，并且用得越久就越好。有两件事让它与众不同：

1. **它不会崩溃。** 自更新针对那些让其他智能体半途而废的故障模式进行了加固——文件锁、中断的安装、过期的恢复标记。智能体在断言之前先验证，并报告真实错误，而不是编造结果。
2. **它会随着使用而可验证地改进。** 记忆跨会话持久存在，技能从困难任务中提炼并在复用时精炼，A2A 集群在节点之间共享经过整理、签名且无泄漏的知识。这是你可以观察到的学习，而不是一句口号。

使用任何模型——OpenRouter、OpenAI、你自己的端点以及[更多](https://github.com/openamer/openamer/blob/main/website/docs/integrations/providers)。用 `openamer model` 切换——无需修改代码，无锁定。

## 功能

| 功能 | 描述 |
|---|---|
| **不会崩溃** | 加固的自更新，能够经受文件锁、中断的安装和过期的恢复标记。智能体在断言之前先验证，并报告真实错误，而不是编造结果。 |
| **可验证地改进** | 记忆跨会话持久存在，技能从困难任务中提炼并在复用时精炼，A2A 集群在节点之间共享经过整理、签名且无泄漏的知识。 |
| **真正的终端界面** | 完整的 TUI，支持多行编辑、斜杠命令自动补全、对话历史、中断与重定向，以及工具输出的实时流式显示。 |
| **生活在你所在之处** | Telegram、Discord、Slack、WhatsApp、Signal 和 CLI——一个网关，一段跨每个渠道跟随你的对话。语音备忘录会自动转写。 |
| **定时自动化** | 内置 cron 调度器，可投递到任何平台。用自然语言描述每日报告、夜间备份或每周审计，它就会无人值守地运行。 |
| **委派与并行** | 为并行工作流启动隔离的子智能体，或编写通过 RPC 调用工具的 Python 脚本，将多步骤流水线压缩为单轮。 |
| **随处运行，而不仅限于你的笔记本** | 六种终端后端——本地、Docker、SSH、Singularity、Modal 和 Daytona。Daytona 和 Modal 提供无服务器持久化，让你的智能体环境在空闲时休眠、按需唤醒——会话之间几乎零成本。 |
| **默认私密** | 电话号码、密码、电子邮件和卡号在存储前会被脱敏。你节点的操作系统、硬件和模型保留在你自己的系统提示中。 |
| **研究就绪** | 批量轨迹生成和轨迹压缩，用于训练下一代调用工具的模型。 |


| **带测试门的自我修改** — 修改核心代码、技能或插件；失败时自动回滚 | `scripts/self_modify.py` + Skill |
| **插件发现** — 在GitHub上搜索社区插件 | `openamer plugins search` |

| **带测试门的自我修改** — 修改核心代码、技能或插件；失败时自动回滚 | `scripts/self_modify.py` + Skill |
| **插件发现** — 在GitHub上搜索社区插件 | `openamer plugins search` |
## 快速安装

### Linux、macOS、WSL2、Termux

```bash
curl -fsSL https://raw.githubusercontent.com/openamer/openamer/main/scripts/install.sh | bash
```

### Windows（原生，PowerShell）

```powershell
iex (irm https://raw.githubusercontent.com/openamer/openamer/main/scripts/install.ps1)
```

安装程序会处理一切：uv、Python 3.11、Node.js、ripgrep、ffmpeg 以及一个便携式 Git Bash。

## 入门

```bash
openamer              # 交互式 CLI——开始对话
openamer model        # 选择 LLM 提供商和模型
openamer tools        # 配置启用的工具
openamer gateway      # 启动消息网关（Telegram、Discord 等）
openamer setup        # 运行完整的设置向导
openamer update       # 更新到最新版本
openamer doctor       # 诊断问题
```

## 更新

OpenAmer 会自动保持最新。每次启动时，它都会在后台检查是否有更新的版本——如果有，欢迎横幅会在聊天中显示 `⚠ 落后 N 个提交——运行 'openamer update'`。

```bash
openamer update
```

## 文档

完整文档位于 **[OpenAmer Docs](https://github.com/openamer/openamer/blob/main/website/docs/)**。

## 社区

- 💬 [Discord](https://discord.gg/openamer)
- 📚 [Skills Hub](https://agentskills.io)
- 🐛 [Issues](https://github.com/openamer/openamer/issues)

## 许可证

Apache License 2.0——见 [LICENSE](LICENSE)。
