import { expect, test, type Page } from '@playwright/test'

async function installContracts(page: Page) {
  let memories: Array<Record<string, unknown>> = []
  let candidates = [{
    content: '今天想早点休息', confidence: 0.65,
    source_session_id: 8, source_turn_id: 2, reason: 'temporary_context',
  }]
  await page.route('http://127.0.0.1:7860/api/v1/**', async (route) => {
    const request = route.request()
    const path = new URL(request.url()).pathname
    const json = (body: unknown, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
    if (path === '/api/v1/health') return json({ status: 'ready', components: {}, resources: {}, version: {} })
    if (path === '/api/v1/onboarding/draft') return json({ id: 1, consent_granted: true, step_completed: 4, profile_draft_json: {}, settings_json: { completed: true }, device_snapshot_json: {} })
    if (path === '/api/v1/profile') return json({ detail: 'profile_not_found' }, 404)
    if (path === '/api/v1/assets/portrait') return json({ kind: 'portrait', items: [] })
    if (path === '/api/v1/avatar/active') return json({ detail: 'avatar.not_found' }, 404)
    if (path === '/api/v1/memories' && request.method() === 'GET') return json({ items: memories })
    if (path === '/api/v1/memories' && request.method() === 'POST') {
      const body = request.postDataJSON()
      const item = { id: memories.length + 1, content: body.content, source: 'manual', source_session_id: null, created_at: '2026-10-06T00:00:00Z', edited: true }
      memories = [item, ...memories]
      return json(item, 201)
    }
    if (path === '/api/v1/memory-candidates' && request.method() === 'GET') return json({ items: candidates })
    if (path === '/api/v1/memory-candidates/confirm') {
      const item = { id: memories.length + 1, content: candidates[0].content, source: 'conversation', source_session_id: 8, created_at: '2026-10-06T00:00:00Z', edited: false }
      memories = [item, ...memories]; candidates = []
      return json(item)
    }
    if (path === '/api/v1/memory-candidates/reject') { candidates = []; return json({ rejected: true }) }
    return json({ ok: true })
  })
}

for (const target of [
  { width: 1920, height: 1080, mode: 'standard' },
  { width: 420, height: 720, mode: 'ultratall' },
  { width: 2160, height: 3500, mode: 'ultratall' },
  { width: 3840, height: 180, mode: 'strip' },
]) {
  test(`UX10 ${target.width}x${target.height} 使用 ${target.mode} 舞台且没有裸露空白`, async ({ page }) => {
    await page.setViewportSize({ width: target.width, height: target.height })
    await page.goto('/?preview=1')
    const stage = page.locator('.experience')
    await expect(stage).toHaveAttribute('data-layout', target.mode)
    await expect(page.getByTestId('scene-background')).toBeVisible()
    await expect(page.getByRole('button', { name: '开始对话' })).toBeVisible()
    await expect(page.getByRole('button', { name: '设置' })).toBeVisible()
    const geometry = await page.evaluate(() => {
      const stage = document.querySelector('.experience')!.getBoundingClientRect()
      const background = document.querySelector('.scene-background')!.getBoundingClientRect()
      return {
        stage: [stage.left, stage.top, stage.right, stage.bottom],
        background: [background.left, background.top, background.right, background.bottom],
        overflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth,
        overflowY: document.documentElement.scrollHeight - document.documentElement.clientHeight,
      }
    })
    expect(geometry.background).toEqual(geometry.stage)
    expect(geometry.overflowX).toBeLessThanOrEqual(0)
    expect(geometry.overflowY).toBeLessThanOrEqual(0)
  })
}

test('UX10 四个本地背景可切换并跨刷新保存', async ({ page }) => {
  await installContracts(page)
  await page.goto('/?preview=1')
  await page.getByRole('button', { name: '设置' }).click()
  await page.getByRole('button', { name: '人物', exact: true }).click()
  const radios = page.getByRole('radio', { name: /蓝调客厅|清晨卧室|雨夜书房|花园阳光房/ })
  await expect(radios).toHaveCount(4)
  await page.getByRole('radio', { name: /雨夜书房/ }).click()
  await expect(page.locator('.experience')).toHaveAttribute('data-background', 'rainy-library')
  await page.reload()
  await expect(page.locator('.experience')).toHaveAttribute('data-background', 'rainy-library')
  await expect(page.getByTestId('scene-background')).toHaveCSS('background-image', /rainy-library\.webp/)
})

test('UX10 可手工新增记忆并显式确认候选', async ({ page }) => {
  await installContracts(page)
  await page.goto('/?preview=1')
  await page.getByRole('button', { name: '设置' }).click()
  await page.getByRole('button', { name: '记忆', exact: true }).click()
  await page.getByLabel('添加一条长期记忆').fill('我周末喜欢去公园散步')
  await page.getByRole('button', { name: '记住', exact: true }).click()
  await expect(page.getByText('我周末喜欢去公园散步')).toBeVisible()
  await expect(page.getByText(/手工记忆/)).toBeVisible()
  await expect(page.getByText('今天想早点休息')).toBeVisible()
  await page.getByRole('button', { name: '确认记住' }).click()
  await expect(page.getByText('今天想早点休息')).toBeVisible()
  await expect(page.getByText(/会话 8/).first()).toBeVisible()
  await expect(page.getByText('等待你确认')).toBeHidden()
})
