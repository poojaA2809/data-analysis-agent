import { test, expect } from '@playwright/test'
import { join } from 'node:path'

// Phase-3 E2E against the LIVE single-origin app (base URL from E2E_BASE_URL,
// default :8001/app/). Real Google Gemini key from `.env` — this asserts on the
// REAL streamed answer, a rendered recharts chart, key-stats/tables, the cost
// bar (per-query + daily total), clickable follow-up chips, and the clarify
// callout for a vague question. Real-LLM steps get generous timeouts.

const CSV_FIXTURE = join(__dirname, 'fixtures', 'sales.csv')

test('streamed answer renders a chart, key-stats/table, cost, and working follow-ups', async ({
  page,
}) => {
  test.setTimeout(300_000)
  await page.goto('/app/')

  await expect(page.getByRole('heading', { name: 'Data Analysis Agent' })).toBeVisible()

  // 1. Upload the CSV fixture.
  await page.getByTestId('file-input').setInputFiles(CSV_FIXTURE)
  await expect(
    page.getByTestId('uploaded-files').getByText('sales.csv'),
  ).toBeVisible({ timeout: 30_000 })

  // 2. Ask an aggregate question that should yield a chart + stats.
  //
  // The REAL Gemini agent occasionally exhausts its code-gen retries and
  // finalizes a turn with no chart data (charts:0). That is genuine agent
  // variance, not a rendering bug — so we RE-ASK (up to 3 attempts), each time
  // strictly requiring a real recharts chart to render. We never loosen the
  // chart assertion; a run that never charts still fails.
  const askInput = page.getByLabel('Ask a question about your data')
  const chart = page.getByTestId('chart-card').first()
  const QUESTION = 'What is the total sales (order_value) by region? Show a bar chart.'

  // Poll a turn to a terminal outcome: a chart rendered, or the turn finished
  // (submit button back to "Ask") with no chart.
  async function turnOutcome(): Promise<'chart' | 'no-chart' | 'pending'> {
    if ((await page.getByTestId('chart-card').count()) > 0) return 'chart'
    const idle = (await page.getByRole('button', { name: 'Ask' }).count()) > 0
    return idle ? 'no-chart' : 'pending'
  }

  let charted = false
  for (let attempt = 0; attempt < 3 && !charted; attempt++) {
    await askInput.fill(QUESTION)
    await page.getByRole('button', { name: 'Ask' }).click()
    // Wait for the run to actually start (button flips to "Analyzing…") so the
    // poll below doesn't read a stale idle state before submit takes effect.
    await page
      .getByRole('button', { name: 'Analyzing' })
      .waitFor({ state: 'visible', timeout: 15_000 })
      .catch(() => {})

    const deadline = Date.now() + 160_000
    for (;;) {
      const o = await turnOutcome()
      if (o === 'chart') {
        charted = true
        break
      }
      if (o === 'no-chart') break // finished without a chart -> re-ask
      if (Date.now() > deadline) break
      await page.waitForTimeout(1500)
    }
  }

  // 3. A recharts chart renders (SVG surface) with a visible title.
  await expect(chart).toBeVisible({ timeout: 30_000 })
  await expect(chart.locator('.recharts-surface').first()).toBeVisible()

  // 4. The streamed answer is real and non-empty.
  const answer = page.getByTestId('answer-pane').first()
  await expect(answer).toBeVisible()
  await expect(answer).not.toBeEmpty()
  expect((await answer.innerText()).trim().length).toBeGreaterThan(0)

  // 5. At least one key-stat OR a summary table renders.
  const stats = page.getByTestId('key-stat')
  const tables = page.getByTestId('table-card')
  const statOrTable = (await stats.count()) + (await tables.count())
  expect(statOrTable).toBeGreaterThan(0)

  // 6. The cost bar shows this-query cost + a daily total.
  const costBar = page.getByTestId('cost-bar')
  await expect(costBar).toBeVisible()
  await expect(page.getByTestId('query-cost')).toContainText('$')
  await expect(page.getByTestId('daily-cost')).toContainText('$')
  // The per-query cost should have resolved to a real dollar figure.
  await expect(page.getByTestId('query-cost')).toContainText(/\$\d/, { timeout: 30_000 })

  // 7. Follow-up chips appear and clicking one submits a new question.
  const chips = page.getByTestId('followup-chip')
  await expect(chips.first()).toBeVisible({ timeout: 30_000 })
  const chipCount = await chips.count()
  expect(chipCount).toBeGreaterThanOrEqual(2)

  const answersBefore = await page.getByTestId('answer-pane').count()
  await chips.first().click()
  // A new answer pane appears for the follow-up turn (another real-LLM run).
  await expect
    .poll(async () => page.getByTestId('answer-pane').count(), { timeout: 120_000 })
    .toBeGreaterThan(answersBefore)
})

test('a vague question triggers the clarify callout with no code panel', async ({ page }) => {
  test.setTimeout(120_000)
  await page.goto('/app/')

  await expect(page.getByRole('heading', { name: 'Data Analysis Agent' })).toBeVisible()

  // Upload so the ask path is enabled.
  await page.getByTestId('file-input').setInputFiles(CSV_FIXTURE)
  await expect(
    page.getByTestId('uploaded-files').getByText('sales.csv'),
  ).toBeVisible({ timeout: 30_000 })

  // A deliberately vague prompt should route to the clarify branch.
  await page.getByLabel('Ask a question about your data').fill('tell me stuff')
  await page.getByRole('button', { name: 'Ask' }).click()

  const clarify = page.getByTestId('clarify-prompt').first()
  await expect(clarify).toBeVisible({ timeout: 90_000 })
  expect((await clarify.innerText()).trim().length).toBeGreaterThan(0)

  // No "Code that ran" panel for a clarify turn.
  await expect(page.getByRole('button', { name: 'Code that ran' })).toHaveCount(0)
})
