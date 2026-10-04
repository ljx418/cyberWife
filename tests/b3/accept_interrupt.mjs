/** B3-AC01: real Windows Chrome + real Gateway/model chain interruption evidence. */
import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { createHash } from 'node:crypto'
import { chromium } from '../../prototype/node_modules/playwright/index.mjs'

const root = path.resolve(import.meta.dirname, '../..')
const arg = name => {
  const index = process.argv.indexOf(name)
  return index >= 0 ? process.argv[index + 1] : undefined
}
const samples = Number(arg('--samples') || 30)
const evidence = path.resolve(arg('--evidence') || path.join(root, 'audit/v1/B3/AC01'))
const audioPath = path.resolve(arg('--audio') || path.join(root, 'audit/tts_nonstream_long_t1.wav'))
const webUrl = process.env.CW_TEST_WEB_URL || 'http://127.0.0.1:4173/?preview=1'
const moduleToken = `b54c-${Date.now()}`

function wavPcm(file) {
  const wav = fs.readFileSync(file)
  if (wav.toString('ascii', 0, 4) !== 'RIFF' || wav.toString('ascii', 8, 12) !== 'WAVE') throw new Error('invalid WAV')
  let offset = 12
  let format = null
  let pcm = null
  while (offset + 8 <= wav.length) {
    const id = wav.toString('ascii', offset, offset + 4)
    const size = wav.readUInt32LE(offset + 4)
    const start = offset + 8
    if (id === 'fmt ') format = { codec: wav.readUInt16LE(start), channels: wav.readUInt16LE(start + 2), rate: wav.readUInt32LE(start + 4), bits: wav.readUInt16LE(start + 14) }
    if (id === 'data') pcm = wav.subarray(start, start + size)
    offset = start + size + (size % 2)
  }
  if (!format || format.codec !== 1 || format.channels !== 1 || format.rate !== 16000 || format.bits !== 16 || !pcm) throw new Error('WAV must be PCM16/16kHz/mono')
  const padding = (640 - pcm.length % 640) % 640
  return Buffer.concat([pcm, Buffer.alloc(padding)])
}

const pcm = wavPcm(audioPath)
const browser = await chromium.connectOverCDP(process.env.CW_CHROME_CDP || 'http://127.0.0.1:9222')
const context = browser.contexts()[0] || await browser.newContext()
const page = await context.newPage()
await page.goto(webUrl)
await page.evaluate(async ({ moduleToken }) => {
  const { AvatarSession } = await import(`/src/services/AvatarSession.ts?b3=${moduleToken}`)
  await AvatarSession.start()
  if (AvatarSession.snapshot().state !== 'ready') throw new Error('AvatarSession is not ready')
}, { moduleToken })
const rows = []

for (let index = 0; index < samples; index += 1) {
  const bucket = ['early', 'mid', 'late'][index % 3]
  const delayMs = { early: 0, mid: 300, late: 700 }[bucket]
  const row = await page.evaluate(async ({ pcmBase64, bucket, delayMs, moduleToken }) => {
    const { MediaSession } = await import(`/src/services/MediaSession.ts?b3=${moduleToken}`)
    const { AvatarSession } = await import(`/src/services/AvatarSession.ts?b3=${moduleToken}`)
    const created = await fetch('http://127.0.0.1:7860/api/v1/sessions', {
      method: 'POST', headers: { 'content-type': 'application/json' }, body: '{}',
    })
    if (!created.ok) throw new Error(`session create failed: ${created.status}`)
    const session = await created.json()
    const sessionId = Number(session.id)
    const pcmBytes = Uint8Array.from(atob(pcmBase64), char => char.charCodeAt(0))
    const events = []
    let resolveOpen
    let resolveInitial
    let resolveFirstAudio
    let resolveDetected
    let resolveCancelled
    const opened = new Promise(resolve => { resolveOpen = resolve })
    const initial = new Promise(resolve => { resolveInitial = resolve })
    const firstAudio = new Promise(resolve => { resolveFirstAudio = resolve })
    const detected = new Promise(resolve => { resolveDetected = resolve })
    const cancelled = new Promise(resolve => { resolveCancelled = resolve })
    const socket = new WebSocket(`ws://127.0.0.1:7860/ws/v1/sessions/${sessionId}`)
    socket.binaryType = 'arraybuffer'
    socket.onopen = () => resolveOpen()
    let interruptSentAt = null
    let silenceObservedAt = null
    let detectedAt = null
    let cancelledAt = null
    let postDetectedOldAudio = 0
    let handledAudio = 0
    let rejectedAudio = 0
    const playbackErrors = []
    socket.onmessage = event => {
      const envelope = JSON.parse(event.data)
      events.push(envelope)
      if (envelope.type !== 'reply.audio.chunk') {
        if (envelope.type === 'barge_in.detected' || envelope.type === 'turn.cancelled') {
          const generation = Number(envelope.payload.generation ?? envelope.payload.cancelled_generation)
          AvatarSession.cancelGeneration(Number.isFinite(generation) ? generation : undefined, envelope.session_id)
        }
        void MediaSession.handleServerEvent(envelope, socket).then(() => {
          if (envelope.type === 'barge_in.detected') {
            detectedAt = performance.now()
            silenceObservedAt = performance.now()
            resolveDetected()
          }
        }).catch(error => playbackErrors.push(String(error)))
      }
      if (envelope.type === 'state.changed' && envelope.turn_id === null) resolveInitial()
      if (envelope.type === 'reply.audio.chunk') {
        AvatarSession.setGeneration(Number(envelope.payload.generation), envelope.session_id)
        if (detectedAt !== null && Number(envelope.payload.generation) === 1) postDetectedOldAudio += 1
        void MediaSession.handleServerEvent(envelope, socket).then(handled => {
          if (handled) {
            handledAudio += 1
            resolveFirstAudio()
          } else rejectedAudio += 1
        }).catch(error => playbackErrors.push(String(error)))
      }
      if (envelope.type === 'turn.cancelled') {
        cancelledAt = performance.now()
        resolveCancelled(envelope)
      }
    }
    await opened
    await initial
    for (let chunk = 0, offset = 0; offset < pcmBytes.length; chunk += 1, offset += 640) {
      const frame = new ArrayBuffer(646)
      const view = new DataView(frame)
      view.setUint32(0, 1, true)
      view.setUint16(4, chunk, true)
      new Uint8Array(frame, 6).set(pcmBytes.subarray(offset, offset + 640))
      socket.send(frame)
    }
    socket.send(JSON.stringify({ type: 'audio.silence', turn_id: 1, event_seq: 1 }))
    await Promise.race([firstAudio, new Promise((_, reject) => setTimeout(() => reject(new Error(`first audio timeout: ${JSON.stringify({ rejectedAudio, playbackErrors, snapshot: MediaSession.snapshot(), eventTypes: events.slice(-20).map(item => item.type) })}`)), 30000))])
    await new Promise(resolve => setTimeout(resolve, delayMs))
    const audibleDeadline = performance.now() + 5000
    while (MediaSession.snapshot().activeSources < 1 && performance.now() < audibleDeadline) {
      await new Promise(resolve => setTimeout(resolve, 2))
    }
    const sourcesBefore = MediaSession.snapshot().activeSources
    const avatarBefore = AvatarSession.snapshot()
    interruptSentAt = performance.now()
    socket.send(JSON.stringify({ type: 'barge_in.detected', turn_id: 1, event_seq: 2 }))
    await Promise.race([detected, new Promise((_, reject) => setTimeout(() => reject(new Error('barge event timeout')), 2000))])
    const snapshot = MediaSession.snapshot()
    const cancelledEvent = await Promise.race([cancelled, new Promise((_, reject) => setTimeout(() => reject(new Error('turn cancel timeout')), 2000))])
    await new Promise(resolve => setTimeout(resolve, 200))
    const avatarAfter = AvatarSession.snapshot()
    socket.close()
    await fetch(`http://127.0.0.1:7860/api/v1/sessions/${sessionId}`, { method: 'DELETE' })
    return {
      session_id: sessionId, bucket, sources_before: sourcesBefore,
      silence_ms: silenceObservedAt - interruptSentAt,
      acknowledgement_ms: cancelledAt - interruptSentAt,
      sources_after: snapshot.activeSources,
      audio_context_state: snapshot.contextState,
      post_detected_old_audio: postDetectedOldAudio,
      cancelled_generation: cancelledEvent.payload.cancelled_generation,
      component_errors: cancelledEvent.payload.component_errors,
      handled_audio: handledAudio,
      rejected_audio: rejectedAudio,
      playback_errors: playbackErrors,
      avatar_state: avatarAfter.state,
      avatar_decoded_before: avatarBefore.decodedFrames,
      avatar_decoded_after: avatarAfter.decodedFrames,
      avatar_generation_after: avatarAfter.mediaGeneration,
      avatar_stale_frames_dropped: avatarAfter.staleFramesDropped,
      avatar_decoder_backlog: avatarAfter.decoderBacklog,
      avatar_connection_generation_before: avatarBefore.connectionGeneration,
      avatar_connection_generation_after: avatarAfter.connectionGeneration,
      avatar_reconnect_attempts: avatarAfter.reconnectAttempts,
    }
  }, { pcmBase64: pcm.toString('base64'), bucket, delayMs, moduleToken })
  row.sample = index + 1
  row.pass = row.sources_before > 0 && row.silence_ms <= 400 && row.sources_after === 0 && row.audio_context_state !== 'closed' && row.post_detected_old_audio === 0 && row.cancelled_generation === 1 && row.component_errors.length === 0 && row.avatar_state === 'ready' && row.avatar_generation_after === 2 && row.avatar_connection_generation_after === row.avatar_connection_generation_before && row.avatar_reconnect_attempts === 0
  rows.push(row)
  process.stdout.write(`${JSON.stringify(row)}\n`)
}

await page.evaluate(async ({ moduleToken }) => {
  const { MediaSession } = await import(`/src/services/MediaSession.ts?b3=${moduleToken}`)
  const { AvatarSession } = await import(`/src/services/AvatarSession.ts?b3=${moduleToken}`)
  await MediaSession.stop()
  await AvatarSession.stop()
}, { moduleToken })
const sorted = rows.map(row => row.silence_ms).sort((a, b) => a - b)
const p95 = sorted[Math.max(0, Math.ceil(sorted.length * 0.95) - 1)]
const summary = {
  evidence_level: 'e2e_real_models_windows_chrome',
  browser: await browser.version(),
  audio_sha256: createHash('sha256').update(pcm).digest('hex'),
  samples: rows.length,
  passed: rows.filter(row => row.pass).length,
  silence_p95_ms: Number(p95.toFixed(3)),
  hard_limit_ms: 400,
  result: rows.every(row => row.pass) && p95 <= 400 ? 'PASS' : 'FAIL',
}
fs.mkdirSync(evidence, { recursive: true })
const headers = Object.keys(rows[0])
fs.writeFileSync(path.join(evidence, 'interrupt.csv'), `${headers.join(',')}\n${rows.map(row => headers.map(key => JSON.stringify(row[key])).join(',')).join('\n')}\n`)
fs.writeFileSync(path.join(evidence, 'result.json'), `${JSON.stringify({ summary, rows }, null, 2)}\n`)
fs.writeFileSync(path.join(evidence, 'manifest.json'), `${JSON.stringify({ schema_version: 1, command: 'node tests/b3/accept_interrupt.mjs --samples 30', summary }, null, 2)}\n`)
process.stdout.write(`SUMMARY ${JSON.stringify(summary)}\n`)
await page.close()
await browser.close()
if (summary.result !== 'PASS') process.exitCode = 2
