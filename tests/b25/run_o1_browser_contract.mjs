/** Target-Windows Edge contract/regression checks over an existing CDP endpoint. */
import fs from 'node:fs'
import path from 'node:path'
import { chromium } from '../../prototype/node_modules/playwright/index.mjs'

const root = path.resolve(import.meta.dirname, '../..')
const output = path.resolve(process.argv[2] || path.join(root, 'audit/v1/B2.5/O1/browser-contract.json'))
const browser = await chromium.connectOverCDP('http://127.0.0.1:9222')
const context = browser.contexts()[0] || await browser.newContext()
const page = await context.newPage()
const checks = {}

await page.goto('http://127.0.0.1:4173/?preview=1')
await page.evaluate(() => localStorage.clear())
await page.goto('http://127.0.0.1:4173/')
await page.getByRole('button', { name: '切换到原始 App.tsx（演示用）' }).click()
if (await page.getByRole('button', { name: '继续' }).count() === 0) {
  throw new Error(`onboarding entry missing at ${page.url()}: ${(await page.locator('body').innerText()).slice(0, 500)}`)
}
const continueButton = page.getByRole('button', { name: '继续' })
checks.consent_starts_disabled = await continueButton.isDisabled()
await page.getByRole('checkbox').check()
checks.consent_enables_continue = await continueButton.isEnabled()
await page.getByRole('button', { name: '跳过设置，查看原型' }).click()
checks.main_stage_visible = await page.getByRole('heading', { name: '你回来啦。' }).isVisible()
await page.getByRole('button', { name: '开始对话' }).click()
checks.listening_state_visible = await page.getByRole('heading', { name: '嗯，我在。' }).isVisible()
await page.getByRole('button', { name: '模拟说完一句话' }).click()
await page.getByRole('heading', { name: '其实我一直都记得。' }).waitFor({ state: 'visible' })
checks.thinking_state_visible = true
await page.getByRole('button', { name: '打断她' }).click()
checks.interrupted_state_visible = await page.getByRole('heading', { name: '嗯，你说。' }).isVisible()

await page.goto('http://127.0.0.1:4173/?preview=1')
await page.getByRole('button', { name: '切换到原始 App.tsx（演示用）' }).click()
const experience = page.locator('main.experience')
await experience.getByRole('button', { name: '设置' }).click()
const drawer = page.getByRole('dialog', { name: '她的世界' })
checks.settings_dialog_visible = await drawer.isVisible()
await drawer.getByRole('button', { name: '记忆', exact: true }).click()
await drawer.getByRole('article').first().getByRole('button', { name: '删除' }).click()
checks.delete_confirmation_visible = await page.getByRole('alertdialog').isVisible()
await page.getByRole('button', { name: '取消' }).click()
await drawer.getByRole('button', { name: '人物', exact: true }).click()
await drawer.getByRole('radio', { name: '柔和浅色' }).click()
checks.theme_switch_applied = (await page.locator('html').getAttribute('data-theme')) === 'soft-light'

checks.audio_contract = await page.evaluate(async () => {
  const { MediaSession } = await import('/src/services/MediaSession.ts')
  const encode = (value) => {
    const bytes = new Uint8Array(640)
    const view = new DataView(bytes.buffer)
    for (let index = 0; index < 320; index += 1) view.setInt16(index * 2, value, true)
    let binary = ''
    bytes.forEach((byte) => { binary += String.fromCharCode(byte) })
    return btoa(binary)
  }
  const sent = []
  const socket = { readyState: WebSocket.OPEN, send: (value) => sent.push(JSON.parse(value)) }
  const common = {
    type: 'reply.audio.chunk', session_id: '7', turn_id: 3,
    payload: {
      trace_id: '01HZX5K2C3D4E5F6G7H8J9K0A1', generation: 2,
      asr_final_wall_ms: Date.now() - 10_000, sample_rate: 16000,
      server_elapsed_ms: 100,
    },
  }
  await MediaSession.start()
  await MediaSession.handleServerEvent({
    ...common, payload: { ...common.payload, audio_chunk_b64: encode(0) },
  }, socket)
  await new Promise((resolve) => setTimeout(resolve, 80))
  const afterSilence = sent.length
  for (let repeat = 0; repeat < 2; repeat += 1) {
    await MediaSession.handleServerEvent({
      ...common, payload: { ...common.payload, audio_chunk_b64: encode(1200) },
    }, socket)
  }
  await new Promise((resolve) => setTimeout(resolve, 200))
  await MediaSession.stop()
  return {
    after_silence: afterSilence,
    confirmation_count: sent.length,
    confirmation_type: sent[0]?.type || null,
    generation: sent[0]?.generation ?? null,
    monotonic_split_clock_latency: (sent[0]?.asr_to_playback_ms ?? 10_000) >= 100 &&
      (sent[0]?.asr_to_playback_ms ?? 10_000) < 1_000,
  }
})

const passed = Object.entries(checks).every(([key, value]) =>
  key === 'audio_contract'
    ? value.after_silence === 0 && value.confirmation_count === 1 &&
      value.confirmation_type === 'audio.playback.started' && value.generation === 2 &&
      value.monotonic_split_clock_latency
    : value === true,
)
const report = { browser: await browser.version(), passed, checks }
fs.mkdirSync(path.dirname(output), { recursive: true })
fs.writeFileSync(output, `${JSON.stringify(report, null, 2)}\n`)
process.stdout.write(`${JSON.stringify(report, null, 2)}\n`)
await page.close()
await browser.close()
if (!passed) process.exitCode = 1
