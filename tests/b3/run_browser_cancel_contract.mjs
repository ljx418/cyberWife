/** Windows Chrome contract for generation-scoped WebAudio cancellation. */
import fs from 'node:fs'
import path from 'node:path'
import { chromium } from '../../prototype/node_modules/playwright/index.mjs'

const root = path.resolve(import.meta.dirname, '../..')
const output = path.resolve(process.argv[2] || path.join(root, 'audit/v1/B3/browser-cancel-contract.json'))
const browser = await chromium.connectOverCDP(process.env.CW_CHROME_CDP || 'http://127.0.0.1:9222')
const context = browser.contexts()[0] || await browser.newContext()
const page = await context.newPage()
await page.goto('http://127.0.0.1:4173/?preview=1')

const result = await page.evaluate(async () => {
  const { MediaSession } = await import('/src/services/MediaSession.ts')
  const encode = (value) => {
    const bytes = new Uint8Array(640)
    const view = new DataView(bytes.buffer)
    for (let index = 0; index < 320; index += 1) view.setInt16(index * 2, value, true)
    let binary = ''
    bytes.forEach((byte) => { binary += String.fromCharCode(byte) })
    return btoa(binary)
  }
  const sent = []
  const socket = { readyState: WebSocket.OPEN, send: value => sent.push(JSON.parse(value)) }
  const event = generation => ({
    type: 'reply.audio.chunk', session_id: '31', turn_id: generation,
    payload: {
      audio_chunk_b64: encode(1400), trace_id: `trace-${generation}`,
      generation, asr_final_wall_ms: Date.now(), sample_rate: 16000,
      server_elapsed_ms: 1,
    },
  })
  await MediaSession.start()
  for (let index = 0; index < 100; index += 1) {
    await MediaSession.handleServerEvent(event(7), socket)
  }
  const before = MediaSession.snapshot()
  const started = performance.now()
  await MediaSession.handleServerEvent({
    type: 'barge_in.detected', session_id: '31', turn_id: 7,
    payload: { active_turn_id: 7, cancelled_components: ['playback'] },
  }, socket)
  const cancelElapsedMs = performance.now() - started
  const afterCancel = MediaSession.snapshot()
  const staleAccepted = await MediaSession.handleServerEvent(event(7), socket)
  const freshAccepted = await MediaSession.handleServerEvent(event(8), socket)
  const afterFresh = MediaSession.snapshot()
  await MediaSession.stop()
  return { before, afterCancel, afterFresh, staleAccepted, freshAccepted, cancelElapsedMs }
})

result.browser = await browser.version()
result.pass = result.before.activeSources === 100 &&
  result.afterCancel.activeSources === 0 &&
  result.afterCancel.contextState !== 'closed' &&
  result.staleAccepted === false && result.freshAccepted === true &&
  result.cancelElapsedMs <= 100
fs.mkdirSync(path.dirname(output), { recursive: true })
fs.writeFileSync(output, `${JSON.stringify(result, null, 2)}\n`)
process.stdout.write(`${JSON.stringify(result, null, 2)}\n`)
await page.close()
await browser.close()
if (!result.pass) process.exitCode = 1
