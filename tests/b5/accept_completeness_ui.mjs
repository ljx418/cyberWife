import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { chromium } from '../../prototype/node_modules/playwright/index.mjs'

const output = path.resolve(process.argv[2])
const apiBase = process.argv[3] || 'http://127.0.0.1:7862'
const browser = await chromium.connectOverCDP(process.env.CW_CHROME_CDP || 'http://127.0.0.1:9222')
const context = await browser.newContext()
const page = await context.newPage()
await page.addInitScript(base => { window.CYBERWIFE_GATEWAY = base }, apiBase)
const responses = []
page.on('response', response => {
  if (response.url().startsWith(apiBase)) responses.push({ url: response.url(), status: response.status(), method: response.request().method() })
})
await page.goto('http://127.0.0.1:4173/?preview=1')
const mainVisible = await page.locator('main.experience').isVisible()
const legacyAbsent = await page.locator('[data-testid="legacy-development-entry"]').count() === 0
await page.locator('.topbar .text-button').click()
await page.locator('.drawer-tabs').waitFor({ state: 'visible' })
for (const label of ['人物', '声音', '人设', '记忆', '隐私', '运行状态']) {
  await page.locator('.drawer-tabs button').filter({ hasText: new RegExp(`^${label}$`) }).click()
  await page.waitForTimeout(350)
}
const tabLabels = await page.locator('.drawer-tabs button').allTextContents()
const apiStatus = await page.locator('[data-testid="settings-api-status"]').textContent()
const hostBridge = await page.evaluate(async () => {
  const { HostBridge } = await import('/src/platform/HostBridge.ts?b5=ac00')
  return {
    mode: await HostBridge.getWindowMode(),
    top: await HostBridge.setAlwaysOnTop(true),
    transparent: await HostBridge.setTransparent(true),
    quit: await HostBridge.quit(),
  }
})
const legacy = await context.newPage()
await legacy.goto('http://127.0.0.1:4173/?legacy=1')
const legacyVisible = await legacy.locator('[data-testid="legacy-development-entry"]').isVisible()
const paths = responses.filter(item => item.status < 500).map(item => new URL(item.url).pathname)
const required = [
  '/api/v1/assets/portrait', '/api/v1/assets/voice', '/api/v1/profile',
  '/api/v1/memories', '/api/v1/consents', '/api/v1/retention/now', '/api/v1/health',
]
const result = {
  browser: await browser.version(), mainVisible, legacyAbsent, legacyVisible,
  tabLabels, apiStatus, responses, hostBridge,
  requiredApiCoverage: Object.fromEntries(required.map(requiredPath => [requiredPath, paths.includes(requiredPath)])),
}
result.pass = mainVisible && legacyAbsent && legacyVisible &&
  JSON.stringify(tabLabels) === JSON.stringify(['人物', '声音', '人设', '记忆', '隐私', '运行状态']) &&
  Object.values(result.requiredApiCoverage).every(Boolean) &&
  hostBridge.mode === 'browser' && [hostBridge.top, hostBridge.transparent, hostBridge.quit].every(item => item.supported === false && item.reason === 'browser_unsupported')
fs.mkdirSync(path.dirname(output), { recursive: true })
fs.writeFileSync(output, `${JSON.stringify(result, null, 2)}\n`)
process.stdout.write(`${JSON.stringify(result, null, 2)}\n`)
await page.close(); await legacy.close(); await context.close(); await browser.close()
if (!result.pass) process.exitCode = 2
