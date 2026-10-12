"""Call the tools through an in-process MCP client, the way Claude Desktop would."""

from datetime import timedelta

import pytest
from mcp import Client

from shelflife.server import build_server

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client(store):
    async with Client(build_server(store)) as c:
        yield c


async def call(client, tool, **arguments):
    result = await client.call_tool(tool, arguments)
    assert not result.is_error, result.content[0].text
    return result.structured_content


async def call_error(client, tool, **arguments) -> str:
    result = await client.call_tool(tool, arguments)
    assert result.is_error
    return result.content[0].text


async def test_lists_the_m1_tools(client):
    tools = {t.name: t for t in (await client.list_tools()).tools}
    assert set(tools) == {"remember", "recall", "due"}
    assert set(tools["remember"].input_schema["required"]) == {"text", "kind"}
    assert "leave both empty unless you are confident" in tools["remember"].description


async def test_remember_then_recall_and_due(client, clock):
    stored = await call(
        client,
        "remember",
        text="The latest version of the mcp package on PyPI is 2.3.0",
        kind="world_fact",
        check_method="pypi",
        check_target="mcp",
    )
    assert stored["volatility"] == "fast"
    assert stored["volatility_source"] == "default"
    assert stored["check_method_source"] == "caller"
    assert stored["next_check_at"] == "2026-10-19"

    found = await call(client, "recall", query="mcp version")
    assert [c["id"] for c in found["claims"]] == [stored["id"]]

    assert (await call(client, "due"))["claims"] == []
    assert [c["id"] for c in (await call(client, "due", days=7))["claims"]] == [stored["id"]]
    clock.now += timedelta(days=7)
    assert [c["id"] for c in (await call(client, "due"))["claims"]] == [stored["id"]]


async def test_decision_with_depends_on(client):
    fact = await call(client, "remember", text="MemGuard has no published eval", kind="world_fact")
    decision = await call(
        client, "remember", text="Focus on the eval", kind="decision", depends_on=[fact["id"]]
    )
    assert decision["depends_on"] == [fact["id"]]


async def test_validation_errors_reach_the_model(client):
    message = await call_error(
        client, "remember", text="A fact", kind="world_fact", check_method="pypi"
    )
    assert "check_target is required when check_method is pypi" in message

    message = await call_error(client, "remember", text="A fact", kind="world_fact", volatility="x")
    assert "volatility" in message

    message = await call_error(client, "due", days=-1)
    assert "days must be 0 or more" in message


async def test_system_managed_fields_are_refused(client, store):
    message = await call_error(
        client, "remember", text="A fact", kind="world_fact", status="fresh", id="mine"
    )
    assert message == "remember does not accept: id, status"
    assert store.recall("fact") == []
