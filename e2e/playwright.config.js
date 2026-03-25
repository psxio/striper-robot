// @ts-check
const { defineConfig } = require("@playwright/test");

module.exports = defineConfig({
  testDir: "./tests",
  timeout: 30000,
  retries: 1,
  workers: 1, // Sequential — tests share database state
  use: {
    baseURL: process.env.E2E_BASE_URL || "http://localhost:8111",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  webServer: {
    command: "cd .. && python -m uvicorn backend.main:app --port 8111",
    port: 8111,
    timeout: 15000,
    reuseExistingServer: true,
    env: {
      ENV: "dev",
      DATABASE_PATH: "backend/data/e2e_test.db",
    },
  },
  projects: [
    {
      name: "chromium",
      use: { browserName: "chromium" },
    },
  ],
});
