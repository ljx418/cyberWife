import { expect, test } from '@playwright/test'

test('X0.1 校准阈值有界且突发噪声不支配中位噪声底', async ({ page }) => {
  await page.goto('/?preview=1')
  const result = await page.evaluate(async () => {
    const module = await import('/src/services/InputAudioSession.ts')
    const quiet = module.deriveInputCalibration(Array(100).fill(0.004), '2026-10-08T00:00:00Z')
    const fan = module.deriveInputCalibration([...Array(95).fill(0.014), ...Array(5).fill(0.8)], '2026-10-08T00:00:00Z')
    return { quiet, fan }
  })
  expect(result.quiet.voiceThreshold).toBeGreaterThanOrEqual(0.012)
  expect(result.quiet.bargeInThreshold).toBeGreaterThan(result.quiet.voiceThreshold)
  expect(result.fan.noiseP50).toBeCloseTo(0.014)
  expect(result.fan.voiceThreshold).toBeLessThanOrEqual(0.055)
  expect(result.fan.bargeInThreshold).toBeLessThanOrEqual(0.095)
})

test('X0.1 PTT未按不启动，按下可启动，释放结束并清状态', async ({ page }) => {
  await page.goto('/?preview=1')
  const result = await page.evaluate(async () => {
    const module = await import('/src/services/InputAudioSession.ts')
    const controller = new module.InputAudioSessionController() as any
    let starts = 0
    let ends = 0
    controller.callbacks = {
      onUtteranceStart: () => { starts += 1; return true },
      onFrame: () => undefined,
      onUtteranceEnd: () => { ends += 1 },
      onError: () => undefined,
    }
    controller.configure({ mode: 'push_to_talk' })
    for (let index = 0; index < 8; index += 1) controller.consumeFrame(new ArrayBuffer(640), 0.08)
    const beforePress = starts
    controller.setPushToTalk(true)
    for (let index = 0; index < 6; index += 1) controller.consumeFrame(new ArrayBuffer(640), 0.08)
    const afterPress = starts
    controller.setPushToTalk(false)
    return { beforePress, afterPress, ends, snapshot: controller.snapshot() }
  })
  expect(result.beforePress).toBe(0)
  expect(result.afterPress).toBe(1)
  expect(result.ends).toBe(1)
  expect(result.snapshot.pushToTalkActive).toBe(false)
  expect(result.snapshot.boundary.capturing).toBe(false)
})

test('X0.1 活动中换麦先停旧track，校准只返回统计摘要', async ({ page }) => {
  await page.goto('/?preview=1')
  const result = await page.evaluate(async () => {
    const active = new Set<any>()
    let maxActive = 0
    let requestedDevice: string | null = null
    Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: {
      enumerateDevices: async () => [
        { kind: 'audioinput', deviceId: 'default', label: '默认' },
        { kind: 'audioinput', deviceId: 'mic-2', label: 'USB麦克风' },
      ],
      getUserMedia: async (constraints: any) => {
        requestedDevice = constraints.audio.deviceId?.exact ?? null
        const track: any = { readyState: 'live', stop() { this.readyState = 'ended'; active.delete(this) } }
        active.add(track); maxActive = Math.max(maxActive, active.size)
        return { getTracks: () => [track] }
      },
    } })
    class MockNode { connect() { return this } disconnect() {} }
    class MockAnalyser extends MockNode {
      fftSize = 1024
      getFloatTimeDomainData(values: Float32Array) { values.fill(0.01) }
    }
    class MockContext {
      state = 'running'; destination = {}; audioWorklet = { addModule: async () => undefined }
      createMediaStreamSource() { return new MockNode() }
      createGain() { return Object.assign(new MockNode(), { gain: { value: 1 } }) }
      createAnalyser() { return new MockAnalyser() }
      async close() { this.state = 'closed' }
    }
    class MockWorklet extends MockNode { port = { onmessage: null as any } }
    ;(window as any).AudioContext = MockContext
    ;(window as any).AudioWorkletNode = MockWorklet
    const module = await import('/src/services/InputAudioSession.ts')
    const controller = new module.InputAudioSessionController()
    const callbacks = { onUtteranceStart: () => true, onFrame: () => undefined, onUtteranceEnd: () => undefined, onError: () => undefined }
    await controller.start(callbacks)
    await controller.selectDevice('mic-2')
    const switched = controller.snapshot()
    await controller.stop()
    const calibration = await controller.calibrate('mic-2', 500)
    const after = controller.snapshot()
    return { maxActive, requestedDevice, switched, calibration, after, activeCount: active.size }
  })
  expect(result.maxActive).toBe(1)
  expect(result.requestedDevice).toBe('mic-2')
  expect(result.switched.activeTracks).toBe(1)
  expect(result.calibration.sampleCount).toBeGreaterThanOrEqual(20)
  expect(result.after.activeTracks).toBe(0)
  expect(result.activeCount).toBe(0)
})

test('X0.1 换麦失败时恢复系统默认输入', async ({ page }) => {
  await page.goto('/?preview=1')
  const result = await page.evaluate(async () => {
    const requested: Array<string | null> = []
    Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: {
      getUserMedia: async (constraints: any) => {
        const device = constraints.audio.deviceId?.exact ?? null
        requested.push(device)
        if (device === 'bad-mic') throw new Error('device unavailable')
        const track: any = { readyState: 'live', stop() { this.readyState = 'ended' } }
        return { getTracks: () => [track] }
      },
      enumerateDevices: async () => [],
    } })
    class MockNode { connect() { return this } disconnect() {} }
    class MockContext { state = 'running'; destination = {}; audioWorklet = { addModule: async () => undefined }; createMediaStreamSource() { return new MockNode() }; createGain() { return Object.assign(new MockNode(), { gain: { value: 1 } }) }; async close() { this.state = 'closed' } }
    class MockWorklet extends MockNode { port = { onmessage: null as any } }
    ;(window as any).AudioContext = MockContext
    ;(window as any).AudioWorkletNode = MockWorklet
    const module = await import('/src/services/InputAudioSession.ts')
    const controller = new module.InputAudioSessionController()
    const callbacks = { onUtteranceStart: () => true, onFrame: () => undefined, onUtteranceEnd: () => undefined, onError: () => undefined }
    await controller.start(callbacks)
    let failed = false
    try { await controller.selectDevice('bad-mic') } catch { failed = true }
    const snapshot = controller.snapshot()
    await controller.stop()
    return { requested, failed, snapshot }
  })
  expect(result.failed).toBe(true)
  expect(result.requested).toEqual([null, 'bad-mic', null])
  expect(result.snapshot.selectedDeviceId).toBeNull()
  expect(result.snapshot.activeTracks).toBe(1)
})

test('X0.1 feature flag开启时显示输入页，关闭时不显示', async ({ page }) => {
  let enabled = true
  await page.route('http://127.0.0.1:7860/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname
    const json = (body: unknown, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
    if (path === '/api/v1/experience/settings') return json({ schema_version: 1, features: { input_calibration: enabled } })
    if (path === '/api/v1/onboarding/draft') return json({ id: 1, consent_granted: true, step_completed: 4, profile_draft_json: {}, settings_json: { completed: true }, device_snapshot_json: {} })
    if (path === '/api/v1/profile') return json({ id: 1, name: '小雅', user_nickname: '你', persona: '', relationship_context: '', example_dialogue: '', version: 1, updated_at: '2026-10-08T00:00:00Z' })
    if (path === '/api/v1/health') return json({ status: 'ready', components: {}, resources: {}, version: {} })
    if (path === '/api/v1/assets/portrait') return json({ kind: 'portrait', items: [] })
    if (path === '/api/v1/avatar/active') return json({ detail: 'avatar.not_found' }, 404)
    return json({ ok: true })
  })
  await page.goto('/?preview=1')
  await page.getByRole('button', { name: '设置' }).click()
  await expect(page.getByRole('button', { name: '输入', exact: true })).toBeVisible()
  await page.getByRole('button', { name: '输入', exact: true }).click()
  await expect(page.getByRole('heading', { name: '麦克风与环境' })).toBeVisible()
  await expect(page.getByRole('radio', { name: '按住说话' })).toBeVisible()
  await expect(page.getByText('不保存或上传录音')).toBeVisible()
  enabled = false
  await page.reload()
  await page.getByRole('button', { name: '设置' }).click()
  await expect(page.getByRole('button', { name: '输入', exact: true })).toHaveCount(0)
})
