import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/fullstack',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  forbidOnly: true,
  reporter: 'line',
  // Real OTP plus the complete staff CRUD/upload/publish workflow can span
  // several bounded service requests on a local emulated Docker runtime.
  timeout: 180_000,
  expect: { timeout: 15_000 },
  outputDir:
    process.env.CP_PLAYWRIGHT_OUTPUT ??
    '/private/tmp/clientproof-fullstack-results',
  // A genuine OTP is sensitive even in a disposable stack. Never record sessions.
  use: {
    baseURL: process.env.CP_FRONTEND_URL,
    trace: 'off',
    screenshot: 'off',
    video: 'off',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});
