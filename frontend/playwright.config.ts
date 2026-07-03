import { defineConfig, devices } from '@playwright/test'

// E2E targets the LIVE single-origin app: FastAPI serves the static export at
// http://localhost:8001/app/. The qa-auditor starts the backend
// (`uv run python -m src`) with the frontend built into `frontend/out/` before
// running these tests — this config does NOT spin up a webServer itself.
const BASE_URL = process.env.E2E_BASE_URL ?? 'http://localhost:8001/app/'

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 90_000,
  expect: { timeout: 45_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: BASE_URL,
    trace: 'on-first-retry',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
})
