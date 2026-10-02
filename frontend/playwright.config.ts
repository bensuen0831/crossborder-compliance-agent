import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e', workers: 1, retries: 0,
  use: {
    baseURL: process.env.M0_FRONTEND_URL ?? 'http://127.0.0.1:5173',
    headless: true, viewport: { width: 1500, height: 1000 },
    launchOptions: process.env.M0_CHROMIUM_PATH ? { executablePath: process.env.M0_CHROMIUM_PATH, args: ['--no-sandbox'] } : undefined,
  },
  reporter: [['list'], ['json', { outputFile: 'test-results/results.json' }]],
});
