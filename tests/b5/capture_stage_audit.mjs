import { chromium } from '../../prototype/node_modules/playwright/index.mjs'
import { mkdir } from 'node:fs/promises'
import { resolve } from 'node:path'

const workspace = resolve(import.meta.dirname, '../..')
const output = resolve(workspace, 'docs/review/stage-audit-evidence')
await mkdir(output, { recursive: true })

const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: 'dark' })
const page = await context.newPage()
const redactPortrait = () => page.addStyleTag({ content: `
  .portrait,.onboarding__portrait,.portrait-preview,.profile-preview__image {
    background-image: radial-gradient(circle at 70% 40%, #314642 0, #162321 24%, #080d0e 62%) !important;
  }
  .avatar-video { visibility: hidden !important; }
` })

const health = {
  status: 'ready',
  components: Object.fromEntries(
    ['vad', 'asr', 'llm', 'tts', 'avatar', 'embedding'].map((id) => [id, { status: 'ready', logical_id: `${id}-local` }]),
  ),
  resources: { vram_used_gb: 11.56, vram_total_gb: 24, ram_used_gb: 13.32, ram_total_gb: 32, disk_free_gb: 880 },
  version: { app: 'v1-stage-audit', schema: '1' },
}
const draft = {
  id: 1, consent_granted: false, step_completed: 0, asset_consent_at: null,
  profile_draft_json: {}, settings_json: {}, device_snapshot_json: {}, updated_at: '2026-10-04T12:00:00Z',
}
const profile = {
  id: 1, name: '小雅', user_nickname: '你', persona: '亲近、自然，认真回应。',
  relationship_context: '私人日常伴侣', example_dialogue: '我陪你。', version: 3, updated_at: '2026-10-04T12:00:00Z',
}
const memories = {
  items: [
    { id: 41, content: '周末希望留出一段不被打扰的休息时间。', source_session_id: 'local-594', created_at: '2026-10-04T08:00:00+08:00', edited: false },
    { id: 42, content: '喜欢红茶，住在杭州。', source_session_id: 'local-594', created_at: '2026-10-04T08:02:00+08:00', edited: true },
  ],
}

await page.route('http://127.0.0.1:7860/api/v1/**', async (route) => {
  const url = route.request().url()
  let body = {}
  if (url.includes('/health')) body = health
  else if (url.includes('/onboarding/draft')) body = draft
  else if (url.endsWith('/profile')) body = profile
  else if (url.includes('/assets/')) body = { kind: url.includes('/voice') ? 'voice' : 'portrait', items: [] }
  else if (url.includes('/memories')) body = memories
  else if (url.includes('/consents')) body = { items: [] }
  else if (url.includes('/retention/now')) body = { days: 30 }
  await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })
})

await page.goto('http://127.0.0.1:4173/?preview=1')
await redactPortrait()
await page.getByRole('heading', { name: '你回来啦。' }).waitFor()
await page.screenshot({ path: resolve(output, '01-main-stage.webp'), type: 'webp', quality: 88, fullPage: true })

await page.getByRole('button', { name: '设置' }).click()
await page.getByRole('button', { name: '记忆', exact: true }).click()
await page.getByText('周末希望留出').waitFor()
await page.screenshot({ path: resolve(output, '02-memory-control.webp'), type: 'webp', quality: 88, fullPage: true })

await page.getByRole('button', { name: '运行状态', exact: true }).click()
await page.getByText('VAD', { exact: true }).waitFor()
await page.screenshot({ path: resolve(output, '03-runtime-ready.webp'), type: 'webp', quality: 88, fullPage: true })

await page.setViewportSize({ width: 420, height: 720 })
await page.screenshot({ path: resolve(output, '04-mobile-runtime.webp'), type: 'webp', quality: 88, fullPage: true })

await page.setViewportSize({ width: 1440, height: 900 })
await page.goto('http://127.0.0.1:4173/')
await redactPortrait()
await page.getByRole('checkbox').waitFor()
await page.screenshot({ path: resolve(output, '05-consent-gate.webp'), type: 'webp', quality: 88, fullPage: true })

await page.goto(`file://${resolve(workspace, 'docs/review/cyberwife-v1-stage-audit-architecture.html')}`)
await page.waitForTimeout(800)
await page.screenshot({ path: resolve(output, '06-current-architecture.webp'), type: 'webp', quality: 88, fullPage: false })

await browser.close()
console.log(JSON.stringify({ pass: true, output, screenshots: 6 }))
