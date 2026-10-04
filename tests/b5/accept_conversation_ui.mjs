import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { chromium } from '../../prototype/node_modules/playwright/index.mjs'

const arg = name => { const i = process.argv.indexOf(name); return i >= 0 ? process.argv[i + 1] : undefined }
const evidence = path.resolve(arg('--evidence') || 'audit/v1/B5/B5.4A-conversation')
const cdp = arg('--cdp') || 'http://127.0.0.1:9225'
fs.mkdirSync(evidence, { recursive: true })
const sha = value => crypto.createHash('sha256').update(String(value)).digest('hex')

const browser = await chromium.connectOverCDP(cdp)
const context = browser.contexts()[0] || await browser.newContext()
const page = await context.newPage()
const events = []
const controls = []
let binaryFrames = 0
let invalidBinaryFrames = 0
let gatewaySocket = null

page.on('websocket', socket => {
  if (!socket.url().includes('/ws/v1/sessions/')) return
  gatewaySocket = socket.url()
  socket.on('framesent', frame => {
    if (typeof frame.payload === 'string') {
      try { controls.push(JSON.parse(frame.payload)) } catch { controls.push({ type: 'invalid-json' }) }
    } else {
      binaryFrames += 1
      if (frame.payload.length !== 646) invalidBinaryFrames += 1
    }
  })
  socket.on('framereceived', frame => {
    if (typeof frame.payload !== 'string') return
    try {
      const item = JSON.parse(frame.payload)
      events.push({
        type: item.type,
        turn_id: item.turn_id,
        event_seq: item.event_seq,
        state: item.payload?.current,
        reason: item.payload?.reason,
        text_sha256: item.payload?.text ? sha(item.payload.text) : item.payload?.text_final ? sha(item.payload.text_final) : undefined,
      })
    } catch { events.push({ type: 'invalid-json' }) }
  })
})

let result
try {
  await page.goto('http://127.0.0.1:4173/?preview=1&acceptance=b54a', { waitUntil: 'networkidle' })
  await page.locator('.voice-button').click()
  await page.waitForFunction(() => window.__CYBERWIFE_SESSION__?.input().activeTracks === 1, null, { timeout: 15000 })
  await page.waitForFunction(() => {
    const debug = window.__CYBERWIFE_SESSION__
    return debug && debug.avatar().decodedFrames > 0
  }, null, { timeout: 20000 })
  await page.waitForFunction(() => {
    const debug = window.__CYBERWIFE_SESSION__
    return debug && document.querySelector('[data-testid="live-subtitle"]')?.textContent?.length > 0
  }, null, { timeout: 20000 })
  const deadline = Date.now() + 120000
  while (Date.now() < deadline) {
    const completed = events.filter(item => item.type === 'reply.audio.complete').length
    const playbackEnded = controls.filter(item => item.type === 'audio.playback.ended').length
    if (completed >= 3 && playbackEnded >= 3 && await page.locator('.voice-button').getAttribute('aria-label') === '结束对话') break
    await page.waitForTimeout(250)
  }
  const completedAtDeadline = events.filter(item => item.type === 'reply.audio.complete').length
  const endedAtDeadline = controls.filter(item => item.type === 'audio.playback.ended').length
  if (completedAtDeadline < 3 || endedAtDeadline < 3) {
    throw new Error(`three complete browser playbacks not observed: complete=${completedAtDeadline}, ended=${endedAtDeadline}`)
  }
  await page.waitForFunction(() => document.querySelector('.voice-button')?.getAttribute('aria-label') === '结束对话', null, { timeout: 15000 })
  const beforeStop = await page.evaluate(() => ({
    input: window.__CYBERWIFE_SESSION__.input(),
    avatar: window.__CYBERWIFE_SESSION__.avatar(),
  }))
  const transcriptFinals = events.filter(item => item.type === 'transcript.final')
  const replyFinals = events.filter(item => item.type === 'reply.text.final')
  const audioChunks = events.filter(item => item.type === 'reply.audio.chunk')
  const audioComplete = events.filter(item => item.type === 'reply.audio.complete')
  const playbackStarted = controls.filter(item => item.type === 'audio.playback.started')
  const playbackEnded = controls.filter(item => item.type === 'audio.playback.ended')
  await page.screenshot({ path: path.join(evidence, 'main-stage.png'), fullPage: true })
  await page.locator('.voice-button').click()
  await page.waitForFunction(() => window.__CYBERWIFE_SESSION__.input().activeTracks === 0)
  const afterStop = await page.evaluate(() => window.__CYBERWIFE_SESSION__.input())
  const sequences = events.map(item => item.event_seq).filter(Number.isInteger)
  const strictSequence = sequences.every((value, index) => index === 0 || value > sequences[index - 1])
  result = {
    schema_version: 1,
    evidence_level: 'windows_chrome_fake_device_authorized_real_wav_real_models',
    gateway_socket: gatewaySocket,
    binary_frames: binaryFrames,
    invalid_binary_frames: invalidBinaryFrames,
    turns: {
      transcript_finals: transcriptFinals.length,
      reply_finals: replyFinals.length,
      audio_complete: audioComplete.length,
      transcript_hashes: transcriptFinals.map(item => item.text_sha256),
      reply_hashes: replyFinals.map(item => item.text_sha256),
    },
    playback: { audio_chunks: audioChunks.length, started: playbackStarted.length, ended: playbackEnded.length },
    event_seq_strict: strictSequence,
    before_stop: beforeStop,
    after_stop: afterStop,
    event_manifest: events
      .filter(item => !['reply.audio.chunk', 'reply.text.delta'].includes(item.type))
      .map(({ text_sha256, ...item }) => ({ ...item, has_text_hash: Boolean(text_sha256) })),
  }
  result.pass = Boolean(
    gatewaySocket && binaryFrames > 0 && invalidBinaryFrames === 0 &&
    transcriptFinals.length >= 3 && replyFinals.length >= 3 && audioComplete.length >= 3 &&
    audioChunks.length > 0 && playbackStarted.length >= 3 && playbackEnded.length >= 3 &&
    strictSequence && beforeStop.input.activeTracks === 1 && beforeStop.avatar.decodedFrames > 0 &&
    afterStop.activeTracks === 0 && afterStop.contextState === 'closed'
  )
} catch (error) {
  result = { schema_version: 1, pass: false, error: String(error), events: events.length, binary_frames: binaryFrames }
} finally {
  fs.writeFileSync(path.join(evidence, 'result.json'), JSON.stringify(result, null, 2) + '\n')
  await page.close().catch(() => {})
  await browser.close().catch(() => {})
}

console.log(JSON.stringify(result, null, 2))
process.exit(result.pass ? 0 : 2)
