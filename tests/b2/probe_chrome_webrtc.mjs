/** Real Windows Chrome -> WSL Avatar WebRTC probe. Writes only sanitized ICE metadata. */
import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { chromium } from '../../prototype/node_modules/playwright/index.mjs'

const cdpUrl = process.env.CW_CHROME_CDP || 'http://127.0.0.1:9223'
const avatarUrl = process.env.CW_AVATAR_URL || 'http://127.0.0.1:8010'
const output = path.resolve(process.argv[2] || 'audit/v1/B2/avatar-recovery/chrome-default.json')
fs.mkdirSync(path.dirname(output), { recursive: true })

const browser = await chromium.connectOverCDP(cdpUrl)
const context = browser.contexts()[0] || await browser.newContext()
const page = await context.newPage()
await page.goto(`${avatarUrl}/health`)

const result = await page.evaluate(async ({ avatarUrl }) => {
  const startedAt = performance.now()
  const timeline = []
  const record = (event, value) => timeline.push({ ms: Math.round(performance.now() - startedAt), event, value })
  const pc = new RTCPeerConnection({ iceServers: [] })
  const candidates = []
  const video = document.createElement('video')
  video.autoplay = true
  video.muted = true
  video.playsInline = true
  document.body.append(video)
  let frames = 0
  let firstFrameMs = null
  let frameStart = null
  let frameEnd = null
  const countFrame = (now) => {
    frames += 1
    firstFrameMs ??= Math.round(performance.now() - startedAt)
    frameStart ??= now
    frameEnd = now
    video.requestVideoFrameCallback(countFrame)
  }
  video.requestVideoFrameCallback(countFrame)
  for (const name of ['connectionstatechange', 'iceconnectionstatechange', 'icegatheringstatechange', 'signalingstatechange']) {
    pc.addEventListener(name, () => record(name, {
      connection: pc.connectionState,
      iceConnection: pc.iceConnectionState,
      iceGathering: pc.iceGatheringState,
      signaling: pc.signalingState,
    }))
  }
  pc.addEventListener('icecandidate', event => {
    if (!event.candidate) return
    const parsed = event.candidate
    candidates.push({
      type: parsed.type || 'unknown',
      protocol: parsed.protocol || 'unknown',
      addressClass: parsed.address?.endsWith('.local') ? 'mdns' :
        parsed.address?.includes(':') ? 'ipv6' : 'ipv4',
    })
  })
  pc.addEventListener('track', event => {
    record('track', event.track.kind)
    if (event.track.kind === 'video') {
      video.srcObject = event.streams[0] || new MediaStream([event.track])
      void video.play().catch(error => record('video-play-error', error.name))
    }
  })
  pc.addTransceiver('audio', { direction: 'recvonly' })
  pc.addTransceiver('video', { direction: 'recvonly' })

  let answer = null
  let error = null
  try {
    await pc.setLocalDescription(await pc.createOffer())
    if (pc.iceGatheringState !== 'complete') {
      await Promise.race([
        new Promise(resolve => pc.addEventListener('icegatheringstatechange', () => {
          if (pc.iceGatheringState === 'complete') resolve()
        })),
        new Promise(resolve => setTimeout(resolve, 5000)),
      ])
    }
    record('offer-ready', { iceGathering: pc.iceGatheringState })
    const response = await fetch(`${avatarUrl}/offer`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(pc.localDescription),
    })
    if (!response.ok) throw new Error(`offer HTTP ${response.status}`)
    answer = await response.json()
    await pc.setRemoteDescription({ type: answer.type, sdp: answer.sdp })
    const deadline = performance.now() + 15000
    while (!['connected', 'failed', 'closed'].includes(pc.connectionState) && performance.now() < deadline) {
      await new Promise(resolve => setTimeout(resolve, 100))
    }
    if (pc.connectionState === 'connected') await new Promise(resolve => setTimeout(resolve, 5000))
  } catch (caught) {
    error = `${caught?.name || 'Error'}: ${caught?.message || String(caught)}`
  }
  const fps = frames > 1 && frameEnd > frameStart ? (frames - 1) * 1000 / (frameEnd - frameStart) : 0
  const summary = {
    measured_at: new Date().toISOString(),
    user_agent: navigator.userAgent,
    browser_brand: navigator.userAgentData?.brands || [],
    webcodecs: {
      video_decoder: typeof VideoDecoder !== 'undefined',
      secure_context: window.isSecureContext,
    },
    offer_http_ok: Boolean(answer?.sdp && answer?.sessionid),
    session_id_present: Boolean(answer?.sessionid),
    candidate_summary: candidates.reduce((acc, item) => {
      const key = `${item.type}/${item.protocol}/${item.addressClass}`
      acc[key] = (acc[key] || 0) + 1
      return acc
    }, {}),
    connection_state: pc.connectionState,
    ice_connection_state: pc.iceConnectionState,
    ice_gathering_state: pc.iceGatheringState,
    frames,
    first_frame_ms: firstFrameMs,
    client_fps: Number(fps.toFixed(3)),
    timeline,
    error,
  }
  summary.pass = summary.connection_state === 'connected' && summary.frames > 0
  pc.close()
  return summary
}, { avatarUrl })

fs.writeFileSync(output, `${JSON.stringify(result, null, 2)}\n`)
process.stdout.write(`${JSON.stringify(result, null, 2)}\n`)
await page.close()
await browser.close()
process.exit(result.pass ? 0 : 1)
