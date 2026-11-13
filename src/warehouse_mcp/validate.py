from typing import Any

from pydantic import BaseModel, ValidationError

from warehouse_mcp.errors import ErrorCode, ToolError


def parse_args(
    model: type[BaseModel],
    raw: dict[str, Any] | None,
    *,
    tool: str,
    example: dict[str, Any],
) -> Any:
    try:
        return model.model_validate(raw or {})
    except ValidationError as exc:
        raise _to_tool_error(model, exc, tool, example) from None


def _to_tool_error(
    model: type[BaseModel], exc: ValidationError, tool: str, example: dict[str, Any]
) -> ToolError:
    problems = exc.errors()
    first = problems[0]
    loc = first["loc"]
    field = ".".join(str(p) for p in loc) or None
    prop = model.model_json_schema().get("properties", {}).get(loc[0], {}) if loc else {}
    kind = first["type"]
    received = first.get("input")
    details: dict[str, Any] = {
        "problems": [
            {"field": ".".join(str(p) for p in e["loc"]) or None, "message": e["msg"]}
            for e in problems
        ]
    }

    if kind == "extra_forbidden" and field == "site":
        message = "This tool does not accept a 'site'. Your site is fixed by your session."
        action = "Remove 'site' and call again. You cannot read or act on another site."
    elif kind == "extra_forbidden":
        message = f"Unknown parameter {field!r}."
        action = f"Remove {field!r} and call again, following the example."
    elif kind == "missing":
        message = f"Required parameter {field!r} is missing."
        action = "Add the missing parameter, or ask the user for it. Do not invent a value."
    elif kind == "literal_error" and "enum" in prop:
        details["allowed_values"] = prop["enum"]
        details["received"] = received
        message = f"{field!r} must be one of {prop['enum']}; got {received!r}."
        action = "Pick one of the allowed values, or ask the user which they mean."
    elif kind == "string_pattern_mismatch":
        details["pattern"] = prop.get("pattern")
        details["received"] = received
        message = f"{field!r} has the wrong format: got {received!r}, expected pattern {prop.get('pattern')}."
        action = "Correct the value, or ask the user for it. Do not invent one."
    elif kind.startswith("date"):
        details["received"] = received
        message = f"{field!r} must be a date in YYYY-MM-DD format; got {received!r}."
        action = "Convert to YYYY-MM-DD, or ask the user for the exact date."
    else:
        details["received"] = received
        message = f"{field!r} is invalid: {first['msg']}."
        action = "Correct the value and call again, following the example."

    return ToolError(
        ErrorCode.INVALID_ARGUMENT,
        message,
        field=field,
        details=details,
        suggested_action=action,
        example_call={"tool": tool, "arguments": example},
    )