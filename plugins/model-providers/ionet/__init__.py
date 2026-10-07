"""IO Intelligence (io.net) provider profile."""

from providers import register_provider
from providers.base import ProviderProfile


class _IonetProfile(ProviderProfile):
    """IO Intelligence profile with the tool_choice quirk handled centrally.

    IO Intelligence's documented ``tool_choice`` default is ``none``, while
    the chat-completions transport sends ``tools`` without an explicit
    ``tool_choice`` on normal agent turns. Without an override, tool calls
    never fire on this provider. The profile emits ``tool_choice: "auto"``
    through ``build_extra_body`` — but only when the request actually
    carries tools. Strict OpenAI-compatible backends (vLLM-derived ones
    included) reject ``tool_choice`` alongside an empty or missing
    ``tools`` list, and the auxiliary no-tools call sites (title
    generation, compression, summaries) send no tools at all.
    """

    def build_extra_body(self, *, session_id=None, tools=None, **context):
        if tools:
            return {"tool_choice": "auto"}
        return {}


ionet = _IonetProfile(
    name="ionet",
    aliases=("io-net", "io-intelligence"),
    display_name="IO Intelligence",
    description="IO Intelligence by io.net — open-weight models, OpenAI-compatible",
    signup_url="https://io.net/docs/guides/intelligence/api-keys-and-secrets",
    env_vars=("IONET_API_KEY", "IONET_BASE_URL"),
    base_url="https://api.intelligence.io.solutions/api/v1",
    auth_type="api_key",
    default_aux_model="openai/gpt-oss-20b",
    # The catalog is discovered live from GET {base_url}/models. The list
    # below is the curated-first picker seed for plugin providers (it leads
    # the /model picker, live-discovered ids merge in after it, and it is
    # the whole list when the live fetch fails) — a snapshot of agentic,
    # tool-calling models, not a contract.
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
