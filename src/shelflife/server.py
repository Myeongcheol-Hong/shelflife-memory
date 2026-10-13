"""MCP server exposing the Shelf Life tools over stdio (design 5.2)."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any, Literal

from mcp.server.context import CallNext, HandlerResult, ServerRequestContext
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import CallToolResult, TextContent

from shelflife.models import CheckMethod, CheckResult, Claim, Kind, Volatility
from shelflife.store import Store
from shelflife.verifiers import Fetch, http_get, verifier_for

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
(observed_at) when that matters. Claims are checked against their source only when you
call verify; nothing is re-checked automatically yet."""


def build_server(store: Store, fetch: Fetch = http_get) -> MCPServer:
    """An MCPServer whose tools read and write `store`; verify fetches through `fetch`."""
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
          web_page, none): leave both empty unless you are confident. For a world fact,
          rules fill empty ones where they apply (an attribute such as latest_version or
          release, with the version as value and a PyPI project or GitHub repository page
          as source_url, gets a check_method; a price, or words such as version, policy or
          history, give the volatility), else a default; a value you give, check_target
          included, is never overwritten. Without a check_method, a world fact is stored
          as unverifiable and is not scheduled for checks yet.
        - check_target: the PyPI package, GitHub owner/repo or URL to check. Required
          when check_method is set; pypi and github_release also need the version as
          value.
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

        status is fresh, unverifiable (nothing can check the claim) or changed (a check
        found a different value at the source; the claim keeps the value it was stored
        with, so tell the user; due shows the value found). Claims are
        checked only when verify is called. A claim with a check_method whose
        next_check_at is today or earlier is due: say how old it is (observed_at,
        last_checked_at).
        """
        return {"claims": [c.to_dict() for c in store.recall(query, limit=RECALL_LIMIT)]}

    @tool
    def due(days: int = 0) -> dict[str, Any]:
        """List what in memory needs attention, in three lists (D9).

        - due: claims whose next check date is today or earlier, or within `days` days.
          Each has last_check, the result of its latest check (null if never checked),
          so a source that keeps failing is visible.
        - changed: claims a check found changed. Each has change, the check that found
          the different value (change.new_value), even if a later check failed. The claim
          keeps the value it was stored with; to adopt the new value, the user asks you
          to remember the new sentence and forget this claim. A changed claim is also
          under due once its next check is due.
        - needs_check_method: world facts that nothing can check, because they have no
          check_method. They are never due.

        Use when the user asks what in their memory needs re-checking. Do not use it to
        search for a topic (use recall). It checks and changes nothing; verify checks a
        claim.
        """
        try:
            due_claims = store.due(days)
        except ValueError as e:
            raise ToolError(str(e)) from e

        def with_check(claim: Claim, key: str, result: CheckResult | None) -> dict[str, Any]:
            check = store.last_check(claim.id, result)
            return claim.to_dict() | {key: check.to_dict() if check else None}

        return {
            "due": [with_check(c, "last_check", None) for c in due_claims],
            "changed": [with_check(c, "change", CheckResult.CHANGED) for c in store.changed()],
            "needs_check_method": [c.to_dict() for c in store.needs_check_method()],
        }

    @tool
    def verify(claim_id: str) -> dict[str, Any]:
        """Check one claim against its source now, record the check and return both.

        Use when the user asks whether a remembered fact is still true, or to check a
        claim that due lists. Works for claims whose check_method is pypi or
        github_release and that have a value; web_page claims cannot be checked this way
        yet.

        check.result is same (the source still gives the claim's value), changed (the
        source gives new_value), cannot_tell, or error (evidence says why). The claim keeps
        the value it was stored with: after changed its status is changed, and to adopt
        new_value the user asks you to remember the new sentence and forget this claim.
        After cannot_tell or error the claim keeps its next_check_at, so a due claim stays
        due and is tried again; the third such result in a row moves the next check out
        by one class interval (see claim.next_check_at). Tell the user either way.
        """
        try:
            claim = store.checkable(claim_id)
            verifier = verifier_for(claim.check_method)
            if verifier is None:
                raise ValueError(
                    f"claim {claim_id!r} is a web_page claim; verify cannot check it yet"
                )
            if claim.value is None:
                raise ValueError(f"claim {claim_id!r} has no value to compare with the source")
            outcome = verifier(claim.check_target or "", claim.value, fetch)
            claim, check = store.add_check(
                claim.id, outcome.result, outcome.new_value, outcome.evidence
            )
        except ValueError as e:
            raise ToolError(str(e)) from e
        return {"claim": claim.to_dict(), "check": check.to_dict()}

    @tool
    def forget(claim_id: str) -> dict[str, Any]:
        """Retire a claim: recall and due no longer show it. Nothing is deleted.

        Use only when the user asks to forget a claim, for example after verify found a
        new value and the user had you remember the new sentence. Forgetting a claim that
        is already retired is not an error.
        """
        try:
            claim = store.forget(claim_id)
        except ValueError as e:
            raise ToolError(str(e)) from e
        return {"claim": claim.to_dict()}

    return server
