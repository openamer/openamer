"""IO Intelligence (io.net) provider profile."""

from providers import register_provider
from providers.base import ProviderProfile


class _IonetProfile(ProviderProfile):
    """IO Intelligence profile with the tool_choice quirk handled centrally.

    IO Intelligence's documented ``tool_choice`` default is ``none``, while
    the chat-completions transport sends ``tools`` without an explicit
    ``tool_choice`` on normal agent turns. Without an override, tool calls
    never fire on this provider. The profile pins ``tool_choice: "auto"``
    through ``build_extra_body`` so every request opts in.
    """

    def build_extra_body(self, *, session_id=None, **context):
        return {"tool_choice": "auto"}


ionet = _IonetProfile(
    name="ionet",
    aliases=("io-net", "io-intelligence"),
    display_name="IO Intelligence",
    description="IO Intelligence by io.net — open-weight models, OpenAI-compatible",
    signup_url="https://io.net/docs/guides/intelligence/api-keys-and-secrets",
    env_vars=("IONET_API_KEY", "IONET_BASE_URL"),
    base_url="https://api.intelligence.io.solutions/api/v1",
    auth_type="api_key",
    # The catalog is discovered live from GET {base_url}/models. The list
    # below only feeds the /model picker when the live fetch fails, so it is
    # a snapshot of agentic, tool-calling models — not a contract.
    fallback_models=(
        "deepseek-ai/DeepSeek-V4.1-Flash",
        "moonshotai/Kimi-K3",
        "zai-org/GLM-5.3",
        "meta-llama/Llama-3.3-70B-Instruct",
        "openai/gpt-oss-120b",
        "Qwen/Qwen3.8-27B",
    ),
)

register_provider(ionet)
