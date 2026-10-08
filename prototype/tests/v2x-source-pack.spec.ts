import { expect, test, type Page, type Route } from '@playwright/test'

const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGNgYGAAAAAEAAEnNCcKAAAAAElFTkSuQmCC', 'base64')

async function installContracts(page: Page, enabled = true) {
  const sources: Array<Record<string, unknown>> = []
  const uploads: string[] = []
  await page.route('http://127.0.0.1:7860/api/v1/**', async (route: Route) => {
    const request = route.request()
    const path = new URL(request.url()).pathname
    const json = (body: unknown, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
    if (path === '/api/v1/experience/settings') return json({ schema_version: 1, features: { source_pack: enabled } })
    if (path === '/api/v1/onboarding/draft') return json({ id: 1, consent_granted: true, step_completed: 5, profile_draft_json: {}, settings_json: { completed: true }, device_snapshot_json: {} })
    if (path === '/api/v1/profile') return json({ id: 1, name: '小雅', user_nickname: '你', persona: '', relationship_context: '', example_dialogue: '', version: 1, updated_at: '2026-10-08T00:00:00Z' })
    if (path === '/api/v1/health') return json({ status: 'ready', components: {}, resources: {}, version: {} })
    if (path === '/api/v1/assets/portrait') return json({ kind: 'portrait', items: [] })
    if (path === '/api/v1/avatar/active') return json({ detail: 'avatar.not_found' }, 404)
    if (path === '/api/v1/source-pack' && request.method() === 'GET') return json({ schema_version: 1, pack_id: 'pack-1', revision: sources.length, sources })
    if (path === '/api/v1/source-pack/sources' && request.method() === 'POST') {
      const body = request.postDataBuffer()?.toString('utf8') || ''
      uploads.push(body)
      const front = body.includes('front')
      const index = sources.length + 1
      const source = {
        source_id: `source-${index}`,
        sha256: `${index}`.repeat(64),
        angle: front ? 'front' : 'full_body',
        appearance_label: front ? '蓝白碎花上衣' : '红色长裙',
        consent_id: 'consent-1',
        provenance: 'local_upload',
        created_at: '2026-10-08T00:00:00Z',
        content_url: `/api/v1/source-pack/sources/source-${index}/content`,
      }
      sources.push(source)
      return json({ schema_version: 1, pack_id: 'pack-1', revision: sources.length, sources, source, created: true })
    }
    if (path.includes('/source-pack/sources/') && path.endsWith('/content')) return route.fulfill({ status: 200, contentType: 'image/png', body: png })
    return json({ ok: true })
  })
  return { sources, uploads }
}

test('X1多选照片后逐张标注并串行导入真实素材清单', async ({ page }) => {
  const contracts = await installContracts(page, true)
  await page.goto('/?preview=1')
  await page.getByRole('button', { name: '设置' }).click()
  await page.getByRole('button', { name: '素材', exact: true }).click()
  await page.getByLabel('选择多张授权照片').setInputFiles([
    { name: 'front.png', mimeType: 'image/png', buffer: png },
    { name: 'full.png', mimeType: 'image/png', buffer: png },
  ])
  await page.getByLabel('front.png 拍摄角度').selectOption('front')
  await page.getByLabel('front.png 穿着标签').fill('蓝白碎花上衣')
  await page.getByLabel('full.png 拍摄角度').selectOption('full_body')
  await page.getByLabel('full.png 穿着标签').fill('红色长裙')
  await page.getByRole('button', { name: '导入 2 张素材' }).click()
  await expect(page.getByText('2 张已授权源图')).toBeVisible()
  await expect(page.getByRole('img', { name: 'front · 蓝白碎花上衣' })).toBeVisible()
  await expect(page.getByRole('img', { name: 'full_body · 红色长裙' })).toBeVisible()
  expect(contracts.uploads).toHaveLength(2)
  expect(contracts.uploads[0]).toContain('蓝白碎花上衣')
  expect(contracts.uploads[0]).toContain('front')
  expect(contracts.uploads[1]).toContain('红色长裙')
  expect(contracts.uploads[1]).toContain('full_body')
})

test('X1 feature flag关闭时不暴露素材入口且V1人物入口保留', async ({ page }) => {
  await installContracts(page, false)
  await page.goto('/?preview=1')
  await page.getByRole('button', { name: '设置' }).click()
  await expect(page.getByRole('button', { name: '素材', exact: true })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '人物', exact: true })).toBeVisible()
  await expect(page.getByText('人物形象')).toBeVisible()
})
