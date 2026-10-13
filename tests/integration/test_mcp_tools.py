"""Call the tools through an in-process MCP client, the way Claude Desktop would."""

from datetime import timedelta

import pytest
from mcp import Client

from shelflife.server import build_server
from shelflife.store import OPTIONAL_FIELDS

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
    schema = tools["remember"].input_schema
    assert set(schema["required"]) == {"text", "kind"}
    assert set(schema["properties"]) == {"text", "kind", *OPTIONAL_FIELDS}
    assert "leave both empty unless you are confident" in tools["remember"].description
    # D3: remember only when asked; Claude may offer but must wait for confirmation.
    for text in (tools["remember"].description, client.instructions):
        text = " ".join(text.split())  # line wrapping is not part of the wording
        assert "only when the user asks" in text
        assert '("Want me to remember this?") with the exact sentence you would store' in text
        assert "never call remember until the user confirms" in text
        assert "the user's yes approves that sentence" in text
    # D2: the user's sentence is stored as given.
    remember = " ".join(tools["remember"].description.split())
    assert "Do not rewrite or translate it" in remember
    # D8: names are matched by substring, so they must be searched in their own spelling.
    recall = " ".join(tools["recall"].description.split())
    assert "original spelling (Hindsight, not 힌드사이트)" in recall
    assert "2-5 key words (names and nouns), not a full question" in recall
    assert '("Chatbox 가격", not "Chatbox의 가격은")' in recall


async def test_remember_passes_every_optional_field_through(client):
    given = {
        "subject": "mcp (PyPI)",
        "attribute": "latest_version",
        "value": "2.3.0",
        "volatility": "medium",
        "check_method": "pypi",
        "check_target": "mcp",
        "source_url": "https://pypi.org/project/mcp/",
        "source_quote": "mcp 2.3.0",
        "observed_at": "2026-10-01",
    }
    stored = await call(client, "remember", text="mcp is 2.3.0", kind="world_fact", **given)
    assert {k: stored[k] for k in given} == given


async def test_empty_strings_mean_not_given(client):
    stored = await call(
        client, "remember", text="A fact", kind="world_fact", volatility="", check_method=""
    )
    assert stored["volatility_source"] == stored["check_method_source"] == "default"


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
    assert stored["volatility_source"] == "rule"  # "latest version"
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


async def test_every_tool_refuses_unknown_arguments(client):
    for tool in (await client.list_tools()).tools:
        assert await call_error(client, tool.name, bogus=1) == f"{tool.name} does not accept: bogus"
