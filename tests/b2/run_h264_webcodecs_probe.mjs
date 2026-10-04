/** Real Windows Chrome + WSL NVENC/WebSocket + WebCodecs acceptance probe. */
import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { chromium } from '../../prototype/node_modules/playwright/index.mjs'

const root = path.resolve(import.meta.dirname, '../..')
const output = path.resolve(process.argv[2] || path.join(root, 'audit/v1/B2/avatar-recovery/h264-webcodecs.json'))
const cdp = process.env.CW_CHROME_CDP || 'http://127.0.0.1:9235'
fs.mkdirSync(path.dirname(output), { recursive: true })

const browser = await chromium.connectOverCDP(cdp)
const context = browser.contexts()[0] || await browser.newContext()
const page = await context.newPage()
await page.goto('http://127.0.0.1:4173/?preview=1')
const result = await page.evaluate(async () => {
  const { AvatarSessionController } = await import('/src/services/AvatarSession.ts')
  const canvas = document.createElement('canvas')
  document.body.append(canvas)
  const snapshots = []
  const session = new AvatarSessionController({ pollIntervalMs: 250, reconnectMaxMs: 2000 })
  const unsubscribe = session.subscribe(value => snapshots.push(value))
  const activeAvatar = await fetch('http://127.0.0.1:7860/api/v1/avatar/active').then(response => response.json())
  const startedAt = performance.now()
  await session.start(canvas, activeAvatar.avatar_id)
  const readyAt = performance.now()
  const first = session.snapshot()
  await new Promise(resolve => setTimeout(resolve, 5000))
  const final = session.snapshot()
  const elapsed = performance.now() - readyAt
  const clientFps = (final.decodedFrames - first.decodedFrames) * 1000 / elapsed
  const metrics = final.sessionId
    ? await fetch(`http://127.0.0.1:8010/api/v1/media/${final.sessionId}/metrics`).then(response => response.json())
    : null
  const context2d = canvas.getContext('2d')
  const pixels = context2d && canvas.width && canvas.height
    ? context2d.getImageData(0, 0, Math.min(canvas.width, 64), Math.min(canvas.height, 64)).data
    : new Uint8ClampedArray()
  const pixelSum = pixels.reduce((sum, value) => sum + value, 0)
  const value = {
    measured_at: new Date().toISOString(),
    user_agent: navigator.userAgent,
    active_avatar: {
      avatar_id: activeAvatar.avatar_id,
      source_sha256: activeAvatar.source_sha256,
      frame_count: activeAvatar.frame_count,
    },
    secure_context: window.isSecureContext,
    video_decoder_available: typeof VideoDecoder !== 'undefined',
    ready_ms: Math.round(readyAt - startedAt),
    initial: first,
    final,
    canvas: { width: canvas.width, height: canvas.height, sample_sum: pixelSum },
    client_wallfps: Number(clientFps.toFixed(3)),
    client_fps: final.mediaFps,
    server_metrics: metrics?.data || null,
    state_trace: snapshots,
  }
  value.pass = first.state === 'ready' && final.state === 'ready' &&
    final.decodedFrames > first.decodedFrames && value.client_fps >= 25 &&
    final.decoderBacklog <= 3 &&
    value.canvas.width > 0 && value.canvas.height > 0 && pixelSum > 0 &&
    value.server_metrics?.video_codec === 'h264_nvenc' &&
    value.server_metrics?.video_queue_limit === 2 &&
    value.server_metrics?.late_video_frames_dropped === 0
  unsubscribe()
  await session.stop()
  value.post_stop = {
    hidden: canvas.hidden,
    opacity: canvas.style.opacity,
    layer: canvas.dataset.avatarLayer,
  }
  value.pass = value.pass && value.post_stop.hidden === true &&
    value.post_stop.opacity === '0' && value.post_stop.layer === 'static'
  canvas.remove()
  return value
})

fs.writeFileSync(output, `${JSON.stringify(result, null, 2)}\n`)
process.stdout.write(`${JSON.stringify(result, null, 2)}\n`)
await page.close()
await browser.close()
process.exit(result.pass ? 0 : 1)
