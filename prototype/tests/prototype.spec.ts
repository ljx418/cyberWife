import { expect, test } from '@playwright/test'

test('首次设置授权门槛与主对话状态可用', async ({ page }) => {
  await page.goto('/')
  const continueButton = page.getByRole('button', { name: '继续' })
  await expect(continueButton).toBeDisabled()
  await page.getByRole('checkbox').check()
  await expect(continueButton).toBeEnabled()

  await page.goto('/?preview=1')
  await expect(page.getByRole('heading', { name: '你回来啦。' })).toBeVisible()
  await expect(page.getByRole('button', { name: '开始对话' })).toBeVisible()
  await expect(page.getByRole('button', { name: '设置' })).toBeVisible()
})

test('用户引导完成照片到动态形象的预览确认闭环', async ({ page }) => {
  let idlePolls = 0
  let approved = false
  await page.route('http://127.0.0.1:7860/api/v1/**', async (route) => {
    const request = route.request()
    const path = new URL(request.url()).pathname
    const json = (body: unknown, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
    if (path === '/api/v1/onboarding/draft' && request.method() === 'GET') return json({ id: 1, consent_granted: false, step_completed: 0, asset_consent_at: null, profile_draft_json: {}, settings_json: {}, device_snapshot_json: {}, updated_at: '2026-10-05T00:00:00Z' })
    if (path === '/api/v1/profile') return json({ detail: 'profile_not_found' }, 404)
    if (path === '/api/v1/health') return json({ status: 'ready', components: { llm: { status: 'ready' }, avatar: { status: 'ready' } }, resources: { vram_used_gb: 1, vram_total_gb: 24, ram_used_gb: 4, ram_total_gb: 32, disk_free_gb: 100 }, version: { app: 'test', schema: 'test' } })
    if (path === '/api/v1/assets/portrait' && request.method() === 'GET') return json({ kind: 'portrait', items: [{ id: 7, is_active: true }] })
    if (path === '/api/v1/avatar/active') return json({ id: 9, engine: 'wav2lip', avatar_id: 'static', source_sha256: 'a', status: 'active' })
    if (path === '/api/v1/consents' || (path === '/api/v1/onboarding/draft' && request.method() === 'PUT')) return json({ ok: true })
    if (path === '/api/v1/assets/portrait/preview') return json({ id: 7, entity_id_hash: 'private', mime: 'image/png', size_bytes: 20 })
    if (path === '/api/v1/assets/7/avatar-builds') return json({ id: 9, asset_id: 7, engine: 'wav2lip', avatar_id: 'static', source_sha256: 'a', status: 'ready' }, 202)
    if (path === '/api/v1/avatar-builds/9/activate') return json({ id: 9, asset_id: 7, engine: 'wav2lip', avatar_id: 'static', source_sha256: 'a', status: 'active', frame_size: [512, 768], face_box: [100, 400, 80, 320] })
    if (path === '/api/v1/avatar-builds/9/idle-generation' && request.method() === 'POST') return json({ derivative_id: 9, status: 'generating', phase: 'generating_frontal_portrait', progress: 25, has_frontal_preview: false, has_video_preview: false, updated_at: 'r1' }, 202)
    if (path === '/api/v1/avatar-builds/9/idle-generation' && request.method() === 'GET') {
      idlePolls += 1
      return json({ derivative_id: 9, status: 'awaiting_approval', phase: 'visual_review', progress: 100, has_frontal_preview: true, has_video_preview: true, updated_at: `r${idlePolls + 1}` })
    }
    if (path.endsWith('/idle-generation/frontal')) return route.fulfill({ status: 200, contentType: 'image/png', body: Buffer.from('89504e470d0a1a0a', 'hex') })
    if (path.endsWith('/idle-generation/video')) return route.fulfill({ status: 200, contentType: 'video/mp4', body: '' })
    if (path.endsWith('/idle-generation/approve')) {
      approved = true
      return json({ id: 9, asset_id: 7, engine: 'wav2lip', avatar_id: 'wav2lip256_idle_p_a_b', source_sha256: 'a', status: 'active' })
    }
    return json({ ok: true })
  })

  await page.goto('/')
  await page.getByRole('checkbox').check()
  await page.getByRole('button', { name: '继续' }).click()
  await page.getByRole('button', { name: '继续' }).click()
  await page.locator('input[type="file"]').setInputFiles({ name: 'portrait.png', mimeType: 'image/png', buffer: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=', 'base64') })
  await page.getByRole('button', { name: '生成动态形象' }).click()
  await expect(page.getByText('启用前人工检查')).toBeVisible({ timeout: 8_000 })
  await expect(page.getByText('10 秒首尾闭环待机')).toBeVisible()
  await page.getByRole('button', { name: '确认并使用动态形象' }).click()
  await expect(page.getByText('当前动态形象')).toBeVisible()
  expect(approved).toBe(true)
})

test('设置、记忆删除确认和主题切换可用', async ({ page }) => {
  await page.route('http://127.0.0.1:7860/api/v1/memories*', async (route) => {
    if (route.request().method() === 'DELETE') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ deleted: 1 }) })
      return
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: [{
          id: 41,
          content: '周末希望留出一段不被打扰的休息时间。',
          source_session_id: 'local-e2e',
          created_at: '2026-10-04T08:00:00+08:00',
          edited: false,
        }],
      }),
    })
  })
  await page.goto('/?preview=1')
  await page.getByRole('button', { name: '设置' }).click()
  await expect(page.getByRole('dialog', { name: '她的世界' })).toBeVisible()

  await page.getByRole('button', { name: '记忆', exact: true }).click()
  const memory = page.getByRole('article').filter({ hasText: '周末希望留出' })
  await expect(memory).toBeVisible()
  await memory.getByRole('button', { name: '删除' }).click()
  await expect(page.getByRole('alertdialog')).toBeVisible()
  await page.getByRole('button', { name: '取消' }).click()

  await page.getByRole('button', { name: '人物', exact: true }).click()
  await expect(page.getByRole('dialog', { name: '她的世界' }).getByText('选择授权照片')).toBeVisible()
  await page.getByRole('radio', { name: '柔和浅色' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'soft-light')
})

test('浏览器媒体合同只为首个非静音 PCM 回传一次播放确认', async ({ page }) => {
  await page.addInitScript(() => {
    class DeterministicAudioContext {
      state = 'running'
      currentTime = 0
      destination = {}
      audioWorklet = { addModule: async () => undefined }
      createBuffer(_channels: number, length: number, sampleRate: number) {
        const channel = new Float32Array(length)
        return { duration: length / sampleRate, getChannelData: () => channel }
      }
      createBufferSource() {
        return {
          buffer: null,
          onended: null as null | (() => void),
          connect: () => undefined,
          disconnect: () => undefined,
          start() { queueMicrotask(() => this.onended?.()) },
          stop() { this.onended?.() },
        }
      }
      async resume() { this.state = 'running' }
      async close() { this.state = 'closed' }
    }
    class DeterministicAudioWorkletNode {
      port = { postMessage: () => undefined, onmessage: null }
      connect() { return undefined }
    }
    Object.defineProperty(window, 'AudioContext', { value: DeterministicAudioContext, configurable: true })
    Object.defineProperty(window, 'AudioWorkletNode', { value: DeterministicAudioWorkletNode, configurable: true })
  })
  await page.goto('/?preview=1')
  await page.evaluate(async () => {
    const { MediaSession } = await import('/src/services/MediaSession.ts')
    const encode = (value: number) => {
      const bytes = new Uint8Array(640)
      const view = new DataView(bytes.buffer)
      for (let index = 0; index < 320; index += 1) view.setInt16(index * 2, value, true)
      let binary = ''
      bytes.forEach((byte) => { binary += String.fromCharCode(byte) })
      return btoa(binary)
    }
    ;(window as any).__runAudioProbe = async () => {
      const sent: string[] = []
      const socket = { readyState: WebSocket.OPEN, send: (value: string) => sent.push(value) } as WebSocket
      const common = {
        type: 'reply.audio.chunk', session_id: '7', turn_id: 3,
        payload: {
          trace_id: '01HZX5K2C3D4E5F6G7H8J9K0A1', generation: 2,
          asr_final_wall_ms: Date.now() - 10_000, sample_rate: 16000,
          server_elapsed_ms: 100,
        },
      }
      await MediaSession.start()
      await MediaSession.handleServerEvent({
        ...common, payload: { ...common.payload, audio_chunk_b64: encode(0) },
      }, socket)
      await new Promise((resolve) => setTimeout(resolve, 80))
      const afterSilence = sent.length
      await MediaSession.handleServerEvent({
        ...common, payload: { ...common.payload, audio_chunk_b64: encode(1200) },
      }, socket)
      await MediaSession.handleServerEvent({
        ...common, payload: { ...common.payload, audio_chunk_b64: encode(1200) },
      }, socket)
      await new Promise((resolve) => setTimeout(resolve, 200))
      await MediaSession.stop()
      return { afterSilence, sent: sent.map((item) => JSON.parse(item)) }
    }
    const button = document.createElement('button')
    button.id = 'run-audio-probe'
    button.textContent = 'run audio probe'
    button.onclick = () => {
      ;(window as any).__audioProbePromise = (window as any).__runAudioProbe()
    }
    document.body.appendChild(button)
  })
  await page.locator('#run-audio-probe').click()
  const result = await page.evaluate(() => (window as any).__audioProbePromise)
  expect(result.afterSilence).toBe(0)
  expect(result.sent).toHaveLength(1)
  expect(result.sent[0]).toMatchObject({
    type: 'audio.playback.started', session_id: '7', turn_id: 3, generation: 2,
  })
  expect(result.sent[0].asr_to_playback_ms).toBeGreaterThanOrEqual(100)
  expect(result.sent[0].asr_to_playback_ms).toBeLessThan(1000)
})

test('打断只停止旧 generation 且不关闭 AudioContext', async ({ page }) => {
  await page.goto('/?preview=1')
  const result = await page.evaluate(async () => {
    const { MediaSession } = await import('/src/services/MediaSession.ts')
    const bytes = new Uint8Array(640)
    const view = new DataView(bytes.buffer)
    for (let index = 0; index < 320; index += 1) view.setInt16(index * 2, 1200, true)
    let binary = ''
    bytes.forEach((byte) => { binary += String.fromCharCode(byte) })
    const socket = { readyState: WebSocket.OPEN, send: () => undefined } as unknown as WebSocket
    const common = {
      session_id: '9', turn_id: 4,
      payload: {
        audio_chunk_b64: btoa(binary), trace_id: '01HZX5K2C3D4E5F6G7H8J9K0A2',
        generation: 7, asr_final_wall_ms: Date.now(), sample_rate: 16000,
        server_elapsed_ms: 1,
      },
    }
    await MediaSession.start()
    for (let index = 0; index < 20; index += 1) {
      await MediaSession.handleServerEvent({ type: 'reply.audio.chunk', ...common }, socket)
    }
    const before = MediaSession.snapshot()
    const started = performance.now()
    await MediaSession.handleServerEvent({
      type: 'turn.cancelled', session_id: '9', turn_id: 4,
      payload: { cancelled_generation: 7 },
    }, socket)
    const elapsedMs = performance.now() - started
    const after = MediaSession.snapshot()
    await MediaSession.stop()
    return { before, after, elapsedMs }
  })
  expect(result.before.activeSources).toBeGreaterThan(0)
  expect(result.after.activeSources).toBe(0)
  expect(result.after.contextState).not.toBe('closed')
  expect(result.elapsedMs).toBeLessThan(100)
})

test('Avatar 停止或降级后透明画布让写真立即恢复而非黑屏', async ({ page }) => {
  await page.route('http://127.0.0.1:8011/healthz', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ status: 'ready', protocol: 'avatar-control-v1' }),
  }))
  await page.goto('/?preview=1')
  const result = await page.evaluate(async () => {
    Object.defineProperty(window, 'VideoDecoder', { value: undefined, configurable: true })
    const { AvatarSessionController } = await import('/src/services/AvatarSession.ts')
    const canvas = document.createElement('canvas')
    canvas.width = 64
    canvas.height = 64
    document.body.appendChild(canvas)
    const controller = new AvatarSessionController({
      controlUrl: 'http://127.0.0.1:8011',
      pollIntervalMs: 10_000,
    })
    await controller.start(canvas, 'wav2lip256_p_deadbeefdeadbeef')
    const degraded = {
      hidden: canvas.hidden,
      opacity: canvas.style.opacity,
      layer: canvas.dataset.avatarLayer,
      state: controller.snapshot().state,
    }
    await controller.stop()
    return {
      degraded,
      stopped: {
        hidden: canvas.hidden,
        opacity: canvas.style.opacity,
        layer: canvas.dataset.avatarLayer,
        state: controller.snapshot().state,
      },
    }
  })
  expect(result.degraded).toMatchObject({ hidden: true, opacity: '0', layer: 'static', state: 'static_fallback' })
  expect(result.stopped).toMatchObject({ hidden: true, opacity: '0', layer: 'static', state: 'stopped' })
})
