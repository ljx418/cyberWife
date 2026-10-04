/** Browser contract for the product AvatarSession lifecycle. */
import process from 'node:process'
import { chromium } from '../../prototype/node_modules/playwright/index.mjs'

const webUrl = process.env.CW_TEST_WEB_URL || 'http://127.0.0.1:4173/?preview=1'
const browser = await chromium.connectOverCDP(process.env.CW_CHROME_CDP || 'http://127.0.0.1:9222')
const context = browser.contexts()[0] || await browser.newContext()
const page = await context.newPage()
await page.goto(webUrl)

const result = await page.evaluate(async () => {
  const originalFetch = window.fetch
  const originalWebSocket = window.WebSocket
  const originalVideoDecoder = window.VideoDecoder
  let healthy = true
  let connections = 0
  let closes = 0

  class FakeVideoDecoder {
    static async isConfigSupported(config) { return { supported: true, config } }
    state = 'unconfigured'
    decodeQueueSize = 0
    constructor(callbacks) { this.callbacks = callbacks }
    configure() { this.state = 'configured' }
    decode() {
      this.callbacks.output({ displayWidth: 32, displayHeight: 32, close() {} })
    }
    close() { this.state = 'closed' }
  }

  class FakeWebSocket {
    static OPEN = 1
    readyState = 1
    binaryType = 'blob'
    onmessage = null
    onerror = null
    onclose = null
    constructor() {
      connections += 1
      const sessionId = `s-${connections}`
      setTimeout(() => {
        this.onmessage?.({ data: JSON.stringify({
          type: 'video.config', version: 1, session_id: sessionId,
          codec: 'avc1.42E01F', format: 'annexb', fps: 25,
          queue_limit: 2, audio: 'gateway-pcm',
        }) })
        setTimeout(() => {
          const frame = new ArrayBuffer(15)
          const bytes = new Uint8Array(frame); bytes[0] = 1; bytes[1] = 1
          this.onmessage?.({ data: frame })
        }, 5)
      }, 5)
    }
    close() { closes += 1; this.readyState = 3 }
  }

  window.WebSocket = FakeWebSocket
  window.VideoDecoder = FakeVideoDecoder
  window.fetch = async (input) => {
    const url = String(input)
    if (url.endsWith('/health')) {
      if (!healthy) throw new TypeError('avatar offline')
      return new Response(JSON.stringify({ status: 'ready' }), { status: 200 })
    }
    throw new Error(`unexpected fetch ${url}`)
  }

  try {
    const { AvatarSessionController } = await import('/src/services/AvatarSession.ts')
    let reloads = 0
    window.addEventListener('beforeunload', () => { reloads += 1 })
    const states = []
    const session = new AvatarSessionController({
      baseUrl: 'http://127.0.0.1:8010',
      pollIntervalMs: 30,
      reconnectMaxMs: 60,
    })
    session.subscribe((snapshot) => states.push(snapshot.state))
    const canvas = document.createElement('canvas')
    canvas.getContext = () => ({ drawImage() {} })
    await session.start(canvas)
    const first = session.snapshot()
    healthy = false
    await new Promise((resolve) => setTimeout(resolve, 80))
    const fallback = session.snapshot()
    healthy = true
    await new Promise((resolve) => setTimeout(resolve, 180))
    const recovered = session.snapshot()
    await session.stop()
    const connectionsAtStop = connections
    await new Promise((resolve) => setTimeout(resolve, 100))
    let invalidRejected = false
    try { new AvatarSessionController({ baseUrl: 'https://example.com' }) } catch { invalidRejected = true }
    return {
      first, fallback, recovered, states, connections, closes, connectionsAtStop,
      noReconnectAfterStop: connections === connectionsAtStop,
      invalidRejected, reloads,
    }
  } finally {
    window.fetch = originalFetch
    window.WebSocket = originalWebSocket
    window.VideoDecoder = originalVideoDecoder
  }
})

const pass = result.first.state === 'ready' &&
  result.fallback.state === 'static_fallback' &&
  result.recovered.state === 'ready' &&
  result.recovered.connectionGeneration >= 2 &&
  result.invalidRejected && result.noReconnectAfterStop && result.reloads === 0
process.stdout.write(`${JSON.stringify({ ...result, pass }, null, 2)}\n`)
await browser.close()
process.exit(pass ? 0 : 1)
