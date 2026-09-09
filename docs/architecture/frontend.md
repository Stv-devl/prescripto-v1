# Frontend architecture

React 19 + TypeScript (strict) + Vite, organized as feature slices under
`client/src/features/`. Each feature owns its types, `*.service.ts` (the
only files allowed to call the fetch client), hooks, and UI.

| Feature | Owns |
| --- | --- |
| `auth` | login, signup, refresh, profile — `/auth/*` |
| `projects` | project/folder/document CRUD, upload with progress |
| `chat` | SSE-streamed conversations, per-project |
| `summary` | SSE-streamed structured project summary |
| `admin` | chunk inspection, semantic search, deduplication, re-chunking |
| `settings` | profile, password change |
| `landing` | static marketing content, no service layer |

## Data flow

`Page → components → hooks → service → apiClient`. Server state lives in
TanStack Query, never mirrored into Zustand or component state:

```typescript
// client/src/features/projects/hooks/projectHooks.ts
export function useProjects() {
  return useQuery({
    queryKey: ["projects"],
    queryFn: async () => unwrap(await listProjects()),
  });
}

export function useCreateProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: CreateProjectInput) => unwrap(await createProject(data)),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["projects"] }),
  });
}
```

Zustand is reserved for client-owned UI state — e.g. the chunk browser's
view mode and filters — never for data the server owns.

## Chat streaming

`fetchSSE` (`client/src/lib/apiClient.ts`) opens the stream; the chat hook
accumulates incoming tokens in **local component state** while the stream is
open, and only touches the Query cache once, to invalidate it, after the
stream closes:

```typescript
// client/src/features/chat/hooks/hooks.ts
const [messages, setMessages] = useState<StreamingMessage[]>([]);
// ...
setMessages((prev) => amendAssistant(prev, (last) => ({
  ...last,
  content: last.content + fragment,
})));
// stream ends:
queryClient.invalidateQueries({ queryKey: ["conversations", projectId] });
```

This is the one deliberate exception to "server data only lives in Query":
tokens are transient render state until the backend has actually persisted
the message, at which point the source of truth becomes the refetched
conversation.

## API client

`client/src/lib/apiClient.ts` centralizes JWT attachment, a 30s timeout with
abort, and 401 handling in one place — `apiGet/Post/Put/Patch/Delete` plus
`fetchSSE` for streaming, all typed generics:

```typescript
function authHeaders(): Record<string, string> {
  const token = useAuthStore.getState().accessToken;
  const h: Record<string, string> = { "Content-Type": "application/json" };
  if (token) h["Authorization"] = `Bearer ${token}`;
  return h;
}
```

## Routing & providers

`client/src/routes/router.tsx` splits routes into three tiers: public
(`/`, `/login`, `/signup`, `/forgot-password`, `/reset-password`, static
legal pages), authenticated (`/projects`, `/projects/:projectId`,
`/settings`, guarded by `SessionProvider` + `AuthGuard`), and admin
(`/admin/chunks`, additionally guarded by `AdminGuard`).

`AppProviders` composes the app around `QueryClientProvider`; session and
auth guarding happen further down the tree, in the router itself.

## Shared schemas — current state

`shared/schemas/` is the intended home for Zod contracts shared between
client and backend, but it's empty today: the schemas that exist
(`chat.schema.ts`, `summary.schema.ts` — the SSE event shapes) are
feature-local, under `client/src/features/*/services/`. Backend/frontend
transport shapes are currently kept in sync by convention rather than a
shared, generated contract.
