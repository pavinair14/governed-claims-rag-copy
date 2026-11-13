import json
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from warehouse_mcp.errors import ErrorCode, ToolError
from warehouse_mcp.scope import Scope

TTL_SECONDS = 300


def canonical_args(args: BaseModel) -> dict[str, Any]:
    return args.model_dump(mode="json", exclude={"confirmation_token"})


def _fingerprint(arguments: dict[str, Any]) -> str:
    return json.dumps(arguments, sort_keys=True)


@dataclass(frozen=True)
class _Issued:
    caller_id: str
    tool: str
    fingerprint: str
    proposed: str
    expires_at: float


class Confirmations:
    def __init__(
        self,
        clock: Callable[[], float] = time.monotonic,
        ttl: int = TTL_SECONDS,
    ) -> None:
        self._clock = clock
        self.ttl = ttl
        self._issued: dict[str, _Issued] = {}

    def outstanding(self) -> int:
        return len(self._issued)

    def issue(
        self, caller_id: str, tool: str, arguments: dict[str, Any], proposed: str
    ) -> str:
        now = self._clock()
        self._issued = {t: i for t, i in self._issued.items() if i.expires_at > now}
        token = secrets.token_urlsafe(16)
        self._issued[token] = _Issued(
            caller_id, tool, _fingerprint(arguments), proposed, now + self.ttl
        )
        return token

    def consume(
        self,
        token: str,
        caller_id: str,
        tool: str,
        arguments: dict[str, Any],
        proposed: str,
    ) -> None:
        issued = self._issued.pop(token, None)
        valid = (
            issued is not None
            and issued.expires_at > self._clock()
            and issued.caller_id == caller_id
            and issued.tool == tool
            and issued.fingerprint == _fingerprint(arguments)
            and issued.proposed == proposed
        )
        if not valid:
            raise ToolError(
                ErrorCode.CONFIRMATION_INVALID,
                "The confirmation token is not valid for this call. It may have "
                "expired, already been used, been issued for different arguments, or "
                "the situation may have changed since the preview. Nothing was changed.",
                field="confirmation_token",
                suggested_action=(
                    "Call again without confirmation_token to get a fresh preview, "
                    "show it to the user, and ask them to confirm again."
                ),
                example_call={"tool": tool, "arguments": arguments},
            )


def execute_write(
    confirmations: Confirmations,
    scope: Scope,
    tool: str,
    args: BaseModel,
    plan: Callable[[Scope, Any], str],
    apply: Callable[[Scope, Any], dict[str, Any]],
) -> dict[str, Any]:
    """Two-step write. `plan` validates and returns a plain-language description
    of the change (raising ToolError if it cannot happen). `apply` makes the change."""
    arguments = canonical_args(args)
    proposed = plan(scope, args)  # runs on the preview AND again on the commit

    token = args.confirmation_token
    if token is None:
        new_token = confirmations.issue(scope.caller_id, tool, arguments, proposed)
        raise ToolError(
            ErrorCode.CONFIRMATION_REQUIRED,
            f"Nothing has been changed yet. Awaiting confirmation: {proposed}",
            field="confirmation_token",
            details={
                "proposed_action": proposed,
                "confirmation_token": new_token,
                "expires_in_seconds": confirmations.ttl,
            },
            suggested_action=(
                "Show proposed_action to the user and ask them to confirm. Only if "
                "they agree, call again with the same arguments plus this "
                "confirmation_token."
            ),
            example_call={
                "tool": tool,
                "arguments": {**arguments, "confirmation_token": new_token},
            },
        )

    confirmations.consume(token, scope.caller_id, tool, arguments, proposed)
    return apply(scope, args)