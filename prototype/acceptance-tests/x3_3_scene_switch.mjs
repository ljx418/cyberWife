import { chromium } from 'playwright'
import fs from 'node:fs/promises'

const base = process.env.CW_BASE_URL || 'http://127.0.0.1:7860'
const output = process.env.CW_X3_3_OUTPUT || '/home/administrator/.cyberWife/acceptance/V2-X3.3/ui'
await fs.mkdir(output, { recursive: true })
const browser = await chromium.launch({
  headless: true,
  args: ['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream'],
})
const context = await browser.newContext({ permissions: ['microphone'], viewport: { width: 1440, height: 900 } })
const page = await context.newPage()
const sessionResponses = []
const activationRequests = []
let endRequests = 0
page.on('response', async (response) => {
  const request = response.request()
  const path = new URL(response.url()).pathname
  if (request.method() === 'POST' && path === '/api/v1/sessions' && response.ok()) {
    sessionResponses.push(await response.json())
  }
})
page.on('request', (request) => {
  const path = new URL(request.url()).pathname
  if (request.method() === 'POST' && path.includes('/scene-presets/') && path.endsWith('/activate')) activationRequests.push(path)
  if (request.method() === 'POST' && /\/api\/v1\/sessions\/[^/]+\/end$/.test(path)) endRequests += 1
})

const records = []
try {
  await page.goto(base, { waitUntil: 'networkidle' })
  const start = page.getByRole('button', { name: '开始对话' })
  await start.waitFor({ timeout: 20_000 })
  await start.click()
  await page.getByRole('button', { name: '结束对话' }).waitFor({ timeout: 20_000 })
  await page.getByRole('button', { name: '设置' }).click()
  const slugs = ['morning-bedroom', 'rainy-library', 'garden-sunroom', 'blue-hour-living']
  for (const slug of slugs) {
    const card = page.locator(`[data-scene-id]`).filter({ has: page.locator(`img[src*="${slug}"]`) })
    await card.getByRole('button', { name: '切换到这里' }).click()
    await card.getByRole('button', { name: '正在使用' }).waitFor({ timeout: 20_000 })
    await page.getByTestId('settings-api-status').filter({ hasText: '当前对话保持连接' }).waitFor({ timeout: 20_000 })
    await page.screenshot({ path: `${output}/${slug}.png`, fullPage: true })
    records.push({ slug, active: true })
  }
  if (sessionResponses.length !== 1 || activationRequests.length !== 4 || endRequests !== 0) {
    throw new Error(`session continuity failed: sessions=${sessionResponses.length}, activations=${activationRequests.length}, ends=${endRequests}`)
  }
  await page.getByRole('button', { name: '关闭' }).click()
  await page.getByRole('button', { name: '结束对话' }).click()
  const result = {
    schema_version: 1,
    result: 'PASS',
    session_ref: sessionResponses[0].session_ref,
    session_create_count: sessionResponses.length,
    activation_count: activationRequests.length,
    end_requests_before_user_stop: endRequests,
    scenes: records,
    headless: true,
  }
  await fs.writeFile(`${output}/result.json`, JSON.stringify(result, null, 2) + '\n')
  console.log(JSON.stringify(result, null, 2))
} finally {
  await browser.close()
}
