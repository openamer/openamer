"""Dashboard authentication provider framework.

The dashboard auth gate engages only when the dashboard binds to a
non-loopback host without ``--insecure``. In that mode, every request must
carry a verified session from one of the registered ``DashboardAuthProvider``
plugins.

The OpenAmer provider lives in ``plugins/dashboard-auth-openamer/`` and is the
default. Third parties register their own providers via the plugin hook
``ctx.register_dashboard_auth_provider``.
"""
from openamer_cli.dashboard_auth.base import (
    DashboardAuthProvider,
    Session,
    TokenPrincipal,
    LoginStart,
    InvalidCodeError,
    InvalidCredentialsError,
    ProviderError,
    RefreshExpiredError,
    assert_protocol_compliance,
)
from openamer_cli.dashboard_auth.registry import (
    register_provider,
    get_provider,
    list_providers,
    list_token_providers,
    list_session_providers,
    clear_providers,
)

__all__ = [
    "DashboardAuthProvider",
    "Session",
    "TokenPrincipal",
    "LoginStart",
    "InvalidCodeError",
    "InvalidCredentialsError",
    "ProviderError",
    "RefreshExpiredError",
    "assert_protocol_compliance",
    "register_provider",
    "get_provider",
    "list_providers",
    "list_token_providers",
    "list_session_providers",
    "clear_providers",
]
