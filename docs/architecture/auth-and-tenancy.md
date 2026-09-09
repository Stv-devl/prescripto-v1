# Authentication & multi-tenant isolation

Prescripto is multi-tenant: one tenant per construction cost consultancy
(*cabinet d'économie de la construction*). There is no database-level tenant
isolation (no Postgres RLS, no Qdrant guard rail) — every table and every
vector query is filtered by `tenant_id` in application code. This is the
single most important invariant in the codebase: a missing filter is a
silent cross-tenant data leak, not an error.

## JWT

Home-grown JWT auth (`backend/app/core/auth.py`) — no third-party auth
service.

- Algorithm: HS256.
- Access token: 30 minutes. Refresh token: 7 days. Password-reset token: 30
  minutes.
- Passwords are hashed with bcrypt (`bcrypt.hashpw` / `bcrypt.checkpw`).
- Every token carries `sub` (user id), `tenant_id`, `type`
  (`access` / `refresh` / `reset`), and — for access/refresh — a
  `token_version` used to invalidate all of a user's tokens at once (e.g. on
  password change) without a revocation list.

```python
# backend/app/core/auth.py
{
    "sub": str(user_id),
    "tenant_id": str(tenant_id),
    "exp": expire_datetime,
    "type": "access",
    "token_version": int,
}
```

`get_current_user` (`backend/app/api/deps.py`) decodes the bearer token,
rejects anything that isn't a `type: "access"` token, and re-checks
`token_version` against the database on every request — one extra `SELECT`
per authenticated call, in exchange for instant token revocation.

## Auth endpoints

All under `/auth`, in `backend/app/api/auth.py`:

| Endpoint | Method | Auth | Rate limit |
| --- | --- | --- | --- |
| `/auth/signup` | POST | public | 10/min |
| `/auth/login` | POST | public | 10/min |
| `/auth/refresh` | POST | token in body | — |
| `/auth/me` | GET / PUT | `get_current_user` | — |
| `/auth/change-password` | POST | `get_current_user` | — |
| `/auth/forgot-password` | POST | public | 10/15min |
| `/auth/reset-password` | POST | token in body | 10/15min |

## Tenant isolation, enforced by hand

Every list/count query filters by `tenant_id`; every single-row fetch
distinguishes "doesn't exist" (404) from "exists but belongs to another
tenant" (403) instead of leaking the distinction:

```python
# backend/app/services/project.py
select(Project).where(Project.tenant_id == tenant_id).order_by(...)
```

```python
# backend/app/services/document.py
select(Folder).join(Project).where(
    Folder.id == folder_id, Project.tenant_id == tenant_id
)
```

The same discipline applies to every Qdrant call — search, scroll, and
count all carry `tenant_id` as a mandatory `FieldCondition`:

```python
# backend/app/services/search.py
Filter(must=[
    FieldCondition(key="tenant_id", match=MatchValue(value=str(tenant_id))),
    FieldCondition(key="project_id", match=MatchValue(value=str(project_id))),
])
```

`TenantMixin` (`backend/app/core/database.py`) is what every tenant-scoped
model inherits from — it adds an indexed, cascading foreign key, not just a
column:

```python
class TenantMixin:
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
```

## The local-only dev bypass

Local development skips login entirely — no JWT to mint or carry around
while iterating on the UI. It is gated by a single property, off by default:

```python
# backend/app/core/config.py
environment: Literal["local", "staging", "production"] = "production"

@property
def dev_mode(self) -> bool:
    return self.environment == "local"
```

When `dev_mode` is true, the app seeds a deterministic dev tenant/user pair
at startup (`_seed_dev_data` in `main.py`) and `get_current_user` falls back
to that pair only when **both** `dev_mode` is on and no bearer token was
sent:

```python
# backend/app/api/deps.py
bearer_scheme = HTTPBearer(auto_error=not settings.dev_mode)

if credentials is None and settings.dev_mode and _dev_user_id and _dev_tenant_id:
    return {"user_id": _dev_user_id, "tenant_id": _dev_tenant_id}
if credentials is None:
    raise HTTPException(status_code=401, detail="Not authenticated")
```

The default (`environment = "production"`) makes `auto_error` `True` and the
bypass branch unreachable — a deployment has to explicitly opt in with
`ENVIRONMENT=local` to lose the auth requirement.
