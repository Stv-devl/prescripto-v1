import { test, expect, type Page } from "@playwright/test";
import {
  mockBackend,
  mockProjectsListFailure,
  ASSISTANT_REPLY,
} from "./support/mock-backend";

async function login(page: Page): Promise<void> {
  await page.goto("/login");
  await page.locator("#email").fill("stevan@example.test");
  await page.locator("#password").fill("un-mot-de-passe");
  await page.getByRole("button", { name: "Se connecter" }).click();
}

test("connexion, sélection de projet et chat qui streame", async ({ page }) => {
  await mockBackend(page);
  await login(page);

  await expect(page).toHaveURL("/projects");
  await page.getByText("Chantier E2E").click();

  await expect(page).toHaveURL(/\/projects\/p-e2e-1$/);
  await page.getByRole("button", { name: "Chat" }).click();

  await page
    .getByPlaceholder("Posez une question sur vos documents…")
    .fill("Quelle est la nature du lot 03 ?");
  await page.getByRole("button", { name: "Envoyer" }).click();

  await expect(page.getByText(ASSISTANT_REPLY)).toBeVisible();
});

test("la liste de projets dit l'échec au lieu de rester vide en silence", async ({ page }) => {
  await mockBackend(page);
  await mockProjectsListFailure(page);
  await login(page);

  await expect(page).toHaveURL("/projects");
  await expect(page.getByRole("alert")).toBeVisible();
});
