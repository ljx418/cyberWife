import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { chromium } from '../../prototype/node_modules/playwright/index.mjs'

const [output, apiBase, portraitPath, voicePath] = process.argv.slice(2)
const browser = await chromium.connectOverCDP(process.env.CW_CHROME_CDP || 'http://127.0.0.1:9222')
const context = await browser.newContext()
const page = await context.newPage()
await page.addInitScript(base => { window.CYBERWIFE_GATEWAY = base }, apiBase)
const responses = []
page.on('response', response => {
  if (response.url().startsWith(apiBase)) responses.push({ path: new URL(response.url()).pathname, method: response.request().method(), status: response.status() })
})

const reloadAtStep = async label => {
  await page.reload({ waitUntil: 'networkidle' })
  await page.locator('.step-list__item.is-active').filter({ hasText: label }).waitFor()
}

let result
try {
  await page.goto(`http://127.0.0.1:4173/?onboarding=${Date.now()}`, { waitUntil: 'networkidle' })
  const firstNext = page.locator('.setup-actions .primary-button')
  const initiallyBlocked = await firstNext.isDisabled()
  await page.locator('.consent-check input').check()
  await firstNext.click()
  await page.locator('.step-list__item.is-active').filter({ hasText: '运行检查' }).waitFor()
  const runtimeCount = await page.locator('.runtime-item').count()
  await reloadAtStep('运行检查')
  await page.locator('.setup-actions .primary-button').click()
  await page.locator('.step-list__item.is-active').filter({ hasText: '人物形象' }).waitFor()
  await page.locator('.file-drop input[type=file]').setInputFiles(portraitPath)
  await page.getByTestId('onboarding-status').filter({ hasText: '人物已保存并激活' }).waitFor()
  const cropSliders = page.locator('.crop-controls input[type=range]')
  await cropSliders.nth(0).fill('1.25')
  await cropSliders.nth(1).fill('24')
  await cropSliders.nth(2).fill('-18')
  const [cropResponse] = await Promise.all([
    page.waitForResponse(response => response.url() === `${apiBase}/api/v1/assets/portrait/preview` && response.request().method() === 'POST'),
    page.getByRole('button', { name: '应用裁切并保存' }).click(),
  ])
  await page.locator('.setup-actions .primary-button').click()
  await page.locator('.step-list__item.is-active').filter({ hasText: '声音样本' }).waitFor()
  await reloadAtStep('声音样本')
  await page.locator('.file-drop input[type=file]').setInputFiles(voicePath)
  await page.getByTestId('onboarding-status').filter({ hasText: '声音已保存并激活' }).waitFor()
  await page.locator('textarea').fill('今天天气不错，我想和你聊聊天')
  await page.locator('.setup-actions .primary-button').click()
  await page.locator('.step-list__item.is-active').filter({ hasText: '人设关系' }).waitFor()
  await reloadAtStep('人设关系')
  const fields = page.locator('.setup-content input')
  await fields.nth(0).fill('小雅验收')
  await fields.nth(1).fill('阿林验收')
  await page.locator('.setup-content textarea').fill('亲近、自然、先回应感受，再回答问题。')
  await page.locator('.setup-actions .primary-button').click()
  await page.locator('main.experience').waitFor()
  await page.reload({ waitUntil: 'networkidle' })
  const persistedMain = await page.locator('main.experience').isVisible()
  const [draft, profile, portrait, voice, consents] = await Promise.all([
    page.evaluate(async base => (await fetch(`${base}/api/v1/onboarding/draft`)).json(), apiBase),
    page.evaluate(async base => (await fetch(`${base}/api/v1/profile`)).json(), apiBase),
    page.evaluate(async base => (await fetch(`${base}/api/v1/assets/portrait`)).json(), apiBase),
    page.evaluate(async base => (await fetch(`${base}/api/v1/assets/voice`)).json(), apiBase),
    page.evaluate(async base => (await fetch(`${base}/api/v1/consents`)).json(), apiBase),
  ])
  const sha = value => crypto.createHash('sha256').update(String(value)).digest('hex')
  result = {
    schema_version: 1,
    evidence_level: 'windows_chrome_real_http_sqlite_files',
    initially_blocked: initiallyBlocked,
    runtime_components: runtimeCount,
    persisted_main: persistedMain,
    completed: draft.settings_json?.completed === true,
    step_completed: draft.step_completed,
    profile: { name_sha256: sha(profile.name), nickname_sha256: sha(profile.user_nickname), version: profile.version },
    assets: {
      portrait_versions: portrait.items.length,
      portrait_active: portrait.items.filter(item => item.is_active).length,
      voice_versions: voice.items.length,
      voice_active: voice.items.filter(item => item.is_active).length,
    },
    crop_interaction: { zoom: 1.25, x: 24, y: -18, status: cropResponse.status() },
    active_consents: consents.items.filter(item => item.granted).length,
    api_manifest: responses,
  }
  result.pass = Boolean(
    initiallyBlocked && runtimeCount === 6 && persistedMain && result.completed && draft.step_completed === 4 &&
    profile.name === '小雅验收' && profile.user_nickname === '阿林验收' &&
    result.assets.portrait_versions === 2 && result.assets.portrait_active === 1 && result.assets.voice_active === 1 &&
    result.crop_interaction.status === 200 && result.active_consents >= 1
  )
} catch (error) {
  result = { schema_version: 1, pass: false, error: String(error), api_manifest: responses }
} finally {
  fs.writeFileSync(output, JSON.stringify(result, null, 2) + '\n')
  await context.close().catch(() => {})
  await browser.close().catch(() => {})
}
console.log(JSON.stringify(result, null, 2))
process.exit(result.pass ? 0 : 2)
