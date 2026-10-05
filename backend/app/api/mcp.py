"""Authenticated, tenant-metered HTTP transport for MCP read tools."""

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.api.deps import resolve_bearer_identity
from app.core.config import settings
from app.core.database import async_session
from app.core.exceptions import UnauthorizedError
from app.core.ratelimit import FixedWindowCounter
from app.services.mcp_server import SessionFactory, register_tools
from app.services.mcp_tools import identity_scope


def build_http_mcp(session_factory: SessionFactory = async_session) -> FastMCP:
    server = FastMCP(
        "prescripto",
        stateless_http=True,
        json_response=True,
        streamable_http_path="/",
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=[
                host.strip() for host in settings.mcp_allowed_hosts.split(",") if host.strip()
            ],
            allowed_origins=[],
        ),
    )
    register_tools(server, session_factory)
    return server


class McpAuthMiddleware:
    def __init__(self, app: ASGIApp, session_factory: SessionFactory = async_session) -> None:
        self.app = app
        self.session_factory = session_factory
        self.counter = FixedWindowCounter(settings.mcp_rate_limit_per_minute, 60)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        scheme, _, token = Headers(scope=scope).get("authorization", "").partition(" ")
        try:
            if scheme.lower() != "bearer" or not token.strip():
                raise UnauthorizedError("Not authenticated")
            identity = await resolve_bearer_identity(token.strip(), self.session_factory)
        except UnauthorizedError:
            await JSONResponse(
                {"detail": "Not authenticated"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )(scope, receive, send)
            return
        verdict = self.counter.hit(str(identity.tenant_id))
        if not verdict.allowed:
            await JSONResponse(
                {"detail": "Too many requests"},
                status_code=429,
                headers={"Retry-After": str(verdict.retry_after_seconds)},
            )(scope, receive, send)
            return
        if scope["path"] == "/mcp":
            scope = {**scope, "path": "/mcp/", "raw_path": b"/mcp/", "root_path": "/mcp"}
        with identity_scope(identity):
            await self.app(scope, receive, send)


def mcp_asgi_app(server: FastMCP, session_factory: SessionFactory = async_session) -> ASGIApp:
    return McpAuthMiddleware(server.streamable_http_app(), session_factory)
