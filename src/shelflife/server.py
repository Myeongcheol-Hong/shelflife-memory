"""MCP server exposing the Shelf Life tools over stdio (design 5.2)."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any, Literal

from mcp.server.context import CallNext, HandlerResult, ServerRequestContext
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import CallToolResult, TextContent

from shelflife.models import CheckMethod, Kind, Volatility
from shelflife.store import Store

RECALL_LIMIT = 10

# D2: the user gives the sentence. D3: remember only when asked; Claude may offer, showing
# the exact sentence, and waits for the user's confirmation of that sentence.
INSTRUCTIONS = """\
Shelf Life is a memory whose claims carry a source, the date they were observed and a
schedule for re-checking them. Call remember only when the user asks you to remember
something. You may offer ("Want me to remember this?") with the exact sentence you would
store, but never call remember until the user confirms; the user's yes approves that
sentence. Store the user's sentence as given, in their language. Call recall before
answering a question a remembered claim might cover, and say how old the claim is
(observed_at) when that matters. Nothing is re-checked automatically yet."""


def build_server(store: Store) -> MCPServer:
    """An MCPServer whose tools read and write `store`."""
    declared: dict[str, set[str]] = {}

    async def reject_unknown_arguments(
        ctx: ServerRequestContext[Any, Any], call_next: CallNext
    ) -> HandlerResult:
        # The SDK silently drops arguments a tool does not declare. A model that sends
        # status or next_check_at would then believe they were stored, so refuse instead.
        if ctx.method == "tools/call" and isinstance(ctx.params, dict):
            name = ctx.params.get("name")
            arguments = ctx.params.get("arguments") or {}
            # Malformed shapes fall through to the SDK's own validation.
            if isinstance(name, str) and name in declared and isinstance(arguments, dict):
                unknown = sorted(set(arguments) - declared[name])
                if unknown:
                    text = f"{name} does not accept: {', '.join(unknown)}"
                    content = [TextContent(type="text", text=text)]
                    return CallToolResult(content=content, is_error=True)
        return await call_next(ctx)

    server = MCPServer(
        "shelflife", instructions=INSTRUCTIONS, middleware=[reject_unknown_arguments]
    )

    def tool(fn: Callable[..., dict[str, Any]]) -> None:
        declared[fn.__name__] = set(inspect.signature(fn).parameters)
        server.add_tool(fn)

    @tool
    def remember(
        text: str,
        kind: Kind,
        subject: str | None = None,
        attribute: str | None = None,
        value: str | None = None,
        # "" is accepted too, because "leave it empty" can be read as an empty string.
        volatility: Volatility | Literal[""] | None = None,
        check_method: CheckMethod | Literal[""] | None = None,
        check_target: str | None = None,
        source_url: str | None = None,
        source_quote: str | None = None,
        observed_at: str | None = None,
        depends_on: list[str] | None = None,
    ) -> dict[str, Any]:
        """Store one claim in Shelf Life memory and return it with its id and next_check_at.

        Use only when the user asks you to remember something: a fact about the world
        (a price, a version, a policy), a decision, a preference or a note. You may offer
        ("Want me to remember this?") with the exact sentence you would store, but never
        call remember until the user confirms; the user's yes approves that sentence. Do
        not store guesses or whole conversations.

        - text: the user's sentence as given, in whatever language. Do not rewrite or
          translate it; only structure it into the other fields.
        - kind: world_fact, decision, preference or note.
        - subject, attribute, value: the structured form of a checkable fact, for example
          "AWS AIP-C01", "exam_fee", "$300".
        - volatility (fast, medium, slow, none) and check_method (pypi, github_release,
          web_page, none): leave both empty unless you are confident. Rules fill empty
          ones where they apply (a fact about the latest version or release, with the
          version as value and a PyPI project or GitHub repository page as source_url,
          gets a check_method; a price, or words such as version, policy or history,
          give the volatility), else a default; a value you give, check_target
          included, is never overwritten. Without a check_method, a
          world fact is stored as unverifiable and is not scheduled for checks yet.
        - check_target: the PyPI package, GitHub owner/repo or URL to check. Required
          when check_method is set.
        - source_url, source_quote: where the fact came from, and one line copied
          verbatim from that source.
        - observed_at: the date (YYYY-MM-DD) the fact was confirmed true. Defaults to today.
        - depends_on: decisions only. Ids of the claims the decision rests on; remember
          those first.
        """
        try:
            claim = store.remember(
                text,
                kind,
                subject=subject,
                attribute=attribute,
                value=value,
                volatility=volatility,
                check_method=check_method,
                check_target=check_target,
                source_url=source_url,
                source_quote=source_quote,
                observed_at=observed_at,
                depends_on=depends_on,
            )
        except ValueError as e:
            raise ToolError(str(e)) from e
        return claim.to_dict()

    @tool
    def recall(query: str) -> dict[str, Any]:
        """Search Shelf Life memory and return the best-matching claims, best first.

        Use before answering a question that a remembered fact or decision might cover.
        Do not use it to find what needs re-checking (use due).

        Search with 2-5 key words (names and nouns), not a full question, and leave
        particles off ("Chatbox 가격", not "Chatbox의 가격은"). Search for names in their
        original spelling (Hindsight, not 힌드사이트). Korean and English both work.

        In this version status is fresh or unverifiable (nothing can check the claim), and
        nothing re-checks claims or updates their status. A claim whose next_check_at is
        before today has not been checked since observed_at, so say how old it is.
        """
        return {"claims": [c.to_dict() for c in store.recall(query, limit=RECALL_LIMIT)]}

    @tool
    def due(days: int = 0) -> dict[str, Any]:
        """List claims whose next check date is today or earlier, or within `days` days.

        Use when the user asks what in their memory needs re-checking. Only claims with a
        check_method are listed; unverifiable claims never appear here. Do not use it to
        search for a topic (use recall). It checks and changes nothing.
        """
        try:
            claims = store.due(days)
        except ValueError as e:
            raise ToolError(str(e)) from e
        return {"claims": [c.to_dict() for c in claims]}

    return server
