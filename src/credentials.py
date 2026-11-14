"""Per-run credentials and backend overrides.

The Streamlit UI lets a visitor paste their own API keys and pick a model.
Those values must only apply to that visitor's research run. Writing them to
``os.environ`` would make them process-wide: every other session on the same
server (e.g. a public demo) would start using, and could read back, a
stranger's key.

Instead the UI keeps them in ``st.session_state`` and activates them for the
duration of one agent run with :func:`use_credentials`. Code that needs a key
calls :func:`get_credential`, which checks the active overrides first and then
falls back to the server configuration (environment, then ``settings``).

The overrides live in a ``ContextVar``. Worker threads do not inherit context
automatically, so code that fans out to a pool must submit
``contextvars.copy_context().run`` (see ``parallel_search_node``).
"""
import os
from contextlib import contextmanager
from contextvars import ContextVar
from types import MappingProxyType
from typing import Iterator, Mapping, Optional

from . import config

_EMPTY: Mapping[str, str] = MappingProxyType({})
_overrides: ContextVar[Mapping[str, str]] = ContextVar("credential_overrides", default=_EMPTY)


def get_credential(name: str) -> Optional[str]:
    """Return the value for ``name`` (e.g. ``"TAVILY_API_KEY"``), or None.

    Order: overrides of the current run, process environment, ``settings``.
    """
    # config.settings is looked up at call time (not imported by name) so tests
    # that patch ``src.config.settings`` are honoured.
    return _overrides.get().get(name) or os.getenv(name) or getattr(config.settings, name.lower(), None)


def server_has(name: str) -> bool:
    """True when the server itself is configured with ``name`` (ignores per-run overrides)."""
    return bool(os.getenv(name) or getattr(config.settings, name.lower(), None))


@contextmanager
def use_credentials(overrides: Optional[Mapping[str, str]]) -> Iterator[None]:
    """Activate ``overrides`` for the current context; empty values are ignored."""
    clean = {k: v for k, v in (overrides or {}).items() if v}
    token = _overrides.set(MappingProxyType(clean))
    try:
        yield
    finally:
        _overrides.reset(token)
