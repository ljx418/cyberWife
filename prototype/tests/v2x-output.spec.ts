import { expect, test } from '@playwright/test'

async function installAudioGraph(page: import('@playwright/test').Page, withSink = false) {
  await page.addInitScript((supportsSink) => {
    class NodeStub { connect(destination: unknown) { return destination } disconnect() {} }
    class SourceStub extends NodeStub { buffer: any = null; onended: null | (() => void) = null; start() {} stop() { this.onended?.() } }
    class ContextStub {
      state = 'running'; currentTime = 0; destination = {}; audioWorklet = { addModule: async () => undefined }
      createGain() { return Object.assign(new NodeStub(), { gain: { value: 1 } }) }
      createDynamicsCompressor() { return Object.assign(new NodeStub(), { threshold: { value: 0 }, knee: { value: 0 }, ratio: { value: 1 }, attack: { value: 0 }, release: { value: 0 } }) }
      createBuffer(_channels: number, length: number, sampleRate: number) { const channel = new Float32Array(length); return { duration: length / sampleRate, getChannelData: () => channel } }
      createBufferSource() { return new SourceStub() }
      async resume() { this.state = 'running' }
      async close() { this.state = 'closed' }
      async setSinkId(deviceId: string) { if (!supportsSink) throw new Error('unsupported'); (window as any).__sink = deviceId }
    }
    if (!supportsSink) delete (ContextStub.prototype as any).setSinkId
    class WorkletStub extends NodeStub { port = { postMessage: () => undefined, onmessage: null as any } }
    ;(window as any).AudioContext = ContextStub
    ;(window as any).AudioWorkletNode = WorkletStub
  }, withSink)
}

test('X0.3 音量静音可逆，当前回答可重播且打断清空', async ({ page }) => {
  await installAudioGraph(page)
  await page.goto('/?preview=1')
  const result = await page.evaluate(async () => {
    const { MediaSession } = await import('/src/services/MediaSession.ts')
    const pcm = new Int16Array(320); pcm.fill(1200)
    let binary = ''; new Uint8Array(pcm.buffer).forEach((byte) => { binary += String.fromCharCode(byte) })
    const sent: string[] = []
    const socket = { readyState: WebSocket.OPEN, send: (value: string) => sent.push(value) } as WebSocket
    const event = { type: 'reply.audio.chunk', session_id: 's1', turn_id: 1, payload: { audio_chunk_b64: btoa(binary), trace_id: 'trace-1', generation: 1, asr_final_wall_ms: Date.now(), sample_rate: 16000, server_elapsed_ms: 1 } }
    await MediaSession.start()
    MediaSession.setVolume(0.5); MediaSession.setMuted(true)
    const muted = MediaSession.snapshot()
    MediaSession.setMuted(false)
    await MediaSession.handleServerEvent(event, socket)
    const beforeReplay = { sent: sent.length, snapshot: MediaSession.snapshot() }
    const replayed = await MediaSession.replayCurrent()
    const afterReplay = { sent: sent.length, snapshot: MediaSession.snapshot() }
    MediaSession.cancelGeneration(1, 's1')
    const afterCancel = MediaSession.snapshot()
    await MediaSession.stop()
    return { muted, beforeReplay, replayed, afterReplay, afterCancel }
  })
  expect(result.muted.outputVolume).toBe(0.5)
  expect(result.muted.outputMuted).toBe(true)
  expect(result.beforeReplay.snapshot.replayAvailable).toBe(true)
  expect(result.replayed).toBe(true)
  expect(result.afterReplay.sent).toBe(result.beforeReplay.sent)
  expect(result.afterCancel.replayBytes).toBe(0)
  expect(result.afterCancel.replayAvailable).toBe(false)
})

test('X0.3 输出设备选择按浏览器能力明确降级', async ({ page }) => {
  await installAudioGraph(page, false)
  await page.goto('/?preview=1')
  const unsupported = await page.evaluate(async () => {
    const { MediaSession } = await import('/src/services/MediaSession.ts')
    const result = await MediaSession.setOutputDevice('speaker-1'); await MediaSession.stop(); return result
  })
  expect(unsupported).toBe('unsupported')

  const second = await page.context().newPage()
  await installAudioGraph(second, true)
  await second.goto('/?preview=1')
  const selected = await second.evaluate(async () => {
    const { MediaSession } = await import('/src/services/MediaSession.ts')
    const result = await MediaSession.setOutputDevice('speaker-2'); const sink = (window as any).__sink; await MediaSession.stop(); return { result, sink }
  })
  expect(selected).toEqual({ result: 'selected', sink: 'speaker-2' })
  await second.close()
})

test('X0.3 feature flag控制输出UI且不创建历史语音入口', async ({ page }) => {
  let enabled = true
  await page.route('http://127.0.0.1:7860/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname
    const json = (body: unknown, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
    if (path === '/api/v1/experience/settings') return json({ schema_version: 1, features: { output_controls: enabled } })
    if (path === '/api/v1/onboarding/draft') return json({ id: 1, consent_granted: true, step_completed: 4, profile_draft_json: {}, settings_json: { completed: true }, device_snapshot_json: {} })
    if (path === '/api/v1/profile') return json({ id: 1, name: '小雅', user_nickname: '你', persona: '', relationship_context: '', example_dialogue: '', version: 1, updated_at: '2026-10-08T00:00:00Z' })
    if (path === '/api/v1/health') return json({ status: 'ready', components: {}, resources: {}, version: {} })
    if (path === '/api/v1/assets/portrait') return json({ kind: 'portrait', items: [] })
    if (path === '/api/v1/avatar/active') return json({ detail: 'avatar.not_found' }, 404)
    return json({ ok: true })
  })
  await page.goto('/?preview=1')
  await expect(page.getByRole('group', { name: '声音输出控制' })).toBeVisible()
  await expect(page.getByRole('slider', { name: '输出音量' })).toBeVisible()
  await expect(page.getByRole('button', { name: '重播本次回答' })).toBeVisible()
  await expect(page.getByText(/历史语音库/)).toHaveCount(0)
  enabled = false
  await page.reload()
  await expect(page.getByRole('group', { name: '声音输出控制' })).toHaveCount(0)
})

test('X0.3 当前回答缓存超限时原子清空且不继续增长', async ({ page }) => {
  await page.goto('/?preview=1')
  const result = await page.evaluate(async () => {
    const { appendBoundedReplayChunk } = await import('/src/services/MediaSession.ts')
    const first = appendBoundedReplayChunk([], 0, new Int16Array(2), 16000, 8)
    const overflow = appendBoundedReplayChunk(first.chunks, first.bytes, new Int16Array(3), 16000, 8)
    return {
      firstBytes: first.bytes,
      firstCount: first.chunks.length,
      overflowBytes: overflow.bytes,
      overflowCount: overflow.chunks.length,
      overflowed: overflow.overflowed,
    }
  })
  expect(result).toEqual({
    firstBytes: 4,
    firstCount: 1,
    overflowBytes: 0,
    overflowCount: 0,
    overflowed: true,
  })
})
