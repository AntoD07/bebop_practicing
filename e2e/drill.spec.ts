import { expect, test } from "@playwright/test";
import { login } from "./helpers";

test("the drill starts, steps with the keyboard, survives a reload paused at the same item", async ({ page, isMobile }) => {
  await login(page);
  await page.request.delete("/api/drill/connections");
  await page.evaluate(() => localStorage.removeItem("bebop.drill"));
  await page.goto("/connections");
  if (isMobile) await page.getByRole("tab", { name: "Drill" }).click();
  const start = page.getByRole("button", { name: /Start exercise/ }).first();
  await expect(start).toBeVisible({ timeout: 30_000 });
  await expect(start).toBeEnabled({ timeout: 60_000 });
  await start.click();
  // the panel exists twice in the DOM (desktop column / phone sheet): match the visible one
  const visible = (text: string | RegExp) => page.getByText(text, { exact: typeof text === "string" }).filter({ visible: true }).first();
  // on the phone the running drill is a mini bar; the status badge is in the expanded sheet
  const expand = async () => {
    const b = page.getByRole("button", { name: "Expand" });
    if (await b.isVisible().catch(() => false)) await b.click();
  };
  await expand();
  await expect(visible("running")).toBeVisible();
  await expect(visible(/#1\/\d+/)).toBeVisible();
  await expect(page.locator("svg[aria-label='guitar tab']").filter({ visible: true }).first()).toBeVisible({ timeout: 20_000 });

  await page.keyboard.press("ArrowRight");
  await expect(visible(/#2\/\d+/)).toBeVisible();

  await page.reload();
  await expect(visible(/#2\/\d+/)).toBeVisible({ timeout: 20_000 });
  await expand();
  await expect(visible("paused")).toBeVisible({ timeout: 20_000 });
  await expect(visible(/#2\/\d+/)).toBeVisible();

  // the server holds the same session for the other device
  const srv = await (await page.request.get("/api/drill/connections")).json();
  expect(srv.exists).toBe(true);
  expect(srv.state.currentIndex).toBe(1);

  await page.keyboard.press(" ");
  await expect(visible("running")).toBeVisible();
});
