"""Call the tools through an in-process MCP client, the way Claude Desktop would."""

from datetime import timedelta
from pathlib import Path

import pytest
from mcp import Client

from shelflife.server import build_server
from shelflife.store import OPTIONAL_FIELDS
from shelflife.verifiers import FetchError

FIXTURES = Path(__file__).parents[1] / "fixtures"
PYPI_MCP = "https://pypi.org/pypi/mcp/json"
GITHUB_GRAPHITI = "https://api.github.com/repos/getzep/graphiti/releases/latest"

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def routes():
    """URL -> fixture file (or an exception) for the fetches verify makes."""
    return {}


@pytest.fixture
async def client(store, routes):
    def fetch(url, headers):
        route = routes.get(url, FetchError(f"no route for {url}"))
        if isinstance(route, Exception):
            raise route
        return (FIXTURES / route).read_bytes()

    async with Client(build_server(store, fetch=fetch)) as c:
        yield c


async def call(client, tool, **arguments):
    result = await client.call_tool(tool, arguments)
    assert not result.is_error, result.content[0].text
    return result.structured_content


async def call_error(client, tool, **arguments) -> str:
    result = await client.call_tool(tool, arguments)
    assert result.is_error
    return result.content[0].text


async def test_lists_the_tools(client):
    tools = {t.name: t for t in (await client.list_tools()).tools}
    assert set(tools) == {"remember", "recall", "due", "verify", "forget"}
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
    # D9 with D3: a check never changes the stored value; adopting a new value is the
    # user's call, through remember and forget.
    verify = " ".join(tools["verify"].description.split())
    assert "The claim keeps the value it was stored with" in verify
    for text in (verify, " ".join(tools["due"].description.split())):
        assert "the user asks you to remember the new sentence and forget this claim" in text
    forget = " ".join(tools["forget"].description.split())
    assert "Use only when the user asks to forget a claim" in forget


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

    assert (await call(client, "due"))["due"] == []
    assert [c["id"] for c in (await call(client, "due", days=7))["due"]] == [stored["id"]]
    clock.now += timedelta(days=7)
    assert [c["id"] for c in (await call(client, "due"))["due"]] == [stored["id"]]


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


# --- verify (D9) ----------------------------------------------------------------------


async def remember_version(client, **fields):
    given = {"kind": "world_fact", "observed_at": "2026-10-01", "volatility": "fast"} | fields
    return await call(client, "remember", text="A latest version", **given)


async def test_verify_records_a_same_check_and_reschedules(client, routes):
    routes[PYPI_MCP] = "pypi/mcp.json"
    claim = await remember_version(client, check_method="pypi", check_target="mcp", value="2.3.0")

    verified = await call(client, "verify", claim_id=claim["id"])
    assert verified["check"] == {
        "result": "same",
        "old_value": "2.3.0",
        "new_value": "2.3.0",
        "evidence": "2.3.0",
        "checked_at": "2026-10-12T09:30:00+00:00",
    }
    assert verified["claim"]["status"] == "fresh"
    assert verified["claim"]["last_checked_at"] == "2026-10-12T09:30:00+00:00"
    assert verified["claim"]["next_check_at"] == "2026-10-19"
    assert (await call(client, "due"))["due"] == []


async def test_verify_reports_a_change_and_keeps_the_value(client, routes):
    routes[GITHUB_GRAPHITI] = "github/getzep__graphiti.json"
    claim = await remember_version(
        client, check_method="github_release", check_target="getzep/graphiti", value="v0.30.1"
    )

    verified = await call(client, "verify", claim_id=claim["id"])
    check = verified["check"]
    assert (check["result"], check["old_value"], check["new_value"]) == (
        "changed",
        "v0.30.1",
        "v0.30.2",
    )
    assert (verified["claim"]["status"], verified["claim"]["value"]) == ("changed", "v0.30.1")


async def test_verify_error_keeps_the_claim_due(client, routes):
    routes[PYPI_MCP] = FetchError(f"HTTP 503 from {PYPI_MCP}")
    claim = await remember_version(client, check_method="pypi", check_target="mcp", value="2.3.0")

    verified = await call(client, "verify", claim_id=claim["id"])
    assert verified["check"]["result"] == "error"
    assert verified["check"]["evidence"] == f"HTTP 503 from {PYPI_MCP}"
    assert verified["claim"]["next_check_at"] == "2026-10-08"
    [item] = (await call(client, "due"))["due"]
    assert (item["id"], item["last_check"]) == (claim["id"], verified["check"])


async def test_verify_refuses_claims_it_cannot_check(client):
    page = await remember_version(
        client, check_method="web_page", check_target="https://example.com/pricing"
    )
    unverifiable = await call(client, "remember", text="Seoul has 25 districts", kind="world_fact")
    assert "verify cannot check it yet" in await call_error(client, "verify", claim_id=page["id"])
    assert "has no check_method" in await call_error(client, "verify", claim_id=unverifiable["id"])
    assert "no claim with id 'nope'" in await call_error(client, "verify", claim_id="nope")
    no_value = await remember_version(client, check_method="pypi", check_target="mcp")
    message = await call_error(client, "verify", claim_id=no_value["id"])
    assert "has no value to compare with the source" in message


async def test_due_returns_three_lists(client, routes):
    routes[GITHUB_GRAPHITI] = "github/getzep__graphiti.json"
    changed = await remember_version(
        client, check_method="github_release", check_target="getzep/graphiti", value="v0.30.1"
    )
    never_checked = await remember_version(client, check_method="pypi", check_target="mcp")
    unverifiable = await call(client, "remember", text="Seoul has 25 districts", kind="world_fact")
    verified = await call(client, "verify", claim_id=changed["id"])

    listed = await call(client, "due", days=7)
    assert set(listed) == {"due", "changed", "needs_check_method"}
    assert [(c["id"], c["last_check"]) for c in listed["due"]] == [
        (never_checked["id"], None),
        (changed["id"], verified["check"]),  # next check 10-19, within 7 days
    ]
    assert [(c["id"], c["change"]) for c in listed["changed"]] == [
        (changed["id"], verified["check"])
    ]
    assert [c["id"] for c in listed["needs_check_method"]] == [unverifiable["id"]]


async def test_a_changed_claim_keeps_its_change_after_a_failed_check(client, routes, clock):
    routes[GITHUB_GRAPHITI] = "github/getzep__graphiti.json"
    claim = await remember_version(
        client, check_method="github_release", check_target="getzep/graphiti", value="v0.30.1"
    )
    change = (await call(client, "verify", claim_id=claim["id"]))["check"]
    clock.now += timedelta(days=7)
    routes[GITHUB_GRAPHITI] = FetchError("HTTP 503")
    failed = (await call(client, "verify", claim_id=claim["id"]))["check"]

    listed = await call(client, "due")
    [item] = listed["changed"]
    assert (item["status"], item["change"]["new_value"]) == ("changed", "v0.30.2")
    assert item["change"] == change
    [item] = listed["due"]
    assert item["last_check"] == failed  # the failure shows under due


async def test_forget_retires_a_claim(client):
    claim = await call(client, "remember", text="Chatbox Pro costs $19.99", kind="world_fact")
    forgotten = await call(client, "forget", claim_id=claim["id"])
    assert forgotten["claim"]["id"] == claim["id"]
    assert forgotten["claim"]["status"] == "retired"
    assert (await call(client, "recall", query="Chatbox"))["claims"] == []
    assert (await call(client, "due"))["needs_check_method"] == []
    assert (await call(client, "forget", claim_id=claim["id"]))["claim"] == forgotten["claim"]
    assert "no claim with id 'nope'" in await call_error(client, "forget", claim_id="nope")
    assert "is retired" in await call_error(client, "verify", claim_id=claim["id"])
