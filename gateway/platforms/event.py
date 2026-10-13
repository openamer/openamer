"""Inbound message event types shared by every gateway platform adapter.

Compatibility module. Upstream extracted ``MessageEvent`` / ``MessageType`` /
``ProcessingOutcome`` out of ``gateway.platforms.base`` into this leaf module so
adapters could import them without pulling in the whole base. This tree has not
performed that extraction yet — the classes still live in ``base`` — but the
ported adapters (``plugins/platforms/feishu/*``, ``plugins/platforms/homeassistant``)
import from here, so the module must exist.

A re-export is deliberate, not a shortcut:

* One definition, two import paths. Defining the classes here *and* leaving them
  in ``base`` would create two distinct class objects, so ``isinstance`` checks
  and ``except``/identity comparisons across the two paths would silently fail.
* Field order is preserved. Upstream's ``MessageEvent`` puts ``user_id`` /
  ``user_name`` at positions 3-4; this tree's has ``source`` there. Replacing the
  local definition with upstream's verbatim would shift every positional
  construction site (11 of them across gateway/plugins).
* No import cycle: ``base`` does not import this module, and neither do its
  dependencies (config, session, base_exec_approval).

Migrating the definitions here (and re-exporting *from* base in the other
direction) is a separate, mechanical refactor and should be done as its own
change with the 11 positional call sites converted to keyword form first.
"""

from gateway.platforms.base import (  # noqa: F401
    MessageEvent,
    MessageType,
    ProcessingOutcome,
)

__all__ = ["MessageEvent", "MessageType", "ProcessingOutcome"]
