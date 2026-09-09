import { render, screen } from "@testing-library/react";
import { RouterProvider, createMemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useAuthStore } from "@/lib/store/authStore";
import type { User } from "@/types/user";
import { AdminGuard } from "./AdminGuard";

let sessionIsPending = false;

vi.mock("@/providers/SessionProvider", () => ({
  useSession: (): { isPending: boolean; logout: () => void } => ({
    isPending: sessionIsPending,
    logout: () => {},
  }),
}));

const initialAuth = useAuthStore.getState();

function aUser(role: string): User {
  return {
    id: "user-1",
    email: "economiste@vinci.fr",
    role,
    tenant_id: "tenant-a",
    first_name: "Camille",
    last_name: "Roux",
    tenant_name: "Groupe Vinci",
    tenant_plan: "pro",
    created_at: "2026-01-15T09:00:00Z",
  };
}

function renderGuard() {
  const router = createMemoryRouter(
    [
      {
        element: <AdminGuard />,
        children: [
          { path: "/admin/chunks", element: <div>console des chunks</div> },
        ],
      },
      { path: "/projects", element: <div>liste des projets</div> },
    ],
    { initialEntries: ["/admin/chunks"] },
  );

  return render(<RouterProvider router={router} />);
}

describe("AdminGuard", () => {
  beforeEach(() => {
    useAuthStore.setState(initialAuth, true);
    sessionIsPending = false;
  });

  it("waits instead of redirecting while the session is still loading", () => {
    // The reload case. `user` is not persisted — only the two tokens are — so
    // it is null until /auth/me answers. A guard reading the role first would
    // eject the operator on every refresh.
    sessionIsPending = true;
    useAuthStore.setState({ user: null, isAuthenticated: true });

    const { container } = renderGuard();

    // The spinner itself, not just the absence of the other two: a guard
    // returning null while pending would satisfy the absences and render
    // nothing at all.
    expect(container.querySelector("svg")).not.toBeNull();
    expect(screen.queryByText("liste des projets")).not.toBeInTheDocument();
    expect(screen.queryByText("console des chunks")).not.toBeInTheDocument();
  });

  it("redirects rather than hanging when the session query is disabled", () => {
    // The query is `enabled: isAuthenticated`, and a disabled React Query stays
    // pending forever. Branching on isPending alone would render the loading
    // screen for good wherever this guard is mounted outside AuthGuard.
    sessionIsPending = true;
    useAuthStore.setState({ user: null, isAuthenticated: false });

    renderGuard();

    expect(screen.getByText("liste des projets")).toBeInTheDocument();
  });

  it("renders the admin route for an admin", () => {
    useAuthStore.setState({ user: aUser("admin") });

    renderGuard();

    expect(screen.getByText("console des chunks")).toBeInTheDocument();
  });

  it("redirects a non-admin to the projects list", () => {
    useAuthStore.setState({ user: aUser("owner") });

    renderGuard();

    expect(screen.getByText("liste des projets")).toBeInTheDocument();
  });

  it("redirects when the session loaded but carries no user", () => {
    // /auth/me failed: isPending is false and user stayed null. Rendering the
    // loading screen here would hang the page forever.
    useAuthStore.setState({ user: null });

    renderGuard();

    expect(screen.getByText("liste des projets")).toBeInTheDocument();
  });
});
