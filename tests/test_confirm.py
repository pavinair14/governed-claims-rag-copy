import pytest

from warehouse_mcp.confirm import Confirmations, canonical_args, execute_write
from warehouse_mcp.context import SessionContext
from warehouse_mcp.errors import ErrorCode, ToolError
from warehouse_mcp.models import ToolInput, Token
from warehouse_mcp.scope import Scope


class DemoInput(ToolInput):
    item: str
    confirmation_token: Token


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class Demo:
    """Stands in for a write tool: counts applies, and can be told to fail its checks."""

    def __init__(self):
        self.applied = 0
        self.fail_plan = False
        self.suffix = ""

    def plan(self, scope, args):
        if self.fail_plan:
            raise ToolError(
                ErrorCode.SLOT_ALREADY_BOOKED, "taken", suggested_action="pick another"
            )
        return f"Do the demo thing to {args.item}{self.suffix}"

    def apply(self, scope, args):
        self.applied += 1
        return {"ok": True, "item": args.item}


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def confirmations(clock):
    return Confirmations(clock=clock)


@pytest.fixture
def demo():
    return Demo()


def run(confirmations, demo, scope, item="a", token=None, tool="demo"):
    args = DemoInput(item=item, confirmation_token=token)
    return execute_write(confirmations, scope, tool, args, demo.plan, demo.apply)


def preview(confirmations, demo, scope, **kw):
    with pytest.raises(ToolError) as caught:
        run(confirmations, demo, scope, **kw)
    assert caught.value.code == ErrorCode.CONFIRMATION_REQUIRED
    return caught.value


def refused(confirmations, demo, scope, **kw):
    with pytest.raises(ToolError) as caught:
        run(confirmations, demo, scope, **kw)
    assert caught.value.code == ErrorCode.CONFIRMATION_INVALID
    return caught.value


def test_preview_changes_nothing_and_describes_the_action(confirmations, demo, make_scope):
    err = preview(confirmations, demo, make_scope("LEEDS-01"))

    assert demo.applied == 0
    assert err.details["proposed_action"] == "Do the demo thing to a"
    assert err.details["confirmation_token"]
    assert err.details["expires_in_seconds"] == 300
    token = err.details["confirmation_token"]
    assert err.example_call == {
        "tool": "demo",
        "arguments": {"item": "a", "confirmation_token": token},
    }


def test_commit_with_the_right_token_applies_once(confirmations, demo, make_scope):
    scope = make_scope("LEEDS-01")
    token = preview(confirmations, demo, scope).details["confirmation_token"]

    assert run(confirmations, demo, scope, token=token) == {"ok": True, "item": "a"}
    assert demo.applied == 1


def test_token_cannot_be_reused(confirmations, demo, make_scope):
    scope = make_scope("LEEDS-01")
    token = preview(confirmations, demo, scope).details["confirmation_token"]
    run(confirmations, demo, scope, token=token)

    refused(confirmations, demo, scope, token=token)
    assert demo.applied == 1


def test_token_expires(confirmations, demo, clock, make_scope):
    scope = make_scope("LEEDS-01")
    token = preview(confirmations, demo, scope).details["confirmation_token"]
    clock.now += 301

    refused(confirmations, demo, scope, token=token)
    assert demo.applied == 0


def test_token_still_works_just_before_expiry(confirmations, demo, clock, make_scope):
    scope = make_scope("LEEDS-01")
    token = preview(confirmations, demo, scope).details["confirmation_token"]
    clock.now += 299

    run(confirmations, demo, scope, token=token)
    assert demo.applied == 1


def test_token_is_bound_to_the_exact_arguments(confirmations, demo, make_scope):
    scope = make_scope("LEEDS-01")
    token = preview(confirmations, demo, scope, item="a").details["confirmation_token"]

    refused(confirmations, demo, scope, item="b", token=token)
    assert demo.applied == 0
    refused(confirmations, demo, scope, item="a", token=token)  # burned by the attempt


def test_token_is_bound_to_the_tool(confirmations, demo, make_scope):
    scope = make_scope("LEEDS-01")
    token = preview(confirmations, demo, scope, tool="demo").details["confirmation_token"]

    refused(confirmations, demo, scope, tool="other_tool", token=token)
    assert demo.applied == 0


def test_token_is_bound_to_the_caller(confirmations, demo, store, make_scope):
    token = preview(confirmations, demo, make_scope("LEEDS-01")).details["confirmation_token"]
    other = Scope(store, SessionContext(caller_id="ops.other", site="LEEDS-01"))

    refused(confirmations, demo, other, token=token)
    assert demo.applied == 0


def test_made_up_token_is_refused(confirmations, demo, make_scope):
    refused(confirmations, demo, make_scope("LEEDS-01"), token="not-a-real-token")
    assert demo.applied == 0


def test_failing_business_rule_returns_its_error_and_issues_no_token(
    confirmations, demo, make_scope
):
    demo.fail_plan = True
    with pytest.raises(ToolError) as caught:
        run(confirmations, demo, make_scope("LEEDS-01"))

    assert caught.value.code == ErrorCode.SLOT_ALREADY_BOOKED
    assert confirmations.outstanding() == 0


def test_rules_are_rechecked_at_commit_time(confirmations, demo, make_scope):
    scope = make_scope("LEEDS-01")
    token = preview(confirmations, demo, scope).details["confirmation_token"]

    demo.fail_plan = True  # the world changed between preview and commit
    with pytest.raises(ToolError) as caught:
        run(confirmations, demo, scope, token=token)

    assert caught.value.code == ErrorCode.SLOT_ALREADY_BOOKED
    assert demo.applied == 0


def test_expired_tokens_are_pruned_when_new_ones_are_issued(confirmations, demo, clock, make_scope):
    scope = make_scope("LEEDS-01")
    preview(confirmations, demo, scope)
    assert confirmations.outstanding() == 1

    clock.now += 301
    preview(confirmations, demo, scope)
    assert confirmations.outstanding() == 1


def test_canonical_args_leave_out_the_token():
    args = DemoInput(item="a", confirmation_token="abc")
    assert canonical_args(args) == {"item": "a"}

def test_token_is_void_if_the_proposed_action_changed_since_the_preview(
    confirmations, demo, make_scope
):
    scope = make_scope("LEEDS-01")
    token = preview(confirmations, demo, scope).details["confirmation_token"]

    demo.suffix = " (held by someone else now)"  # same arguments, different situation
    refused(confirmations, demo, scope, token=token)

    assert demo.applied == 0