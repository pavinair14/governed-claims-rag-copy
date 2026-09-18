from dataclasses import dataclass


VALID_SITES = {
    "LEEDS-01",
    "READING-02",
    "GLASGOW-03",
}


@dataclass(frozen=True)
class CallerContext:
    """Identity and warehouse-site scope for the current caller."""

    caller_id: str
    assigned_site: str

    def __post_init__(self) -> None:
        if self.assigned_site not in VALID_SITES:
            raise ValueError(
                f"Invalid assigned site: {self.assigned_site}"
            )


def require_site_access(
    context: CallerContext,
    requested_site: str,
) -> None:
    """Ensure the caller is allowed to access the requested site."""

    if requested_site != context.assigned_site:
        raise PermissionError(
            f"Caller is assigned to {context.assigned_site} "
            f"and cannot access {requested_site}."
        )