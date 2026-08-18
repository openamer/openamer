# OpenAmer Agent

**OpenAmer é o agente que não quebra — e que melhora de forma comprovável com o uso.**

Ele roda na sua própria máquina, encontra você nos canais que já usa e fica melhor quanto mais você o usa. Duas coisas o diferenciam:

1. **Ele não quebra.** A auto-atualização é endurecida contra os modos de falha que deixam outros agentes pela metade — bloqueios de arquivo, instalações interrompidas, marcadores de recuperação obsoletos. O agente verifica antes de afirmar e reporta erros reais em vez de inventar resultados.
2. **Ele melhora de forma comprovável com o uso.** A memória persiste entre sessões, as habilidades são destiladas de tarefas difíceis e refinadas no reuso, e o enxame A2A compartilha conhecimento curado, assinado e sem vazamentos entre nós. Aprendizado que você pode observar, não um slogan.

Use qualquer modelo — OpenRouter, OpenAI, seu próprio endpoint e [muitos outros](https://github.com/openamer/openamer/blob/main/website/docs/integrations/providers). Troque com `openamer model` — sem mudanças de código, sem dependência.

## Funcionalidades

| Funcionalidade | Descrição |
|---|---|
| **Não quebra** | Auto-atualização endurecida que sobrevive a bloqueios de arquivo, instalações interrompidas e marcadores de recuperação obsoletos. O agente verifica antes de afirmar e reporta erros reais em vez de inventar resultados. |
| **Melhora de forma comprovável** | A memória persiste entre sessões, as habilidades são destiladas de tarefas difíceis e refinadas no reuso, e o enxame A2A compartilha conhecimento curado, assinado e sem vazamentos entre nós. |
| **Interface de terminal real** | TUI completo com edição multilinha, autocompletar de comandos slash, histórico de conversa, interrupção-e-redirecionamento e saída de ferramentas em streaming ao vivo. |
| **Vive onde você vive** | Telegram, Discord, Slack, WhatsApp, Signal e CLI — um gateway, uma conversa que segue você em cada canal. Notas de voz são transcritas automaticamente. |
| **Automações agendadas** | Agendador cron integrado com entrega em qualquer plataforma. Descreva um relatório diário, um backup noturno ou uma auditoria semanal em linguagem natural e ele roda sem supervisão. |
| **Delega e paraleliza** | Inicie subagentes isolados para fluxos de trabalho paralelos, ou escreva scripts Python que chamam ferramentas via RPC para colapsar pipelines de várias etapas em um único turno. |
| **Roda em qualquer lugar, não só no seu laptop** | Seis backends de terminal — local, Docker, SSH, Singularity, Modal e Daytona. Daytona e Modal adicionam persistência serverless, para que o ambiente do seu agente hiberne em repouso e desperte sob demanda — quase sem custo entre sessões. |
| **Privado por padrão** | Números de telefone, senhas, e-mails e números de cartão são redigidos antes de qualquer armazenamento. O sistema operacional, o hardware e o modelo do seu nó permanecem no seu próprio prompt de sistema. |
| **Pronto para pesquisa** | Geração de trajetórias em lote e compressão de trajetórias para treinar a próxima geração de modelos que chamam ferramentas. |

## Instalação rápida

### Linux, macOS, WSL2, Termux

```bash
curl -fsSL https://raw.githubusercontent.com/openamer/openamer/main/scripts/install.sh | bash
```

### Windows (nativo, PowerShell)

```powershell
iex (irm https://raw.githubusercontent.com/openamer/openamer/main/scripts/install.ps1)
```

O instalador cuida de tudo: uv, Python 3.11, Node.js, ripgrep, ffmpeg e um Git Bash portátil.

## Primeiros passos

```bash
openamer              # CLI interativo — iniciar uma conversa
openamer model        # Escolher o provedor e o modelo de LLM
openamer tools        # Configurar quais ferramentas estão ativas
openamer gateway      # Iniciar o gateway de mensagens (Telegram, Discord, …)
openamer setup        # Executar o assistente de configuração completo
openamer update       # Atualizar para a versão mais recente
openamer doctor       # Diagnosticar problemas
```

## Atualização

O OpenAmer se mantém atualizado automaticamente. A cada inicialização, ele verifica em segundo plano se há uma versão mais recente — se houver, o banner de boas-vindas mostra `⚠ N commits atrás — execute 'openamer update'` dentro do chat.

```bash
openamer update
```

## Documentação

A documentação completa está em **[OpenAmer Docs](https://github.com/openamer/openamer/blob/main/website/docs/)**.

## Comunidade

- 💬 [Discord](https://discord.gg/openamer)
- 📚 [Skills Hub](https://agentskills.io)
- 🐛 [Issues](https://github.com/openamer/openamer/issues)

## Licença

Apache License 2.0 — veja [LICENSE](LICENSE).
