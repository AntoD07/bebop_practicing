import { expect, type Page } from "@playwright/test";

export const PASSWORD = process.env.E2E_PASSWORD ?? "bebop";

export async function login(page: Page) {
  await page.goto("/login");
  await page.fill("input[type=password]", PASSWORD);
  await page.click("button[type=submit]");
  await expect(page).not.toHaveURL(/\/login/);
}
