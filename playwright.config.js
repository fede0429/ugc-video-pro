const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests/e2e',
  timeout: 60000,
  use: {
    baseURL: process.env.ANIMATION_E2E_BASE_URL || 'http://127.0.0.1:8000',
    headless: true,
    trace: 'on-first-retry',
  },
});
