"""Start the real command over stdio, as Claude Desktop would."""

import shutil
import sys
from pathlib import Path

import pytest
from mcp import Client, StdioServerParameters

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def test_server_runs_over_stdio(tmp_path):
    params = StdioServerParameters(
        # The console script is installed next to the interpreter running the tests.
        command=shutil.which("shelflife-memory", path=Path(sys.executable).parent),
        env={"SHELFLIFE_DB": str(tmp_path / "stdio.db")},
    )
    async with Client(params) as client:
        result = await client.call_tool("remember", {"text": "A note", "kind": "note"})
        assert not result.is_error
        found = await client.call_tool("recall", {"query": "note"})
        assert found.structured_content["claims"][0]["text"] == "A note"
    assert (tmp_path / "stdio.db").exists()
