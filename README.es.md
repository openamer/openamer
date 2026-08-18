# OpenAmer Agent

**OpenAmer es el agente que no se rompe — y que mejora de forma demostrable con el uso.**

Se ejecuta en tu propia máquina, te encuentra en los canales que ya usas y mejora cuanto más lo usas. Dos cosas lo distinguen:

1. **No se rompe.** La auto-actualización está endurecida contra los modos de fallo que dejan a otros agentes a medio instalar — bloqueos de archivos, instalaciones interrumpidas, marcadores de recuperación obsoletos. El agente verifica antes de afirmar y reporta errores reales en lugar de inventar resultados.
2. **Mejora de forma demostrable con el uso.** La memoria persiste entre sesiones, las habilidades se destilan de tareas difíciles y se refinan al reutilizarlas, y el enjambre A2A comparte conocimiento curado, firmado y sin fugas entre nodos. Aprendizaje que puedes observar, no un eslogan.

Usa cualquier modelo — OpenRouter, OpenAI, tu propio endpoint y [muchos más](https://github.com/openamer/openamer/blob/main/website/docs/integrations/providers). Cambia con `openamer model` — sin cambios de código, sin dependencia.

## Funciones

| Función | Descripción |
|---|---|
| **No se rompe** | Auto-actualización endurecida que sobrevive a bloqueos de archivos, instalaciones interrumpidas y marcadores de recuperación obsoletos. El agente verifica antes de afirmar y reporta errores reales en lugar de inventar resultados. |
| **Mejora de forma demostrable** | La memoria persiste entre sesiones, las habilidades se destilan de tareas difíciles y se refinan al reutilizarlas, y el enjambre A2A comparte conocimiento curado, firmado y sin fugas entre nodos. |
| **Interfaz de terminal real** | TUI completo con edición multilínea, autocompletado de comandos slash, historial de conversación, interrupción-y-redirección y salida de herramientas en streaming en vivo. |
| **Vive donde tú vives** | Telegram, Discord, Slack, WhatsApp, Signal y CLI — una puerta de enlace, una conversación que te sigue en cada canal. Las notas de voz se transcriben automáticamente. |
| **Automatizaciones programadas** | Programador cron integrado con entrega a cualquier plataforma. Describe un informe diario, una copia de seguridad nocturna o una auditoría semanal en lenguaje natural y se ejecuta sin supervisión. |
| **Delega y paraleliza** | Genera subagentes aislados para flujos de trabajo paralelos, o escribe scripts de Python que llaman herramientas por RPC para colapsar pipelines de varios pasos en un solo turno. |
| **Se ejecuta en cualquier lugar, no solo en tu portátil** | Seis backends de terminal — local, Docker, SSH, Singularity, Modal y Daytona. Daytona y Modal añaden persistencia serverless, para que el entorno de tu agente hiberne en reposo y despierte bajo demanda — casi sin coste entre sesiones. |
| **Privado por defecto** | Números de teléfono, contraseñas, correos y números de tarjeta se redactan antes de almacenarse. El sistema operativo, el hardware y el modelo de tu nodo permanecen en tu propio prompt de sistema. |
| **Listo para investigación** | Generación de trayectorias por lotes y compresión de trayectorias para entrenar la próxima generación de modelos que llaman herramientas. |

## Instalación rápida

### Linux, macOS, WSL2, Termux

```bash
curl -fsSL https://raw.githubusercontent.com/openamer/openamer/main/scripts/install.sh | bash
```

### Windows (nativo, PowerShell)

```powershell
iex (irm https://raw.githubusercontent.com/openamer/openamer/main/scripts/install.ps1)
```

El instalador se encarga de todo: uv, Python 3.11, Node.js, ripgrep, ffmpeg y un Git Bash portátil.

## Primeros pasos

```bash
openamer              # CLI interactivo — iniciar una conversación
openamer model        # Elegir proveedor y modelo de LLM
openamer tools        # Configurar qué herramientas están activas
openamer gateway      # Iniciar la puerta de enlace de mensajería (Telegram, Discord, …)
openamer setup        # Ejecutar el asistente de configuración completo
openamer update       # Actualizar a la última versión
openamer doctor       # Diagnosticar problemas
```

## Actualización

OpenAmer se mantiene actualizado automáticamente. En cada inicio comprueba en segundo plano si hay una versión más reciente — si la hay, el banner de bienvenida muestra `⚠ N commits atrás — ejecuta 'openamer update'` dentro del chat.

```bash
openamer update
```

## Documentación

La documentación completa está en **[OpenAmer Docs](https://github.com/openamer/openamer/blob/main/website/docs/)**.

## Comunidad

- 💬 [Discord](https://discord.gg/openamer)
- 📚 [Skills Hub](https://agentskills.io)
- 🐛 [Issues](https://github.com/openamer/openamer/issues)

## Licencia

Apache License 2.0 — ver [LICENSE](LICENSE).
