import { expect, test } from "@playwright/test";
import { login } from "./helpers";

test("unauthenticated visitors are sent to /login and APIs get 401", async ({ page }) => {
  await page.goto("/connections");
  await expect(page).toHaveURL(/\/login\?next=%2Fconnections/);
  const r = await page.request.get("/api/engine/health");
  expect(r.status()).toBe(401);
});

test("wrong password is refused, the right one signs in and the cookie persists", async ({ page }) => {
  await page.goto("/login");
  await page.fill("input[type=password]", "definitely-not-it");
  await page.click("button[type=submit]");
  await expect(page.getByText("Wrong password.")).toBeVisible();
  await login(page);
  await expect(page).toHaveURL(/\/connections/);
  await page.reload();
  await expect(page).toHaveURL(/\/connections/);
  const r = await page.request.get("/api/engine/health");
  expect(r.ok()).toBeTruthy();
  expect((await r.json()).ok).toBe(true);
});
