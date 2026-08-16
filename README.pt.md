# OpenAmer Agent

**O agente de inteligência artificial que se melhora — aprenda com a experiência, crie habilidades, lembre-se das suas preferências e trabalhe para você em qualquer lugar.**

**Traduzindo para o Português**

Por favor, forneça o texto que deseja traduzir.

## Características

- **Interface de terminal real — TUI completo com autocompletar, histórico e saída em streaming de ferramenta**
- **Vive onde você mora — Telegram, Discord, Slack, WhatsApp e mais de um gateway**
- **Aprende ao longo do tempo — memória, habilidades em melhoria contínua, recuperação de sessão cruzada**
- **Delegados & paraleliza — spawn subagentes para trabalho paralelo**
- **Automatizações agendadas — cron integrado para relatórios diários, backups, auditorias**
- **Executa em qualquer lugar — local, Docker, SSH, nuvem, sem servidor**

## Instalação Rápida

Windows (Powershell)
```powershell
iex (irm https://github.com/openamer/openamer/raw/main/scripts/install.ps1)
```

Linux / macOS
```bash
curl -fsSL https://github.com/openamer/openamer/raw/main/scripts/install.sh | bash
```

## **Começando**

```bash
openamer              # Começar a conversar
openamer setup        # **Configurando suas chaves de API e provedor**

Para configurar suas chaves de API e provedor, você precisará seguir os passos abaixo:

1. **Escolha um provedor de API**: Selecione um provedor de API que atenda às suas necessidades, como [Google Cloud](https://cloud.google.com/), [AWS](https://aws.amazon.com/) ou [Microsoft Azure](https://azure.microsoft.com/).
2. **Crie uma conta**: Crie uma conta no provedor de API escolhido. Isso geralmente envolve fornecer informações de contato e criar uma senha.
3. **Obtenha a chave de API**: Após criar sua conta, você precisará gerar uma chave de API. Isso pode ser feito no painel de controle do provedor de API.
4. **Configure as permissões**: Configure as permissões para a chave de API para que ela tenha acesso aos recursos necessários.
5. **Armazene a chave de API**: Armazene a chave de API em um local seguro, como um arquivo de configuração ou uma variável de ambiente.

**Exemplo de configuração**

Aqui está um exemplo de como configurar a chave de API no [Google Cloud](https://cloud.google.com/):

1. Acesse o [Console do Google Cloud](https://console.cloud.google.com/).
2. Clique em **Projetos** e selecione o projeto desejado.
3. Clique em **APIs e Serviços** e selecione a API desejada.
4. Clique em **Criar credenciais** e selecione **Chave de API**.
5. Siga as instruções para criar a chave de API e armazene-a em um local seguro.

Lembre-se de que a segurança é fundamental ao trabalhar com
openamer model        # Escolha seu modelo.
openamer update       # Atualize para a versão mais recente.
```

## Atualizando

O OpenAmer verifica automaticamente as atualizações e exibe uma advertência no banner de boas-vindas. Execute o comando `openamer update` para obter a versão mais recente — ele faz um backup dos dados antes disso.

## **Contribuindo**

Contribuições são bem-vindas — abra issues, envie solicitações de pull, ou participe da comunidade.

## Licença

Licença Apache 2.0. Consulte {LICENSE}.
