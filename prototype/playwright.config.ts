import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests',
  timeout: 20_000,
  // The target machine keeps roughly 16GB RAM free. Ten parallel Chromium
  // workers can cross that budget and make acceptance results non-repeatable.
  workers: 4,
  use: {
    baseURL: 'http://127.0.0.1:4173',
    channel: process.platform === 'win32' ? 'msedge' : undefined,
    viewport: { width: 1440, height: 900 },
  },
  webServer: {
    command: 'node ./node_modules/vite/bin/vite.js --host 127.0.0.1 --port 4173',
    url: 'http://127.0.0.1:4173',
    reuseExistingServer: true,
  },
})
