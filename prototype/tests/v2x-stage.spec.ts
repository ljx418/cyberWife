import { expect, test, type Page } from '@playwright/test'

async function installContracts(page: Page, enabled = true) {
  await page.route('http://127.0.0.1:7860/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname
    const json = (body: unknown, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
    if (path === '/api/v1/experience/settings') return json({ schema_version: 1, features: { stage_composition: enabled } })
    if (path === '/api/v1/onboarding/draft') return json({ id: 1, consent_granted: true, step_completed: 5, profile_draft_json: {}, settings_json: { completed: true }, device_snapshot_json: {} })
    if (path === '/api/v1/profile') return json({ id: 1, name: '小雅', user_nickname: '你', persona: '', relationship_context: '', example_dialogue: '', version: 1, updated_at: '2026-10-08T00:00:00Z' })
    if (path === '/api/v1/health') return json({ status: 'ready', components: {}, resources: {}, version: {} })
    if (path === '/api/v1/assets/portrait') return json({ kind: 'portrait', items: [] })
    if (path === '/api/v1/avatar/active') return json({ detail: 'avatar.not_found' }, 404)
    return json({ ok: true })
  })
}

test('X2控制器统一分类、焦点边界和条幅降级', async ({ page }) => {
  await page.goto('/?preview=1')
  const result = await page.evaluate(async () => {
    const module = await import('/src/services/StagePresentation.ts')
    return {
      standard: module.resolveStagePresentation('full', 1920, 1080, { x: 120, y: -5 }),
      tall: module.resolveStagePresentation('full', 2160, 3500),
      strip: module.resolveStagePresentation('full', 3840, 180),
    }
  })
  expect(result.standard).toMatchObject({ layout: 'standard', requested: 'full', effective: 'full', focus: { x: 90, y: 8 }, degradedReason: null })
  expect(result.tall).toMatchObject({ layout: 'ultratall', effective: 'full' })
  expect(result.strip).toMatchObject({ layout: 'strip', requested: 'full', effective: 'close' })
  expect(result.strip.degradedReason).toContain('条幅窗口')
})

test('X2用户切换全身构图并跨刷新保留', async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 })
  await installContracts(page, true)
  await page.goto('/?preview=1')
  await page.getByRole('button', { name: '设置' }).click()
  await page.getByRole('radio', { name: '全身' }).click()
  await expect(page.locator('main.experience')).toHaveAttribute('data-composition', 'full')
  await page.reload()
  await expect(page.locator('main.experience')).toHaveAttribute('data-requested-composition', 'full')
  expect(await page.evaluate(() => localStorage.getItem('cyberwife-composition'))).toBe('full')
})

for (const viewport of [{ width: 2160, height: 3500 }, { width: 420, height: 720 }]) {
  test(`X2 ${viewport.width}x${viewport.height} 全身舞台无溢出且主操作可达`, async ({ page }) => {
    await page.setViewportSize(viewport)
    await page.addInitScript(() => localStorage.setItem('cyberwife-composition', 'full'))
    await installContracts(page, true)
    await page.goto('/?preview=1')
    await expect(page.locator('main.experience')).toHaveAttribute('data-composition', 'full')
    const result = await page.evaluate(() => {
      const main = document.querySelector('main')!.getBoundingClientRect()
      const background = document.querySelector('.scene-background')!.getBoundingClientRect()
      const button = document.querySelector('.voice-button')!.getBoundingClientRect()
      return {
        composition: document.querySelector('main')!.getAttribute('data-composition'),
        overflow: Math.max(document.documentElement.scrollWidth - document.documentElement.clientWidth, document.body.scrollWidth - document.body.clientWidth),
        main: { width: main.width, height: main.height },
        background: { width: background.width, height: background.height },
        buttonVisible: button.width > 0 && button.height > 0 && button.top < innerHeight && button.bottom > 0,
      }
    })
    expect(result.composition).toBe('full')
    expect(result.overflow).toBeLessThanOrEqual(1)
    expect(result.background.width).toBeGreaterThanOrEqual(result.main.width)
    expect(result.background.height).toBeGreaterThanOrEqual(result.main.height)
    expect(result.buttonVisible).toBe(true)
  })
}

test('X2条幅请求全身时明确降级近景并保持主操作', async ({ page }) => {
  await page.setViewportSize({ width: 3840, height: 180 })
  await page.addInitScript(() => localStorage.setItem('cyberwife-composition', 'full'))
  await installContracts(page, true)
  await page.goto('/?preview=1')
  const main = page.locator('main.experience')
  await expect(main).toHaveAttribute('data-requested-composition', 'full')
  await expect(main).toHaveAttribute('data-composition', 'close')
  await expect(page.getByText('条幅窗口优先保留面部与主操作')).toBeVisible()
  await expect(page.getByRole('button', { name: '开始对话' })).toBeVisible()
})

test('X2 feature flag关闭时隐藏构图控制并使用V1默认半身', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('cyberwife-composition', 'full'))
  await installContracts(page, false)
  await page.goto('/?preview=1')
  await expect(page.locator('main.experience')).toHaveAttribute('data-composition', 'half')
  await page.getByRole('button', { name: '设置' }).click()
  await expect(page.getByRole('radiogroup', { name: '人物构图' })).toHaveCount(0)
})
