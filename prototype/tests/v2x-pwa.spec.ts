import { expect, test, type Page } from '@playwright/test'

async function installContracts(page: Page, enabled = true) {
  await page.route('http://127.0.0.1:7860/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname
    const json = (body: unknown, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
    if (path === '/api/v1/experience/settings') return json({ schema_version: 1, features: { pwa: enabled } })
    if (path === '/api/v1/onboarding/draft') return json({ id: 1, consent_granted: true, step_completed: 5, profile_draft_json: {}, settings_json: { completed: true }, device_snapshot_json: {} })
    if (path === '/api/v1/profile') return json({ id: 1, name: '小雅', user_nickname: '你', persona: '', relationship_context: '', example_dialogue: '', version: 1, updated_at: '2026-10-08T00:00:00Z' })
    if (path === '/api/v1/health') return json({ status: 'ready', components: {}, resources: {}, version: {} })
    if (path === '/api/v1/assets/portrait') return json({ kind: 'portrait', items: [] })
    if (path === '/api/v1/avatar/active') return json({ detail: 'avatar.not_found' }, 404)
    return json({ ok: true })
  })
}

test('X9 manifest具备桌面安装所需元数据与双尺寸图标', async ({ request }) => {
  const response = await request.get('/manifest.webmanifest')
  expect(response.ok()).toBe(true)
  const manifest = await response.json()
  expect(manifest).toMatchObject({
    name: 'cyberWife 本地数字伴侣',
    start_url: '/?source=pwa',
    scope: '/',
    display: 'standalone',
  })
  expect(manifest.icons.map((item: { sizes: string }) => item.sizes)).toEqual(['192x192', '512x512'])
  for (const icon of manifest.icons) expect((await request.get(icon.src)).ok()).toBe(true)
})

test('X9安装和全屏均渐进增强，状态跟随浏览器事件', async ({ page }) => {
  await page.addInitScript(() => {
    ;(window as any).__installPromptCount = 0
  })
  await installContracts(page, true)
  await page.goto('/?preview=1')
  await expect(page.getByRole('button', { name: '进入全屏' })).toBeVisible()
  await page.evaluate(() => {
    let fullscreen: Element | null = null
    Object.defineProperty(document, 'fullscreenElement', { configurable: true, get: () => fullscreen })
    Object.defineProperty(document.documentElement, 'requestFullscreen', { configurable: true, value: async () => {
      fullscreen = document.documentElement
      document.dispatchEvent(new Event('fullscreenchange'))
    } })
    Object.defineProperty(document, 'exitFullscreen', { configurable: true, value: async () => {
      fullscreen = null
      document.dispatchEvent(new Event('fullscreenchange'))
    } })
  })
  await page.getByRole('button', { name: '进入全屏' }).click()
  await expect(page.getByRole('button', { name: '退出全屏' })).toBeVisible()
  await page.getByRole('button', { name: '退出全屏' }).click()
  await expect(page.getByRole('button', { name: '进入全屏' })).toBeVisible()

  await page.evaluate(() => {
    const event = new Event('beforeinstallprompt', { cancelable: true }) as Event & { prompt: () => Promise<void>; userChoice: Promise<{ outcome: 'accepted' }> }
    event.prompt = async () => { (window as any).__installPromptCount += 1 }
    event.userChoice = Promise.resolve({ outcome: 'accepted' })
    window.dispatchEvent(event)
  })
  await page.getByRole('button', { name: '安装到桌面' }).click()
  await expect(page.getByText('已添加到桌面')).toBeVisible()
  expect(await page.evaluate(() => (window as any).__installPromptCount)).toBe(1)
})

test('X9 Service Worker只缓存公开壳并拒绝API与鉴权请求', async ({ page }) => {
  await installContracts(page, true)
  await page.goto('/?preview=1')
  await page.evaluate(async () => { await navigator.serviceWorker.ready })
  if (!await page.evaluate(() => Boolean(navigator.serviceWorker.controller))) {
    await page.reload()
    await page.evaluate(async () => { await navigator.serviceWorker.ready })
  }
  const entries = await page.evaluate(async () => {
    await fetch('/backgrounds/blue-hour-living.webp')
    await fetch('/api/v1/private-memory', { headers: { Authorization: 'Bearer should-never-cache' } }).catch(() => undefined)
    const names = await caches.keys()
    const urls: string[] = []
    for (const name of names) {
      for (const request of await (await caches.open(name)).keys()) urls.push(new URL(request.url).pathname)
    }
    return { names, urls }
  })
  expect(entries.names).toEqual(['cyberwife-public-shell-v1'])
  expect(entries.urls).toContain('/index.html')
  expect(entries.urls).toContain('/manifest.webmanifest')
  expect(entries.urls).toContain('/backgrounds/blue-hour-living.webp')
  expect(entries.urls.some((path) => path.startsWith('/api/'))).toBe(false)
})

test('X9 feature flag关闭时隐藏桌面控制且保留原入口', async ({ page }) => {
  await installContracts(page, false)
  await page.goto('/?preview=1')
  await expect(page.getByRole('button', { name: '进入全屏' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '开始对话' })).toBeVisible()
  await expect(page.getByRole('button', { name: '设置' })).toBeVisible()
})
