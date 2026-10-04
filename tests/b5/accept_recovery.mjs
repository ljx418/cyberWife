import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { execFileSync, spawn } from 'node:child_process'
import { chromium } from '../../prototype/node_modules/playwright/index.mjs'

const root = path.resolve(import.meta.dirname, '../..')
const arg = name => { const i = process.argv.indexOf(name); return i >= 0 ? process.argv[i + 1] : undefined }
const cycles = Number(arg('--cycles') || 3)
const onlyManaged = arg('--managed')
const evidence = path.resolve(arg('--evidence') || path.join(root, 'audit/v1/B5/B5.2-recovery'))
const launcher = 'C:\\workSpace\\cyberWife\\ops\\windows\\RuntimeLauncher.ps1'
const ps = args => execFileSync('powershell.exe', ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', launcher, ...args], { cwd: root, encoding: 'utf8', timeout: 180000 })
const psDetached = args => {
  const child = spawn('powershell.exe', ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', launcher, ...args], { cwd: root, stdio: 'ignore', detached: true })
  child.unref()
}
const wait = ms => new Promise(resolve => setTimeout(resolve, ms))
const health = async () => {
  const response = await fetch('http://127.0.0.1:7860/api/v1/health')
  if (!response.ok) throw new Error(`health ${response.status}`)
  return response.json()
}
async function waitHealth(component, expected, timeout = 120000) {
  const started = performance.now()
  while (performance.now() - started < timeout) {
    try {
      const body = await health()
      if (body.components?.[component]?.status === expected) return { ms: performance.now() - started, body }
    } catch {}
    await wait(100)
  }
  throw new Error(`${component} did not become ${expected}`)
}
async function recover(component) {
  const response = await fetch('http://127.0.0.1:7860/api/v1/launcher/recover', {
    method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ component }),
  })
  if (!response.ok) throw new Error(`recover ${component}: ${response.status} ${await response.text()}`)
  return response.json()
}

await recover('all')
const browser = await chromium.connectOverCDP(process.env.CW_CHROME_CDP || 'http://127.0.0.1:9222')
const context = await browser.newContext()
const page = await context.newPage()
const cdp = await context.newCDPSession(page)
await cdp.send('Network.enable')
await cdp.send('Network.setCacheDisabled', { cacheDisabled: true })
const browserHealthResponses = []
page.on('response', response => {
  if (response.url().includes('/api/v1/health')) browserHealthResponses.push({ at: Date.now(), status: response.status(), url: response.url() })
})
await page.goto('http://127.0.0.1:4173/?preview=1')
await page.bringToFront()
await page.locator('.topbar .text-button').click()
await page.locator('.drawer-tabs button').filter({ hasText: /^运行状态$/ }).click()
await page.waitForTimeout(500)
const navigationStart = await page.evaluate(() => performance.getEntriesByType('navigation').length)
const rows = []

async function waitUiText(locator, predicate, timeout = 3000) {
  const started = performance.now()
  let value = ''
  while (performance.now() - started < timeout) {
    value = await locator.innerText()
    if (predicate(value)) return { matched: true, value, ms: performance.now() - started }
    await page.waitForTimeout(100)
  }
  return { matched: false, value, ms: performance.now() - started }
}

for (let cycle = 1; cycle <= cycles; cycle += 1) {
  for (const scenario of [
    { managed: 'llama', logical: ['llm'], recover: 'llm' },
    { managed: 'speech', logical: ['asr', 'embedding'], recover: 'asr' },
    { managed: 'avatar', logical: ['avatar'], recover: 'avatar' },
  ].filter(item => !onlyManaged || item.managed === onlyManaged)) {
    const faultAt = performance.now()
    ps(['-Action', 'stop', '-Component', scenario.managed])
    const failures = []
    for (const logical of scenario.logical) failures.push(await waitHealth(logical, 'error', 3000))
    const browserHealthAfterFault = await page.evaluate(async () => {
      const response = await fetch('http://127.0.0.1:7860/api/v1/health', { cache: 'no-store' })
      return response.json()
    })
    const uiFailure = await waitUiText(page.locator('.runtime-list'), text => text.includes('error'))
    const uiText = uiFailure.value
    const recovery = await recover(scenario.recover)
    const ready = []
    for (const logical of scenario.logical) ready.push(await waitHealth(logical, 'ready'))
    await page.waitForTimeout(2100)
    rows.push({
      cycle, managed: scenario.managed, logical: scenario.logical,
      detection_ms: Math.max(...failures.map(item => item.ms)),
      browser_status_after_fault: Object.fromEntries(scenario.logical.map(id => [id, browserHealthAfterFault.components?.[id]?.status])),
      browser_health_response_count: browserHealthResponses.length,
      ui_showed_error: uiFailure.matched, ui_detection_ms: uiFailure.ms, recovery_status: recovery.status,
      ui_text: uiText,
      ready_ms: Math.max(...ready.map(item => item.ms)), pass: Math.max(...failures.map(item => item.ms)) <= 3000,
    })
  }

  if (!onlyManaged || onlyManaged === 'gateway') {
  // CosyVoice is hosted in Gateway in V1. Stop that owned process to prove
  // the UI reports the true control-plane impact and recovers in the same page.
  const faultAt = performance.now()
  ps(['-Action', 'stop', '-Component', 'gateway'])
  let unavailable = false
  const deadline = performance.now() + 3000
  while (performance.now() < deadline) {
    try { await health() } catch { unavailable = true; break }
    await wait(50)
  }
  const gatewayDetectionMs = performance.now() - faultAt
  const uiFailure = await waitUiText(
    page.locator('[data-testid="settings-api-status"]'),
    text => text.includes('Gateway 不可达'),
  )
  const downText = uiFailure.value
  psDetached(['-Action', 'recover', '-Component', 'gateway'])
  const httpStarted = performance.now()
  while (true) {
    try { await health(); break } catch {}
    if (performance.now() - httpStarted > 180000) throw new Error('gateway did not recover')
    await wait(250)
  }
  await recover('all')
  await page.waitForTimeout(2100)
  rows.push({
    cycle, managed: 'gateway', logical: ['tts'],
    detection_ms: unavailable ? gatewayDetectionMs : 3000,
    ui_showed_error: uiFailure.matched, ui_detection_ms: uiFailure.ms, unavailable,
    ui_text: downText,
    recovery_status: 'ready', ready_ms: performance.now() - httpStarted,
    pass: unavailable && String(downText).includes('Gateway 不可达'),
  })
  }
}

const navigationEnd = await page.evaluate(() => performance.getEntriesByType('navigation').length)
const result = {
  schema_version: 1, evidence_level: 'owned_process_failure_real_probe_windows_chrome',
  browser: await browser.version(), cycles, rows,
  page_reload_count: navigationEnd - navigationStart,
}
const scenariosPerCycle = onlyManaged ? 1 : 4
result.pass = rows.length === cycles * scenariosPerCycle && rows.every(row => row.pass && row.ui_showed_error && row.recovery_status === 'ready') && result.page_reload_count === 0
fs.mkdirSync(evidence, { recursive: true })
fs.writeFileSync(path.join(evidence, 'result.json'), `${JSON.stringify(result, null, 2)}\n`)
process.stdout.write(`${JSON.stringify(result, null, 2)}\n`)
await page.close(); await context.close(); await browser.close()
if (!result.pass) process.exitCode = 2
