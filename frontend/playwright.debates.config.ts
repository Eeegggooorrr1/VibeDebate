import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests",
  workers: 1,
  use: { baseURL: "http://127.0.0.1:5175" },
  webServer: {
    command: "npx vite --host 127.0.0.1 --port 5175",
    url: "http://127.0.0.1:5175",
    reuseExistingServer: true,
  },
  projects: [{ name: "chromium", use: { browserName: "chromium" } }],
});
