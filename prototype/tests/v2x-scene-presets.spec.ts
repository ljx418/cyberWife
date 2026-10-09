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
  idle_url: null,
  speaking_avatar_id: null,
}))

async function installContracts(page: Page, enabled = true, approved = false, combinationMode = false) {
  let revision = approved ? 10 : 2
  let activeSceneId = approved ? scenes[0].scene_id : null
  let activeAppearanceId = combinationMode ? '10000000-0000-4000-8000-000000000001' : null
  const appearances = combinationMode ? [
    { appearance_id: '10000000-0000-4000-8000-000000000001', label: '红色针织上衣', confirmed: true },
    { appearance_id: '10000000-0000-4000-8000-000000000002', label: '蓝白碎花上衣', confirmed: true },
  ] : []
  const combinations = combinationMode ? appearances.flatMap((appearance) => scenes.slice(1).map((scene) => ({
    appearance_id: appearance.appearance_id,
    scene_id: scene.scene_id,
    idle_url: `/api/v1/scene-presets/${scene.scene_id}/idle`,
    speaking_avatar_id: `avatar_${appearance.appearance_id.slice(-1)}_${scene.slug.replaceAll('-', '_')}`,
    engine: 'musetalk',
  }))) : []
  const catalogItems = () => scenes.map((scene) => approved ? {
    ...scene,
    quality_status: scene.scene_id === activeSceneId ? 'active' : combinationMode && scene === scenes[0] ? 'preview_only' : 'approved',
    can_activate: !combinationMode || scene !== scenes[0],
    idle_url: combinationMode && scene === scenes[0] ? null : `/api/v1/scene-presets/${scene.scene_id}/idle`,
    speaking_avatar_id: combinationMode && scene !== scenes[0]
      ? `avatar_${activeAppearanceId!.slice(-1)}_${scene.slug.replaceAll('-', '_')}`
      : `avatar_${scene.slug.replaceAll('-', '_')}`,
  } : scene)
  await page.route('http://127.0.0.1:7860/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname
    const json = (body: unknown, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
    if (path === '/api/v1/experience/settings') return json({ schema_version: 1, features: { scene_presets: enabled, output_controls: true } })
    if (path === '/api/v1/onboarding/draft') return json({ id: 1, consent_granted: true, step_completed: 5, profile_draft_json: {}, settings_json: { completed: true }, device_snapshot_json: {} })
    if (path === '/api/v1/profile') return json({ id: 1, name: '小雅', user_nickname: '你', persona: '', relationship_context: '', example_dialogue: '', version: 1, updated_at: '2026-10-08T00:00:00Z' })
    if (path === '/api/v1/health') return json({ status: 'ready', components: {}, resources: {}, version: {} })
    if (path === '/api/v1/assets/portrait') return json({ kind: 'portrait', items: [] })
    if (path === '/api/v1/avatar/active') return json({ detail: 'avatar.not_found' }, 404)
    if (path === '/api/v1/scene-presets') return json({ schema_version: combinationMode ? 2 : 1, revision, active_scene_id: activeSceneId, active_appearance_id: activeAppearanceId, appearances, combinations, items: catalogItems() })
    if (path.startsWith('/api/v1/scene-presets/') && path.endsWith('/activate')) {
      activeSceneId = path.split('/')[4]
      if (combinationMode) activeAppearanceId = JSON.parse(route.request().postData() || '{}').appearance_id
      revision += 1
      return json({ schema_version: combinationMode ? 2 : 1, revision, active_scene_id: activeSceneId, active_appearance_id: activeAppearanceId, appearances, combinations, items: catalogItems() })
    }
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
  await expect(catalog.getByRole('button', { name: '尚不可用' })).toHaveCount(4)
})

test('X3.3批准场景可原子切换并更新当前空间状态', async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(navigator, 'mediaDevices', { value: {
      enumerateDevices: async () => [{ deviceId: 'default', kind: 'audiooutput', label: '系统默认', groupId: '', toJSON: () => ({}) }],
    }, configurable: true })
  })
  await installContracts(page, true, true)
  await page.goto('/?preview=1')
  await page.getByRole('button', { name: '开始对话' }).click({ trial: true })
  await page.getByRole('button', { name: '设置' }).click()
  const catalog = page.getByTestId('scene-preset-catalog')
  await expect(catalog.getByText('当前空间', { exact: false })).toHaveCount(1)
  const target = catalog.locator('[data-scene-id="00000000-0000-4000-8000-000000000001"]')
  await target.getByRole('button', { name: '切换到这里' }).click()
  await expect(target.getByRole('button', { name: '正在使用' })).toBeVisible()
  await expect(page.getByTestId('settings-api-status')).toContainText('当前对话保持连接')
})

test('X3.1 feature flag关闭时保留原本地背景预览入口', async ({ page }) => {
  await installContracts(page, false)
  await page.goto('/?preview=1')
  await page.getByRole('button', { name: '设置' }).click()
  await expect(page.getByTestId('scene-preset-catalog')).toHaveCount(0)
  await expect(page.getByRole('radiogroup', { name: '本地背景' })).toBeVisible()
})

test('X3.5可选择外观并原子激活匹配的完整场景组合', async ({ page }) => {
  await installContracts(page, true, true, true)
  await page.goto('/?preview=1')
  await page.getByRole('button', { name: '设置' }).click()
  const appearances = page.getByRole('radiogroup', { name: '已批准外观' })
  await expect(appearances.getByRole('radio')).toHaveCount(2)
  await appearances.getByRole('radio', { name: '蓝白碎花上衣' }).click()
  const target = page.getByTestId('scene-preset-catalog').locator(`[data-scene-id="${scenes[2].scene_id}"]`)
  await target.getByRole('button', { name: '切换到这里' }).click()
  await expect(appearances.getByRole('radio', { name: '蓝白碎花上衣' })).toHaveAttribute('aria-checked', 'true')
  await expect(target.getByRole('button', { name: '正在使用' })).toBeVisible()
  await expect(page.getByTestId('settings-api-status')).toContainText('蓝白碎花上衣 · 雨夜书房')
})
