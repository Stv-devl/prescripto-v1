# MCP server: read tools over `/mcp`

The backend exposes a [Model Context Protocol](https://modelcontextprotocol.io)
server at `/mcp`, built with the SDK's `FastMCP` and served over the
streamable HTTP transport (stateless, JSON responses). It offers two
read-only tools over the same project-scoped retrieval the chat uses. Nothing
in it writes data.

| File | Role |
| --- | --- |
| `backend/app/api/mcp.py` | HTTP transport, bearer auth middleware, rate limit, host protection |
| `backend/app/services/mcp_server.py` | `register_tools`: declares the two tools on any `FastMCP` instance |
| `backend/app/services/mcp_tools.py` | Tool logic: identity, project ownership, search, read |
| `backend/app/services/chat/tool_retry.py` | The agent's own use of the tools (in-memory session) |
| `backend/app/services/injection_guard.py` | Prompt-injection heuristics and context framing |

## The two tools

```
search_documents(project_id: str, query: str,
                 lot: str | None = None, doc_type: str | None = None)
    -> { passages: ToolPassage[] }

read_passage(project_id: str, point_id: str)
    -> { passage: ToolPassage | None }
```

- `project_id` and `point_id` are UUID strings; anything else is rejected as
  invalid input.
- `query` is trimmed, must not be empty and is capped at 500 characters;
  `lot` and `doc_type` are capped at 100 characters.
- `search_documents` returns at most 8 passages, from the same merged
  Qdrant search the chat pipeline uses (`search_merged`).
- `read_passage` returns the full passage for a point id (as returned by
  `search_documents`), or `null` when the point does not exist, belongs to
  another tenant, or belongs to another project.
- A `ToolPassage` is a search result that is always traceable to its Qdrant
  point: it carries `point_id`, the document and project ids, filename, page,
  position, lot/phase/type metadata, heading and section fields, the passage
  `text`, and a boolean `suspect` (see [Prompt-injection
  defences](#prompt-injection-defences)).
- Errors come back as MCP error results. A business exception
  (`AppException`) surfaces its own message; anything unexpected is logged by
  exception type only and the client sees `Internal error`.

## Two consumers, one implementation

`register_tools(server, session_factory)` is transport-agnostic: the caller
supplies how a tool obtains a database session. Two servers are built from it.

```mermaid
flowchart LR
    ext["External MCP client<br/>(Claude Desktop, Claude Code, Cursor...)"]
    ext -->|"HTTP + Bearer access token"| mw["McpAuthMiddleware"]
    mw -->|"identity_scope(tenant)"| http["FastMCP 'prescripto'<br/>/mcp"]
    graph["Chat graph<br/>retry_search_node"] -->|"in-memory session<br/>identity_scope(tenant, project)"| internal["FastMCP 'prescripto-internal'"]
    http --> tools["register_tools:<br/>search_documents, read_passage"]
    internal --> tools
    tools --> logic["mcp_tools.py<br/>ownership check + tenant filter"]
    logic --> pg[(Postgres)]
    logic --> qd[(Qdrant)]
```

**External clients** connect over HTTP to `/mcp` with a Prescripto JWT
access token (the same one the web client uses). The client chooses the
`project_id` of each call, among the projects of the token's tenant.

**The agent's retry** (`retry_search_node` in
`backend/app/services/chat/graph.py`) is used when the judge finds the first
retrieval insufficient and the retry has not run yet. It does not go over HTTP:
`create_connected_server_and_client_session` links an MCP client session to a
second, internal `FastMCP` server inside the process. The internal server
reuses the chat request's database session, and is built on first use rather
than at import. `retry_with_tools` (`tool_retry.py`) then runs one Mistral
tool-calling turn:

- The model receives the question and the judge's description of what was
  missing, framed as data, and the tool definitions listed by the session.
- `project_id` and `tenant_id` are stripped from the tool schemas it sees.
  Only whitelisted arguments are kept from each call (`query`, `lot`,
  `doc_type` for search; `point_id` for read), validated, and the
  conversation's `project_id` is injected server-side.
- At most 3 tool calls run (`TOOL_CALL_BUDGET`), one after another because the
  graph's tools share a single database session.
- The first invalid call (unknown tool, malformed arguments, overlong filter)
  or the first error result stops the remaining calls.
- Tool results are never fed back to the model; they are merged into the
  search results the answer is generated from. Logs carry ids only.
- If the retry fails, the first search results are served unchanged.

## Security model

**Identity comes from the transport, never from an argument.** The tool
schemas contain no `tenant_id`, and an extra `tenant_id` argument sent by a
caller never reaches another tenant (covered in
`tests/services/test_mcp_server.py`). The tenant is read from a `ContextVar`
(`identity_scope` / `current_identity` in `mcp_tools.py`) set by whoever opened
the session: `McpAuthMiddleware` for HTTP, the chat graph for the in-memory
session. A tool call with no identity set is refused.

**`/mcp` authentication.** `McpAuthMiddleware` requires an
`Authorization: Bearer <access token>` header and resolves it with
`resolve_bearer_identity` (`api/deps.py`): the token must be a valid, unexpired
`type: "access"` token whose `token_version` still matches the database, the
same checks as `get_current_user`. Anything else is a `401` with
`WWW-Authenticate: Bearer`. There is **no local dev bypass on `/mcp`**: with
`ENVIRONMENT=local`, a request without a token is still a `401`
(`test_mcp_in_local_environment_still_requires_a_token`). The middleware does
not use `get_current_user`, so the `dev_mode` fallback described in
[auth-and-tenancy.md](./auth-and-tenancy.md) never applies to it.

**Project scoping and ownership.** Every call goes through `_owned_project`,
which parses the UUID, then checks the project against the identity's tenant.
For the agent's session the identity also carries `allowed_project_id`: a call
for any other project is refused even within the same tenant. Unknown, foreign
and out-of-scope projects all raise the same `Project not found` message, so a
caller cannot probe which ids exist; the refusal is logged server-side with
ids. `read_passage` additionally checks that the retrieved point's
`project_id` matches the owned project.

**Tenant filter on every query.** Project lookup filters on `tenant_id`;
the Qdrant search carries `tenant_id` and `project_id` conditions, and the
point retrieval for `read_passage` is also tenant-filtered. Cross-tenant
search and read are tested over the in-memory session and over HTTP
(`test_mcp_tenant_a_cannot_read_tenant_b`).

**Rate limit.** Per tenant, a fixed-window counter
(`FixedWindowCounter`, `core/ratelimit.py`) allows
`MCP_RATE_LIMIT_PER_MINUTE` requests per minute (default 60). Past it, `429`
with `Retry-After`. The counter is in the memory of one process, like the auth
limiters.

**DNS-rebinding protection.** The SDK's transport security is enabled with an
allow-list from `MCP_ALLOWED_HOSTS` (comma-separated `Host` values, exact or
`host:*`; default `localhost:*,127.0.0.1:*`). Allowed origins are empty. A
request whose `Host` is not listed is rejected before reaching any tool; the
tests assert a `421` or `403` status. The middleware runs first, so an
unauthenticated request is a `401` whatever its `Host`.

## Prompt-injection defences

Retrieved passages are text written by third parties, so a trapped document can
contain sentences addressed to the model. Three layers apply; they reduce the
risk and do not claim to remove it.

1. **Framing.** In the `v1` retrieval mode the generation prompt appends
   `DATA_FRAMING_RULE` to the system message and wraps the context in
   `<documents>...</documents>` (`frame_context`, in `chat/graph.py`). The
   rule tells the model the content
   is quoted corpus material, never instructions, and not to follow, repeat or
   act on any it contains (role change, ignoring rules, revealing the prompt,
   calling a tool). Any `<documents>` tag inside a passage is escaped
   (`neutralise_tags`, also applied to unicode look-alike brackets and
   case/spacing variants) so a passage cannot close the frame. The retry prompt
   frames the judge's `manque` text the same way.
2. **Warning on suspect passages.** `frame_context` scans each passage of the
   context for injection-shaped sentences and, if any, appends a line naming
   the suspect passages (by their source header) and reminding the model they
   are citations.
3. **Ingestion flag.** When chunks are embedded
   (`services/ingestion/embedding.py`), `mark_suspect_points` sets
   `injection_suspect: true` in the Qdrant payload of suspect points only
   (absence means clean), with a set-payload operation that leaves vectors and
   other keys untouched. A backfill function flags points ingested before the
   check existed. Both tools set `ToolPassage.suspect` from this flag, or from a
   fresh heuristic check of the text.

Detection is a heuristic with no model call (`looks_like_injection`): text is
lowercased and stripped of accents and invisible format characters, then
matched against patterns for instruction-override phrasing (French and
English), role reassignment, references to the system prompt, requests to
call tools, the names of the two tools, frame-closing tags, and chat-template
control tokens.

What the tests pin down: framing and tag neutralisation
(`tests/services/test_injection_guard.py`), the flag being written only on
suspect points and the backfill being idempotent
(`tests/services/ingestion/test_injection_marking.py`), the `suspect` field on
a trapped passage (`test_mcp_tools.py`), and that the retry never forwards
`project_id` to the model, neutralises a closing `<manque>` tag, and stops at
the call budget or on the first invalid call (`test_tool_retry.py`).

## Connecting a client

The transport is mounted on both `/mcp` and `/mcp/` (`main.py` registers the
route and the mount; the middleware rewrites the bare path), so neither form
redirects.

Claude Code:

```bash
claude mcp add --transport http prescripto http://localhost:8000/mcp \
  --header "Authorization: Bearer <access token>"
```

Or, as a JSON entry (project `.mcp.json`):

```json
{
  "mcpServers": {
    "prescripto": {
      "type": "http",
      "url": "http://localhost:8000/mcp",
      "headers": { "Authorization": "Bearer <access token>" }
    }
  }
}
```

- The token is the `access_token` returned by `/auth/login`. Access tokens
  last 30 minutes (`JWT_ACCESS_TOKEN_EXPIRE_MINUTES`) and stop working
  immediately after a password change, so a client configuration needs a
  fresh token when it expires.
- Against a deployed instance, use its HTTPS API URL and add its public host to
  `MCP_ALLOWED_HOSTS`; the default only accepts localhost.
- The caller then sees only the projects of the token's tenant; `project_id`
  values come from `GET /projects`.
