import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { chromium } from '../../prototype/node_modules/playwright/index.mjs'

const output = path.resolve(process.argv[2] || 'audit/v1/B5/B5.4B-no-record-ui/result.json')
fs.mkdirSync(path.dirname(output), { recursive: true })
const browser = await chromium.connectOverCDP(process.env.CW_CHROME_CDP || 'http://127.0.0.1:9226')
const context = await browser.newContext()
const page = await context.newPage()
const patches = []
const sockets = []
page.on('response', response => {
  if (response.url().includes('/no_record')) patches.push({ status: response.status(), method: response.request().method() })
})
page.on('websocket', socket => {
  if (socket.url().includes('/ws/v1/sessions/')) sockets.push(new URL(socket.url()).pathname.split('/').at(-1))
})
let result
try {
  await page.goto(`http://127.0.0.1:4173/?preview=1&no-record=${Date.now()}`)
  await page.locator('.voice-button').click()
  await page.waitForFunction(() => window.__CYBERWIFE_SESSION__?.input().activeTracks === 1)
  await page.locator('.topbar .text-button').click()
  await page.locator('.drawer-tabs button').filter({ hasText: /^隐私$/ }).click()
  const toggle = page.locator('.privacy-toggle input')
  await toggle.click()
  await page.getByTestId('settings-api-status').filter({ hasText: '已由后端切换为不记录' }).waitFor({ timeout: 15000 })
  result = {
    schema_version: 1,
    patches,
    socket_count: sockets.length,
    old_ref_numeric: /^\d+$/.test(sockets[0] || ''),
    new_ref_opaque: /^[0-9a-f]{32}$/.test(sockets[1] || ''),
    checked: await toggle.isChecked(),
    status_confirmed: true,
  }
  result.pass = patches.length === 1 && patches[0].status === 200 && result.socket_count === 2 && result.old_ref_numeric && result.new_ref_opaque && result.checked
} catch (error) {
  result = { schema_version: 1, pass: false, error: String(error), patches, socket_count: sockets.length }
} finally {
  fs.writeFileSync(output, JSON.stringify(result, null, 2) + '\n')
  await context.close().catch(() => {})
  await browser.close().catch(() => {})
}
console.log(JSON.stringify(result, null, 2))
process.exit(result.pass ? 0 : 2)
