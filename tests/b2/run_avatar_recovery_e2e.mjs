/** Real Chrome + Gateway + CosyVoice + Wav2Lip H.264 failure/recovery acceptance. */
import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { execFileSync, spawn } from 'node:child_process'
import { chromium } from '../../prototype/node_modules/playwright/index.mjs'

const root = path.resolve(import.meta.dirname, '../..')
const outputDir = path.resolve(process.argv[2] || path.join(root, 'audit/v1/B2/avatar-recovery'))
const webUrl = process.env.CW_TEST_WEB_URL || 'http://127.0.0.1:4173/?preview=1'
const cycles = Number(process.env.CW_AVATAR_RECOVERY_CYCLES || 3)
const inputWav = path.join(root, 'audit/v1/B2/tts/cosyvoice/17.wav')
const killScript = 'C:\\workSpace\\cyberWife\\tests\\b2\\KillOwnedAvatar.ps1'
const launcher = 'C:\\workSpace\\cyberWife\\ops\\windows\\RuntimeLauncher.ps1'
fs.mkdirSync(outputDir, { recursive: true })

function wavPcm(file) {
  const wav = fs.readFileSync(file)
  if (wav.toString('ascii', 0, 4) !== 'RIFF' || wav.toString('ascii', 8, 12) !== 'WAVE') throw new Error('invalid WAV')
  let offset = 12; let fmt; let data
  while (offset + 8 <= wav.length) {
    const id = wav.toString('ascii', offset, offset + 4)
    const size = wav.readUInt32LE(offset + 4)
    const start = offset + 8
    if (id === 'fmt ') fmt = { encoding: wav.readUInt16LE(start), channels: wav.readUInt16LE(start + 2), rate: wav.readUInt32LE(start + 4), bits: wav.readUInt16LE(start + 14) }
    if (id === 'data') data = wav.subarray(start, start + size)
    offset = start + size + (size % 2)
  }
  if (!fmt || fmt.encoding !== 1 || fmt.channels !== 1 || fmt.rate !== 16000 || fmt.bits !== 16 || !data) throw new Error('expected PCM16 mono 16kHz')
  return data.subarray(0, Math.floor(data.length / 640) * 640)
}

function ps(args, timeout = 300_000) {
  return execFileSync('powershell.exe', ['-NoProfile', ...args], { encoding: 'utf8', timeout }).trim()
}

function psDetached(args) {
  const child = spawn('powershell.exe', ['-NoProfile', ...args], {
    detached: true,
    stdio: 'ignore',
  })
  child.unref()
  return { launched: true, pid: child.pid }
}

const browser = await chromium.connectOverCDP(process.env.CW_CHROME_CDP || 'http://127.0.0.1:9222')
const context = browser.contexts()[0] || await browser.newContext()
const page = await context.newPage()
const cdp = await context.newCDPSession(page)
await cdp.send('Network.enable')
await cdp.send('Network.setCacheDisabled', { cacheDisabled: true })
let navigationCount = 0
page.on('framenavigated', frame => { if (frame === page.mainFrame()) navigationCount += 1 })
await page.exposeFunction('b2KillOwnedAvatar', () => JSON.parse(ps(['-File', killScript])))
await page.exposeFunction('b2RecoverRuntime', () => psDetached([
  '-File', launcher, '-Action', 'recover', '-Component', 'avatar',
]))
await page.goto(webUrl)
const pcmB64 = wavPcm(inputWav).toString('base64')

const result = await page.evaluate(async ({ pcmB64, cycles }) => {
  const cacheKey = Date.now()
  const { MediaSession } = await import(`/src/services/MediaSession.ts?b2_acceptance=${cacheKey}`)
  const { AvatarSession } = await import(`/src/services/AvatarSession.ts?b2_acceptance=${cacheKey}`)
  const canvas = document.createElement('canvas')
  document.body.append(canvas)
  await MediaSession.start()
  await AvatarSession.start(canvas)
  const avatarTransitions = []
  const unsubscribeAvatar = AvatarSession.subscribe(snapshot => avatarTransitions.push(snapshot))

  const waitFor = async (predicate, timeoutMs, label) => {
    const deadline = Date.now() + timeoutMs
    while (Date.now() < deadline) {
      const value = await predicate()
      if (value) return value
      await new Promise(resolve => setTimeout(resolve, 100))
    }
    throw new Error(`timeout: ${label}`)
  }
  await waitFor(() => AvatarSession.snapshot().state === 'ready', 120_000, 'initial Avatar ready')
  const pcmText = atob(pcmB64)
  const pcm = new Uint8Array(pcmText.length)
  for (let i = 0; i < pcmText.length; i += 1) pcm[i] = pcmText.charCodeAt(i)
  const created = await fetch('http://127.0.0.1:7860/api/v1/sessions', { method: 'POST', headers: { 'content-type': 'application/json' }, body: '{}' }).then(r => r.json())
  const sessionId = Number(created.id)
  const socket = new WebSocket(`ws://127.0.0.1:7860/ws/v1/sessions/${sessionId}`)
  socket.binaryType = 'arraybuffer'
  await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject })
  let active = null
  socket.onmessage = message => {
    const event = JSON.parse(message.data)
    void MediaSession.handleServerEvent(event, socket)
    const turn = active
    if (!turn || event.turn_id !== turn.turnId) return
    turn.events += 1
    if (event.type === 'reply.audio.chunk') {
      AvatarSession.setGeneration(Number(event.payload.generation), event.session_id)
      turn.audioChunks += 1
      const raw = atob(String(event.payload.audio_chunk_b64 || ''))
      const bytes = new Uint8Array(raw.length)
      for (let i = 0; i < raw.length; i += 1) bytes[i] = raw.charCodeAt(i)
      if (new Int16Array(bytes.buffer).some(sample => Math.abs(sample) >= 66)) turn.nonSilent += 1
      if (turn.kill && !turn.killPromise && turn.audioChunks >= 5) {
        turn.killRequestedAt = Date.now()
        turn.killPromise = window.b2KillOwnedAvatar().then(value => { turn.killResult = value; return value })
      }
      if (turn.killResult && Date.now() >= turn.killResult.offline_at_ms) turn.audioAfterKill += 1
    }
    if (event.type === 'reply.text.final') turn.textFinal = String(event.payload.text_final || '')
    if (event.type === 'media.state' && event.payload.mode === 'static_fallback') turn.fallbackAt = Date.now()
    if (event.type === 'error') turn.errors.push(event.payload.code)
    if (event.type === 'state.changed' && event.payload.current === 'listening') turn.resolve()
  }

  async function runTurn(turnId, kill) {
    const initialAvatar = AvatarSession.snapshot()
    const turn = { turnId, kill, events: 0, audioChunks: 0, nonSilent: 0, audioAfterKill: 0, textFinal: '', fallbackAt: null, killRequestedAt: null, killPromise: null, killResult: null, errors: [], decodedStart: initialAvatar.decodedFrames, decodedEnd: initialAvatar.decodedFrames, mediaFpsSamples: [], clientFpsSamples: [] }
    const done = new Promise((resolve, reject) => { turn.resolve = resolve; turn.reject = reject; setTimeout(() => reject(new Error(`turn ${turnId} timeout`)), 180_000) })
    active = turn
    const fpsSampler = window.setInterval(() => {
      const snapshot = AvatarSession.snapshot()
      turn.decodedEnd = snapshot.decodedFrames
      if (snapshot.decodedFrames - turn.decodedStart >= 10) {
        if (snapshot.mediaFps > 0) turn.mediaFpsSamples.push(snapshot.mediaFps)
        if (snapshot.clientFps > 0) turn.clientFpsSamples.push(snapshot.clientFps)
      }
    }, 100)
    for (let offset = 0, seq = 0; offset < pcm.length; offset += 640, seq += 1) {
      const frame = new ArrayBuffer(646); const view = new DataView(frame)
      view.setUint32(0, turnId, true); view.setUint16(4, seq, true)
      new Uint8Array(frame, 6).set(pcm.subarray(offset, offset + 640)); socket.send(frame)
    }
    socket.send(JSON.stringify({ type: 'audio.silence', turn_id: turnId, event_seq: turnId }))
    await done
    window.clearInterval(fpsSampler)
    const finalAvatar = AvatarSession.snapshot()
    turn.decodedEnd = finalAvatar.decodedFrames
    if (turn.killPromise) await turn.killPromise
    active = null
    delete turn.resolve; delete turn.reject; delete turn.killPromise
    return turn
  }

  const rows = []
  let turnId = 1
  for (let cycle = 1; cycle <= cycles; cycle += 1) {
    const beforeGeneration = AvatarSession.snapshot().connectionGeneration
    const transitionStart = avatarTransitions.length
    const fault = await runTurn(turnId++, true)
    await waitFor(() => AvatarSession.snapshot().state === 'static_fallback', 10_000, `cycle ${cycle} client fallback`)
    const fallbackSnapshot = AvatarSession.snapshot()
    await window.b2RecoverRuntime()
    const recovered = await waitFor(() => {
      const snapshot = AvatarSession.snapshot()
      return snapshot.state === 'ready' && snapshot.connectionGeneration > beforeGeneration ? snapshot : null
    }, 180_000, `cycle ${cycle} reconnect`)
    const recovery = await runTurn(turnId++, false)
    const clientSnapshot = AvatarSession.snapshot()
    const percentile50 = values => {
      if (!values.length) return 0
      const ordered = [...values].sort((a, b) => a - b)
      return ordered[Math.floor((ordered.length - 1) * 0.5)]
    }
    const clientFps = percentile50(recovery.mediaFpsSamples)
    const clientWallFps = percentile50(recovery.clientFpsSamples)
    const firstFallback = avatarTransitions.slice(transitionStart).find(snapshot =>
      snapshot.state === 'static_fallback' && snapshot.changedAtMs >= fault.killRequestedAt)
    const metrics = await fetch(`http://127.0.0.1:8010/api/v1/media/${recovered.sessionId}/metrics`).then(r => r.json())
    rows.push({
      cycle,
      before_generation: beforeGeneration,
      fallback_snapshot: fallbackSnapshot,
      recovered_snapshot: recovered,
      fault_turn: fault,
      recovery_turn: recovery,
      fallback_ms: firstFallback && fault.killResult?.requested_at_ms ? firstFallback.changedAtMs - fault.killResult.requested_at_ms : null,
      pipeline_fallback_ms: fault.fallbackAt && fault.killResult?.requested_at_ms ? fault.fallbackAt - fault.killResult.requested_at_ms : null,
      client_finalfps: Number(Number(clientFps || 0).toFixed(3)),
      client_wallfps: Number(Number(clientWallFps || 0).toFixed(3)),
      client_decoded_frames: recovery.decodedEnd - recovery.decodedStart,
      decoder_backlog: clientSnapshot.decoderBacklog,
      server_metrics: metrics.data,
    })
  }
  socket.close()
  unsubscribeAvatar()
  await AvatarSession.stop()
  await MediaSession.stop()
  return { rows, avatar_final: AvatarSession.snapshot() }
}, { pcmB64, cycles })

result.navigation_count = navigationCount
result.reload_count = Math.max(0, navigationCount - 1)
for (const row of result.rows) {
  row.pass = row.fault_turn.killResult?.marker_validated === true &&
    row.fallback_ms !== null && row.fallback_ms <= 2000 &&
    row.fault_turn.audioAfterKill > 0 && row.fault_turn.textFinal.length > 0 &&
    row.recovery_turn.audioChunks > 0 && row.recovery_turn.textFinal.length > 0 &&
    row.recovery_turn.fallbackAt === null && row.client_finalfps >= 25 &&
    row.decoder_backlog <= 3 &&
    Number(row.server_metrics?.late_video_frames_dropped || 0) === 0 &&
    Number(row.server_metrics?.inferfps || 0) >= 25
}
result.pass = result.rows.length === cycles && result.rows.every(row => row.pass) && result.reload_count === 0
fs.writeFileSync(path.join(outputDir, 'result.json'), `${JSON.stringify(result, null, 2)}\n`)
process.stdout.write(`${JSON.stringify(result, null, 2)}\n`)
await page.close(); await browser.close()
process.exit(result.pass ? 0 : 1)
