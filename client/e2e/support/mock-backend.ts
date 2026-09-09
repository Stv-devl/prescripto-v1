import type { Page } from "@playwright/test";

export const PROJECT_ID = "p-e2e-1";

export const ASSISTANT_REPLY =
  "Le lot 03 couvre l'isolation thermique par l'intérieur.";

export const user = {
  id: "u-e2e-1",
  email: "stevan@example.test",
  role: "user",
  tenant_id: "t-e2e-1",
  first_name: "Stevan",
  last_name: null,
  tenant_name: "Chantier E2E",
  tenant_plan: "pro",
  created_at: "2026-01-01T00:00:00Z",
};

export const project = {
  id: PROJECT_ID,
  tenant_id: "t-e2e-1",
  name: "Chantier E2E",
  phase: "conception",
  status: "active",
  address: "1 rue du Test",
  client: "Client E2E",
  architect: "",
  architect_address: "",
  bureau_thermique: "",
  bureau_thermique_address: "",
  bureau_vrd: "",
  bureau_vrd_address: "",
  bureau_beton: "",
  bureau_beton_address: "",
  economiste: "",
  economiste_address: "",
  controleur_technique: "",
  controleur_technique_address: "",
  is_favorite: false,
  document_count: 0,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const tokens = {
  access_token: "e2e-token",
  refresh_token: "e2e-refresh",
  token_type: "bearer",
};

function sseBody(): string {
  return [
    `data: ${JSON.stringify({ conversation_id: "conv-e2e-1" })}`,
    `data: ${JSON.stringify({ text: ASSISTANT_REPLY })}`,
    `data: [DONE]`,
    "",
  ].join("\n");
}

/**
 * Wires every `/api/**` route the connexion → project → streaming-chat
 * journey touches, with no real backend involved.
 */
export async function mockBackend(page: Page): Promise<void> {
  await page.route("**/api/auth/login", (route) =>
    route.fulfill({ json: tokens }),
  );
  await page.route("**/api/auth/me", (route) => route.fulfill({ json: user }));
  await page.route("**/api/projects", (route) =>
    route.fulfill({ json: { projects: [project], total: 1 } }),
  );
  await page.route(`**/api/projects/${PROJECT_ID}`, (route) =>
    route.fulfill({ json: project }),
  );
  await page.route(`**/api/projects/${PROJECT_ID}/documents`, (route) =>
    route.fulfill({ json: { documents: [], total: 0 } }),
  );
  await page.route(`**/api/projects/${PROJECT_ID}/folders`, (route) =>
    route.fulfill({ json: { folders: [], total: 0 } }),
  );
  await page.route(`**/api/projects/${PROJECT_ID}/conversations`, (route) =>
    route.fulfill({ json: { conversations: [], total: 0 } }),
  );
  await page.route(`**/api/projects/${PROJECT_ID}/chat`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: sseBody(),
    }),
  );
  await page.route("**/api/conversations/*/messages", (route) =>
    route.fulfill({ json: [] }),
  );
}

/** Overrides the projects list with a failure — must be called after `mockBackend`. */
export async function mockProjectsListFailure(page: Page): Promise<void> {
  await page.route("**/api/projects", (route) =>
    route.fulfill({ status: 500, json: { detail: "server_error" } }),
  );
}
