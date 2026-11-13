import os
from collections.abc import Mapping
from dataclasses import dataclass

SITES = ("LEEDS-01", "READING-02", "GLASGOW-03")


class StartupError(Exception):
    """The server was launched without a valid caller context."""


@dataclass(frozen=True)
class SessionContext:
    caller_id: str
    site: str


def load_context(env: Mapping[str, str] | None = None) -> SessionContext:
    env = os.environ if env is None else env

    caller_id = env.get("KESTREL_CALLER_ID", "").strip()
    site = env.get("KESTREL_ASSIGNED_SITE", "").strip()

    if not caller_id:
        raise StartupError("KESTREL_CALLER_ID is missing or empty.")
    if site not in SITES:
        raise StartupError(
            f"KESTREL_ASSIGNED_SITE must be one of {', '.join(SITES)}; got {site!r}."
        )

    return SessionContext(caller_id=caller_id, site=site)