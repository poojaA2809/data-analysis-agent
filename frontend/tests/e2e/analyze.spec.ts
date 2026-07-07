import { test, expect } from '@playwright/test'
import { join } from 'node:path'

// Full primary-journey E2E against the LIVE app served at :8001/app/.
//
// ASSUMPTION: the backend (`uv run python -m src`) is already running with the
// frontend built into `frontend/out/`, so the static export is served at
// http://localhost:8001/app/ and the API is same-origin. The qa-auditor starts
// the server before running this; the config does not launch it. Real Google
// Gemini key from `.env` — this asserts on REAL answer + code content, not just a 200.

// Playwright runs specs in a CommonJS context, so `__dirname` is available.
const CSV_FIXTURE = join(__dirname, 'fixtures', 'sales.csv')

test('upload a CSV, ask a question, and see a real answer + the exact code', async ({ page }) => {
  await page.goto('/app/')

  // Page loads and is styled (the primary heading is visible).
  await expect(page.getByRole('heading', { name: 'Data Analysis Agent' })).toBeVisible()

  // 1. Upload a CSV via the hidden file input behind the dropzone.
  await page.getByTestId('file-input').setInputFiles(CSV_FIXTURE)

  // The uploaded file chip confirms the dataset was accepted by /datasets.
  // Scope to the uploaded-files list — 'sales.csv' also appears in the dataset
  // picker and the profile card, so an unscoped locator is strict-mode ambiguous.
  await expect(
    page.getByTestId('uploaded-files').getByText('sales.csv'),
  ).toBeVisible({ timeout: 30_000 })

  // 2. Ask a question and submit.
  await page
    .getByLabel('Ask a question about your data')
    .fill('What is the average order value by region?')
  await page.getByRole('button', { name: 'Ask' }).click()

  // 3. A real, non-empty answer appears in the answer pane.
  const answer = page.getByTestId('answer-pane')
  await expect(answer).toBeVisible({ timeout: 60_000 })
  await expect(answer).not.toBeEmpty()
  expect((await answer.innerText()).trim().length).toBeGreaterThan(0)

  // 4. Expand "Code that ran" and assert the code panel shows non-empty code.
  await page.getByRole('button', { name: 'Code that ran' }).click()
  const code = page.getByTestId('code-block')
  await expect(code).toBeVisible()
  expect((await code.innerText()).trim().length).toBeGreaterThan(0)
})
