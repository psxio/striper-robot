import { defineConfig } from '@playwright/test';

const port = Number(process.env.PLAYWRIGHT_PORT || process.env.PORT || '8111');
const baseUrl = `http://127.0.0.1:${port}`;

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [
    ['html', { outputFolder: 'playwright-report' }],
    ['list'],
  ],
  use: {
    baseURL: baseUrl,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: { browserName: 'chromium' },
    },
  ],
  webServer: {
    command: `python scripts/run_backend.py --host 0.0.0.0 --strict-port --start-port ${port}`,
    url: `${baseUrl}/api/health`,
    reuseExistingServer: false,
    timeout: 30000,
  },
});
