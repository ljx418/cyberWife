import { expect, test, type Page } from '@playwright/test'

const scenes = ['blue-hour-living', 'morning-bedroom', 'rainy-library', 'garden-sunroom'].map((slug, index) => ({
  scene_id: `00000000-0000-4000-8000-00000000000${index}`,
  slug,
  label: ['蓝调客厅', '清晨卧室', '雨夜书房', '花园阳光房'][index],
  description: ['暖灯与城市蓝调', '柔和晨光与浅木色', '安静深色与雨窗', '自然绿意与午后光'][index],
  asset_sha256: `${index + 1}`.repeat(64),
  preview_url: `/backgrounds/${slug}.webp`,
  focus: { x: 0.5, y: 0.42 },
  safe_area: { left: 0.08, top: 0.08, right: 0.92, bottom: 0.92 },
  quality_status: 'preview_only',
  can_activate: false,
}))

async function installContracts(page: Page, enabled = true) {
  await page.route('http://127.0.0.1:7860/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname
    const json = (body: unknown, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
    if (path === '/api/v1/experience/settings') return json({ schema_version: 1, features: { scene_presets: enabled } })
    if (path === '/api/v1/onboarding/draft') return json({ id: 1, consent_granted: true, step_completed: 5, profile_draft_json: {}, settings_json: { completed: true }, device_snapshot_json: {} })
    if (path === '/api/v1/profile') return json({ id: 1, name: '小雅', user_nickname: '你', persona: '', relationship_context: '', example_dialogue: '', version: 1, updated_at: '2026-10-08T00:00:00Z' })
    if (path === '/api/v1/health') return json({ status: 'ready', components: {}, resources: {}, version: {} })
    if (path === '/api/v1/assets/portrait') return json({ kind: 'portrait', items: [] })
    if (path === '/api/v1/avatar/active') return json({ detail: 'avatar.not_found' }, 404)
    if (path === '/api/v1/scene-presets') return json({ schema_version: 1, revision: 2, active_scene_id: null, items: scenes })
    return json({ ok: true })
  })
}

test('X3.1设置页展示四个真实登记场景但不开放虚假激活', async ({ page }) => {
  await installContracts(page, true)
  await page.goto('/?preview=1')
  await page.getByRole('button', { name: '设置' }).click()
  const catalog = page.getByTestId('scene-preset-catalog')
  await expect(catalog).toBeVisible()
  await expect(catalog.locator('.scene-preset-card')).toHaveCount(4)
  await expect(catalog.getByText('动态素材待准备', { exact: false })).toHaveCount(4)
  await expect(catalog.getByRole('radio')).toHaveCount(0)
  await expect(catalog.getByRole('button')).toHaveCount(0)
})

test('X3.1 feature flag关闭时保留原本地背景预览入口', async ({ page }) => {
  await installContracts(page, false)
  await page.goto('/?preview=1')
  await page.getByRole('button', { name: '设置' }).click()
  await expect(page.getByTestId('scene-preset-catalog')).toHaveCount(0)
  await expect(page.getByRole('radiogroup', { name: '本地背景' })).toBeVisible()
})

