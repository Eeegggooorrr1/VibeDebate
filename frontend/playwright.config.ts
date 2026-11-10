import { defineConfig } from "@playwright/test";
import { loadEnv } from "vite";
const local = loadEnv("development", "..", "");
const port = Number(process.env.E2E_PORT || 5173);
process.env.E2E_ADMIN_USERNAME ||= local.KEYCLOAK_ADMIN;
process.env.E2E_ADMIN_PASSWORD ||= local.KEYCLOAK_ADMIN_PASSWORD;
export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  use: { baseURL: `http://localhost:${port}`, trace: "retain-on-failure" },
  webServer: {
    command: `npm run dev -- --port ${port}`,
    url: `http://localhost:${port}`,
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
  projects: [{ name: "chromium", use: { browserName: "chromium" } }],
});
