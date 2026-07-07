import { test, expect } from '@playwright/test'
import { join } from 'node:path'

// Phase-A E2E against the LIVE single-origin app (base URL from E2E_BASE_URL,
// default :8001/app/). Real Google Gemini key from `.env`. Asserts that AFTER a
// CSV upload — WITHOUT the user typing any question — the auto-dashboard renders
// real content: ≥2 charts, a summary table, an insights list (≥2 items), and a
// data grid ("of N rows"). Dashboard generation makes multiple Gemini calls, so
// steps get generous (120s) timeouts.

const CSV_FIXTURE = join(__dirname, 'fixtures', 'sales.csv')

test('uploading a CSV auto-renders a dashboard with charts, table, insights, and a data grid', async ({
  page,
}) => {
  test.setTimeout(240_000)
  await page.goto('/app/')

  await expect(page.getByRole('heading', { name: 'Data Analysis Agent' })).toBeVisible()

  // Upload the CSV fixture — no question is typed.
  await page.getByTestId('file-input').setInputFiles(CSV_FIXTURE)
  await expect(
    page.getByTestId('uploaded-files').getByText('sales.csv'),
  ).toBeVisible({ timeout: 30_000 })

  // The dashboard is auto-triggered: it should appear without any question.
  const dashboard = page.getByTestId('dashboard')
  await expect(dashboard).toBeVisible({ timeout: 180_000 })

  // Title present.
  await expect(page.getByTestId('dashboard-title')).toBeVisible()

  // >= 2 charts — assert on rendered recharts surfaces.
  await expect
    .poll(async () => page.locator('[data-testid="dashboard"] .recharts-surface').count(), {
      timeout: 30_000,
    })
    .toBeGreaterThanOrEqual(2)

  // Summary table renders with rows.
  const summary = page.getByTestId('dashboard-summary')
  await expect(summary).toBeVisible()
  await expect(summary.locator('table tbody tr').first()).toBeVisible()

  // Insights list — at least 2 items.
  await expect
    .poll(async () => page.getByTestId('dashboard-insight').count(), { timeout: 15_000 })
    .toBeGreaterThanOrEqual(2)

  // Data grid with an "of N rows" caption and record rows.
  const caption = page.getByTestId('dashboard-grid-caption')
  await expect(caption).toBeVisible()
  await expect(caption).toContainText(/of \d+ rows/)
  await expect(
    page.getByTestId('dashboard-grid').locator('table tbody tr').first(),
  ).toBeVisible()

  // The Export/Share control is the single labelled, disabled Phase-B stub.
  const exportStub = page.getByTestId('dashboard-export-stub')
  await expect(exportStub).toBeVisible()
  await expect(exportStub).toBeDisabled()
  await expect(exportStub).toContainText('Coming soon')
})
