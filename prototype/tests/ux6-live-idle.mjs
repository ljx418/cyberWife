import { chromium } from '@playwright/test'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'

const output = path.resolve(process.argv[2] || '../audit/v1/UX6/live-idle-transition')
await mkdir(output, { recursive: true })

const browser = await chromium.launch({
  headless: true,
  args: ['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream'],
})
const context = await browser.newContext({ viewport: { width: 1366, height: 768 } })
await context.grantPermissions(['microphone'], { origin: 'http://127.0.0.1:7860' })
const page = await context.newPage()
const avatarSockets = []
page.on('websocket', (socket) => {
  if (socket.url().includes('/ws/v1/avatar')) avatarSockets.push(socket.url())
})

try {
  await page.goto('http://127.0.0.1:7860/?preview=1', { waitUntil: 'networkidle' })
  const activeAvatar = await page.evaluate(async () => {
    const response = await fetch('http://127.0.0.1:7860/api/v1/avatar/active')
    return response.json()
  })
  const idle = page.getByTestId('idle-avatar-video')
  await idle.waitFor({ state: 'attached', timeout: 15_000 })
  await page.waitForFunction(() => {
    const video = document.querySelector('[data-testid="idle-avatar-video"]')
    return video instanceof HTMLVideoElement && video.currentTime > 0.2
  }, null, { timeout: 15_000 })
  const idleBeforeLive = await idle.evaluate((video) => video.currentTime)

  await page.getByRole('button', { name: '开始对话' }).click()
  await page.waitForFunction(() => {
    const canvas = document.querySelector('.avatar-video')
    return canvas instanceof HTMLCanvasElement
      && canvas.dataset.avatarLayer === 'live'
      && !canvas.hidden
  }, null, { timeout: 30_000 })
  await page.screenshot({ path: path.join(output, '01-live.png'), fullPage: true })

  const live = await page.locator('.avatar-video').evaluate((canvas) => ({
    hidden: canvas.hidden,
    layer: canvas.dataset.avatarLayer,
    width: canvas.width,
    height: canvas.height,
    opacity: getComputedStyle(canvas).opacity,
  }))
  await page.getByRole('button', { name: '结束对话' }).click()
  await page.waitForFunction(() => {
    const canvas = document.querySelector('.avatar-video')
    return canvas instanceof HTMLCanvasElement
      && canvas.hidden
      && canvas.dataset.avatarLayer === 'static'
  }, null, { timeout: 10_000 })
  const idleAfterStop = await idle.evaluate((video) => video.currentTime)
  await page.waitForTimeout(900)
  const idleAfterWait = await idle.evaluate((video) => video.currentTime)
  await page.screenshot({ path: path.join(output, '02-idle-restored.png'), fullPage: true })
  const stopped = await page.locator('.avatar-video').evaluate((canvas) => ({
    hidden: canvas.hidden,
    layer: canvas.dataset.avatarLayer,
    opacity: getComputedStyle(canvas).opacity,
  }))
  const result = {
    page: 'http://127.0.0.1:7860/?preview=1',
    viewport: [1366, 768],
    active_avatar_id: activeAvatar.avatar_id,
    avatar_websockets: avatarSockets,
    idle_before_live_seconds: Number(idleBeforeLive.toFixed(3)),
    live,
    stopped,
    idle_after_stop_seconds: Number(idleAfterStop.toFixed(3)),
    idle_after_wait_seconds: Number(idleAfterWait.toFixed(3)),
    idle_advance_after_stop_seconds: Number((idleAfterWait - idleAfterStop).toFixed(3)),
    pass: live.layer === 'live'
      && !live.hidden
      && stopped.layer === 'static'
      && stopped.hidden
      && avatarSockets.some((url) => url.includes(`avatar_id=${activeAvatar.avatar_id}`))
      && idleAfterWait - idleAfterStop >= 0.7,
  }
  await writeFile(path.join(output, 'result.json'), `${JSON.stringify(result, null, 2)}\n`)
  console.log(JSON.stringify(result, null, 2))
  if (!result.pass) process.exitCode = 1
} finally {
  await browser.close()
}
