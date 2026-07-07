import { test, expect } from '@playwright/test'
import { join } from 'node:path'

// Phase-2 E2E against the LIVE single-origin app.
//
// ASSUMPTION: the backend is already running with the frontend built into
// `frontend/out/`, served at the base URL (default :8001/app/, overridable via
// E2E_BASE_URL so the qa-auditor can point at a non-8001 port). Real Google
// Gemini key from `.env` — asserts on REAL profile + answer content.
//
// Journey: upload a CSV -> profile card renders with real content -> ask a
// question -> answer renders -> the history sidebar lists the session.

const CSV_FIXTURE = join(__dirname, 'fixtures', 'sales.csv')

test('upload shows a real profile, answer renders, and history lists the session', async ({
  page,
}) => {
  await page.goto('/app/')

  await expect(page.getByRole('heading', { name: 'Data Analysis Agent' })).toBeVisible()

  // 1. Upload a CSV.
  await page.getByTestId('file-input').setInputFiles(CSV_FIXTURE)
  await expect(page.getByText('sales.csv').first()).toBeVisible({ timeout: 30_000 })

  // 2. The real profile card renders with real content: a known column name
  //    and a row/column/quality figure (not a raw JSON dump).
  const profile = page.getByTestId('profile-card').first()
  await expect(profile).toBeVisible({ timeout: 30_000 })
  await expect(profile).toContainText('region')
  await expect(profile).toContainText(/rows|columns/i)

  // 3. Ask a question and get a real answer.
  await page
    .getByLabel('Ask a question about your data')
    .fill('What is the average order value by region?')
  await page.getByRole('button', { name: 'Ask' }).click()

  const answer = page.getByTestId('answer-pane')
  await expect(answer).toBeVisible({ timeout: 60_000 })
  expect((await answer.innerText()).trim().length).toBeGreaterThan(0)

  // 4. The history sidebar lists this session.
  const list = page.getByTestId('session-list')
  await expect(list).toBeVisible({ timeout: 30_000 })
  await expect(list.getByRole('button').first()).toBeVisible()

  // 5. Reload restores the session (persisted last-session id) with its turn.
  await page.reload()
  await page.goto('/app/')
  await expect(page.getByTestId('answer-pane').first()).toBeVisible({ timeout: 30_000 })
})
