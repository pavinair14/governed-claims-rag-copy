import json
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from mcp import ClientSession, StdioServerParameters, stdio_client

ROOT = Path(__file__).resolve().parents[1]


def server_env(site: str | None = "LEEDS-01", caller: str | None = "ops.test") -> dict:
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    env.pop("KESTREL_CALLER_ID", None)
    env.pop("KESTREL_ASSIGNED_SITE", None)
    if caller is not None:
        env["KESTREL_CALLER_ID"] = caller
    if site is not None:
        env["KESTREL_ASSIGNED_SITE"] = site
    return env


class Client:
    def __init__(self, session: ClientSession) -> None:
        self.session = session

    async def tools(self):
        return (await self.session.list_tools()).tools

    async def call(self, name: str, args: dict | None = None) -> tuple[bool, dict]:
        result = await self.session.call_tool(name, args or {})
        return result.is_error, json.loads(result.content[0].text)


@asynccontextmanager
async def mcp_client(site: str = "LEEDS-01"):
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "warehouse_mcp.server"],
        env=server_env(site),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield Client(session)