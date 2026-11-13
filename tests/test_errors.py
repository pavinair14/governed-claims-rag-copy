import pytest

from warehouse_mcp.errors import ErrorCode, ToolError


@pytest.mark.parametrize("code", list(ErrorCode))
def test_every_code_has_the_full_shape(code):
    err = ToolError(code, "something failed", suggested_action="do this next")
    envelope = err.to_envelope()

    assert envelope["ok"] is False
    error = envelope["error"]
    assert error["code"] == code.value
    assert set(error) >= {"code", "message", "field", "details", "suggested_action"}


def test_example_call_only_present_when_given():
    plain = ToolError(ErrorCode.NOT_FOUND, "x", suggested_action="y").to_envelope()
    assert "example_call" not in plain["error"]

    call = {"tool": "get_stock", "arguments": {"sku": "SKU-8801"}}
    with_call = ToolError(
        ErrorCode.INVALID_ARGUMENT, "x", suggested_action="y", example_call=call
    ).to_envelope()
    assert with_call["error"]["example_call"] == call


def test_code_list_matches_spec():
    assert len(ErrorCode) == 9