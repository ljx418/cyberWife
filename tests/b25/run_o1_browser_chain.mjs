/** Real browser ASR→LLM→TTS→AudioWorklet latency probe for B2.5-O1. */
import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { chromium } from '../../prototype/node_modules/playwright/index.mjs'

function wavPcm(file) {
  const wav = fs.readFileSync(file)
  if (wav.toString('ascii', 0, 4) !== 'RIFF' || wav.toString('ascii', 8, 12) !== 'WAVE') {
    throw new Error(`not a RIFF/WAVE file: ${file}`)
  }
  let offset = 12
  let format = null
  let data = null
  while (offset + 8 <= wav.length) {
    const id = wav.toString('ascii', offset, offset + 4)
    const size = wav.readUInt32LE(offset + 4)
    const start = offset + 8
    if (id === 'fmt ') {
      format = {
        encoding: wav.readUInt16LE(start),
        channels: wav.readUInt16LE(start + 2),
        sampleRate: wav.readUInt32LE(start + 4),
        bits: wav.readUInt16LE(start + 14),
      }
    } else if (id === 'data') {
      data = wav.subarray(start, start + size)
    }
    offset = start + size + (size % 2)
  }
  if (!format || format.encoding !== 1 || format.channels !== 1 || format.sampleRate !== 16000 || format.bits !== 16) {
    throw new Error(`expected PCM16 mono 16kHz: ${file}`)
  }
  if (!data || data.length < 640) throw new Error(`empty PCM payload: ${file}`)
  return data.subarray(0, Math.floor(data.length / 640) * 640)
}

const root = path.resolve(import.meta.dirname, '../..')
const requested = Number(process.argv[2] || 1)
const outputDir = path.resolve(process.argv[3] || path.join(root, 'audit/v1/B2.5/O1'))
const webUrl = process.env.CW_TEST_WEB_URL || 'http://127.0.0.1:4173/?preview=1'
const corpusDir = path.join(root, 'audit/v1/B2/tts/cosyvoice')
const fixedAudio = process.env.CW_TEST_AUDIO_FILE
const corpusOffset = Number(process.env.CW_TEST_CORPUS_OFFSET || 0)
const turnTimeoutMs = Number(process.env.CW_TEST_TURN_TIMEOUT_MS || 180_000)
const recordingPolicy = process.env.CW_TEST_RECORDING_POLICY || 'standard'
if (!['standard', 'none'].includes(recordingPolicy)) {
  throw new Error(`invalid CW_TEST_RECORDING_POLICY: ${recordingPolicy}`)
}
const files = Array.from({ length: requested }, (_, index) => fixedAudio
  ? path.resolve(fixedAudio)
  : path.join(corpusDir, `${String(((index + corpusOffset) % 30) + 1).padStart(2, '0')}.wav`),
)
fs.mkdirSync(outputDir, { recursive: true })

const browser = await chromium.connectOverCDP(process.env.CW_CHROME_CDP || 'http://127.0.0.1:9222')
const context = browser.contexts()[0] || await browser.newContext()
const page = await context.newPage()
const cdp = await context.newCDPSession(page)
await cdp.send('Network.enable')
await cdp.send('Network.setCacheDisabled', { cacheDisabled: true })
await page.goto(webUrl)

const rows = []
for (let index = 0; index < files.length; index += 1) {
  const pcmB64 = wavPcm(files[index]).toString('base64')
  let result
  try {
    result = await page.evaluate(async ({ pcmB64, sampleIndex, turnTimeoutMs, recordingPolicy }) => {
    // The long-lived Windows Chrome used for hardware acceptance can retain a
    // prior Vite module graph. A unique URL guarantees this probe exercises
    // the checked-out MediaSession implementation rather than stale JS.
    const { MediaSession } = await import(`/src/services/MediaSession.ts?b25_acceptance=${Date.now()}`)
    await MediaSession.start()
    const created = await fetch('http://127.0.0.1:7860/api/v1/sessions', {
      method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ recording_policy: recordingPolicy }),
    }).then((response) => response.json())
    const sessionId = Number(created.id)
    const sessionRef = String(created.session_ref || created.id)
    const pcmText = atob(pcmB64)
    const pcm = new Uint8Array(pcmText.length)
    for (let i = 0; i < pcmText.length; i += 1) pcm[i] = pcmText.charCodeAt(i)

    let traceId = ''
    let generation = 0
    let transcriptSeen = false
    let eventCount = 0
    let audioChunks = 0
    let nonSilentChunks = 0
    let confirmationsSent = 0
    let lastConfirmation = null
    const receivedErrors = []
    const eventTail = []
    const socket = new WebSocket(`ws://127.0.0.1:7860/ws/v1/sessions/${sessionRef}`)
    socket.binaryType = 'arraybuffer'
    const finished = new Promise((resolve, reject) => {
      const timeout = window.setTimeout(() => reject(new Error(JSON.stringify({
        reason: `turn timeout ${sampleIndex}`,
        media: MediaSession.snapshot(),
        eventTail,
        eventCount,
        audioChunks,
        confirmationsSent,
        lastConfirmation,
        receivedErrors,
      }))), turnTimeoutMs)
      socket.onerror = () => reject(new Error(`websocket error ${sampleIndex}`))
      socket.onmessage = (message) => {
        const event = JSON.parse(message.data)
        eventCount += 1
        eventTail.push({ type: event.type, turn_id: event.turn_id, payload: event.payload })
        if (eventTail.length > 12) eventTail.shift()
        if (event.type === 'reply.audio.chunk') {
          audioChunks += 1
          const binary = atob(String(event.payload.audio_chunk_b64 || ''))
          const bytes = new Uint8Array(binary.length)
          for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i)
          if (new Int16Array(bytes.buffer).some((sample) => Math.abs(sample) >= 66)) nonSilentChunks += 1
        }
        if (event.type === 'error') receivedErrors.push(event.payload.code)
        void MediaSession.handleServerEvent(event, socket)
        if (event.type === 'transcript.final' && event.turn_id === 1) {
          transcriptSeen = true
          traceId = String(event.payload.trace_id)
          generation = Number(event.payload.generation)
        }
        if (
          transcriptSeen && event.type === 'state.changed' && event.turn_id === 1 &&
          event.payload.current === 'listening'
        ) {
          window.clearTimeout(timeout)
          resolve(undefined)
        }
      }
    })
    await new Promise((resolve, reject) => {
      socket.onopen = resolve
      socket.onerror = reject
    })
    const nativeSend = socket.send.bind(socket)
    socket.send = (data) => {
      if (typeof data === 'string') {
        try {
          const control = JSON.parse(data)
          if (control.type === 'audio.playback.started') {
            confirmationsSent += 1
            lastConfirmation = control
          }
        } catch {}
      }
      nativeSend(data)
    }
    for (let offset = 0, chunk = 0; offset < pcm.length; offset += 640, chunk += 1) {
      const frame = new ArrayBuffer(646)
      const view = new DataView(frame)
      view.setUint32(0, 1, true)
      view.setUint16(4, chunk, true)
      new Uint8Array(frame, 6).set(pcm.subarray(offset, offset + 640))
      socket.send(frame)
    }
    socket.send(JSON.stringify({ type: 'audio.silence', turn_id: 1, event_seq: 1 }))
    await finished

    let sample = null
    const deadline = Date.now() + 15_000
    while (Date.now() < deadline) {
      const snapshot = await fetch('http://127.0.0.1:7860/api/v1/runtime/metrics').then((r) => r.json())
      sample = snapshot.latency.samples.find((item) => item.trace_id === traceId) || null
      if (sample?.complete) break
      await new Promise((resolve) => setTimeout(resolve, 100))
    }
    socket.close()
    await MediaSession.stop()
    if (!sample?.complete) throw new Error(JSON.stringify({
      reason: 'browser confirmation missing', sampleIndex, eventCount, audioChunks,
      nonSilentChunks, confirmationsSent, lastConfirmation, receivedErrors,
    }))
    return {
      sample_index: sampleIndex,
      trace_id: traceId,
      session_id: sessionId,
      turn_id: 1,
      generation,
      event_count: eventCount,
      audio_chunks: audioChunks,
      non_silent_chunks: nonSilentChunks,
      confirmations_sent: confirmationsSent,
      bucket: sample.bucket,
      asr_to_llm_playable_ms: sample.asr_to_llm_playable_ms,
      llm_playable_to_tts_first_packet_ms: sample.llm_playable_to_tts_first_packet_ms,
      tts_first_packet_to_browser_ms: sample.tts_first_packet_to_browser_ms,
      asr_to_browser_first_non_silent_ms: sample.asr_to_browser_first_non_silent_ms,
      complete: sample.complete,
    }
    }, { pcmB64, sampleIndex: index + 1, turnTimeoutMs, recordingPolicy })
  } catch (error) {
    await page.close().catch(() => {})
    await browser.close().catch(() => {})
    throw error
  }
  rows.push(result)
  process.stdout.write(`${JSON.stringify(result)}\n`)
}

const runtimeSnapshot = await page.evaluate(() =>
  fetch('http://127.0.0.1:7860/api/v1/runtime/metrics').then((response) => response.json()),
)
const health = await page.evaluate(() =>
  fetch('http://127.0.0.1:7860/api/v1/health').then((response) => response.json()),
)
const percentile = (values, q) => {
  const ordered = [...values].sort((a, b) => a - b)
  const position = (ordered.length - 1) * q
  const lower = Math.floor(position)
  const upper = Math.ceil(position)
  if (lower === upper) return Number(ordered[lower].toFixed(3))
  return Number((ordered[lower] * (upper - position) + ordered[upper] * (position - lower)).toFixed(3))
}
const totals = rows.map((row) => row.asr_to_browser_first_non_silent_ms)
const observedBuckets = [...new Set(rows.map((row) => row.bucket))]
const metrics = {
  schema_version: 1,
  bucket: observedBuckets.length === 1 ? observedBuckets[0] : 'mixed',
  sample_count: rows.length,
  complete_count: rows.filter((row) => row.complete).length,
  p50_ms: percentile(totals, 0.5),
  p95_ms: percentile(totals, 0.95),
  cache_hit_count: rows.filter((row) => row.bucket === 'cache-hit').length,
  config_invalid_count: rows.filter((row) => row.bucket === 'config-invalid').length,
  runtime_collector_sample_count: runtimeSnapshot.latency.buckets.normal.sample_count,
  resources_after: health.resources,
}
fs.writeFileSync(path.join(outputDir, 'samples.json'), `${JSON.stringify(rows, null, 2)}\n`)
fs.writeFileSync(path.join(outputDir, 'metrics.json'), `${JSON.stringify(metrics, null, 2)}\n`)
const fields = [
  'sample_index', 'trace_id', 'session_id', 'turn_id', 'generation', 'event_count',
  'audio_chunks', 'non_silent_chunks', 'confirmations_sent', 'bucket',
  'asr_to_llm_playable_ms', 'llm_playable_to_tts_first_packet_ms',
  'tts_first_packet_to_browser_ms', 'asr_to_browser_first_non_silent_ms', 'complete',
]
fs.writeFileSync(
  path.join(outputDir, 'samples.csv'),
  `${fields.join(',')}\n${rows.map((row) => fields.map((field) => row[field]).join(',')).join('\n')}\n`,
)
await page.close()
await browser.close()
