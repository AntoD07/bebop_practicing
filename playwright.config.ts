import { defineConfig, devices } from "@playwright/test";

// Runs against a built app: `npm run build && npm run e2e` (the config starts
// `next start`), or set E2E_BASE_URL to test a deployment. The Python API must
// be reachable from the app (ENGINE_URL) and APP_PASSWORD / E2E_PASSWORD agree.
export default defineConfig({
  testDir: "e2e",
  timeout: 90_000,
  retries: 0,
  // the drill tests share ONE server-side session: never run projects concurrently
  workers: 1,
  fullyParallel: false,
  reporter: [["list"]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    trace: "retain-on-failure",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "phone", use: { ...devices["iPhone 13"], browserName: "chromium" } },
  ],
  webServer: process.env.E2E_BASE_URL
    ? undefined
    : { command: "npm run start", url: "http://localhost:3000/login", reuseExistingServer: true, timeout: 60_000 },
});
