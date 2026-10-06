import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'

const viewports = [
  { width: 1920, height: 1080 },
  { width: 1366, height: 768 },
  { width: 420, height: 720 },
]

async function tabTo(page: Page, name: string, limit = 40) {
  for (let index = 0; index < limit; index += 1) {
    await page.keyboard.press(index === 0 ? 'Tab' : 'Tab')
    const label = await page.evaluate(() => {
      const node = document.activeElement as HTMLElement | null
      if (!node || !['BUTTON', 'INPUT', 'TEXTAREA', 'SELECT', 'A'].includes(node.tagName)) return ''
      const label = (node as HTMLInputElement | HTMLTextAreaElement | null)?.labels?.[0]?.textContent?.trim()
      return node?.getAttribute('aria-label') || label || node?.textContent?.trim() || ''
    })
    if (label.includes(name)) return
  }
  throw new Error(`Tab sequence did not reach: ${name}`)
}

async function installLocalContracts(page: Page) {
  await page.addInitScript(() => {
    class FakeSocket extends EventTarget {
      static OPEN = 1
      static instances: FakeSocket[] = []
      readyState = 0
      binaryType = 'arraybuffer'
      url: string
      onmessage: ((event: MessageEvent) => void) | null = null
      onerror: ((event: Event) => void) | null = null
      constructor(url: string) {
        super()
        this.url = url
        FakeSocket.instances.push(this)
        queueMicrotask(() => { this.readyState = 1; this.dispatchEvent(new Event('open')) })
      }
      send(value: string | ArrayBuffer) {
        if (typeof value !== 'string') return
        try {
          const message = JSON.parse(value)
          if (message.type === 'barge_in.detected') this.emit('barge_in.detected', 'interrupted')
        } catch { /* binary/control split is verified elsewhere */ }
      }
      close() { this.readyState = 3; this.dispatchEvent(new Event('close')) }
      emit(type: string, state: string) {
        const event = new MessageEvent('message', { data: JSON.stringify({
          type, session_id: 1, turn_id: 1, event_seq: Date.now(),
          occurred_at: new Date().toISOString(), payload: { current: state },
        }) })
        this.onmessage?.(event)
        this.dispatchEvent(event)
      }
    }
    Object.defineProperty(window, 'WebSocket', { value: FakeSocket, configurable: true })
    ;(window as any).__ac11Emit = (type: string, state: string) => FakeSocket.instances.find((socket) => socket.url.includes('/sessions/'))?.emit(type, state)

    class AudioContextStub {
      state = 'running'; currentTime = 0; destination = {}; sampleRate = 16000
      audioWorklet = { addModule: async () => undefined }
      createBuffer(_channels: number, length: number, sampleRate: number) {
        const channel = new Float32Array(length)
        return { duration: length / sampleRate, getChannelData: () => channel }
      }
      createBufferSource() { return { buffer: null, onended: null, connect() { return this }, disconnect() {}, start() {}, stop() {} } }
      createMediaStreamSource() { return { connect() { return this }, disconnect() {} } }
      createGain() { return { gain: { value: 1 }, connect() { return this }, disconnect() {} } }
      async resume() { this.state = 'running' }
      async close() { this.state = 'closed' }
    }
    class WorkletStub { port = { postMessage() {}, onmessage: null }; connect() { return this }; disconnect() {} }
    Object.defineProperty(window, 'AudioContext', { value: AudioContextStub, configurable: true })
    Object.defineProperty(window, 'AudioWorkletNode', { value: WorkletStub, configurable: true })
    Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: {
      getUserMedia: async () => ({ getTracks: () => [{ stop() {} }] }),
    } })
  })

  await page.route('http://127.0.0.1:7860/api/v1/**', async (route) => {
    const request = route.request()
    const path = new URL(request.url()).pathname
    const json = (body: unknown, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
    if (path === '/api/v1/health') return json({ status: 'ready', components: Object.fromEntries(['vad','asr','llm','tts','avatar','embedding'].map((id) => [id, { status: 'ready' }])), resources: {}, version: {} })
    if (path === '/api/v1/sessions' && request.method() === 'POST') return json({ session_ref: 'ac11-local', next_turn_id: 1 })
    if (path === '/api/v1/profile' && request.method() === 'GET') return json({ name: '小悠', user_nickname: '你', persona: '温柔、自然', relationship_context: '私人日常伴侣', example_dialogue: '', version: 1 })
    if (path === '/api/v1/profile' && request.method() === 'PUT') return json({ name: '小悠', user_nickname: '你', persona: '清醒、温柔、自然', relationship_context: '私人日常伴侣', example_dialogue: '', version: 2 })
    if (path === '/api/v1/memory-candidates') return json({ items: [] })
    if (path.startsWith('/api/v1/memories')) {
      if (request.method() === 'DELETE') return json({ deleted: 1 })
      return json({ items: [{ id: 41, content: 'ACC1 隔离测试记忆', source_session_id: 'ac11-local', created_at: '2026-10-05T00:00:00Z', edited: false }] })
    }
    if (path.startsWith('/api/v1/assets/')) return json({ kind: 'portrait', items: [] })
    if (path === '/api/v1/avatar/active') return json({ detail: 'not_found' }, 404)
    if (path === '/api/v1/onboarding/draft') return json({ id: 1, consent_granted: true, step_completed: 5, profile_draft_json: {}, settings_json: {}, device_snapshot_json: {} })
    return json({ ok: true })
  })
}

for (const viewport of viewports) {
  test(`AC-11 ${viewport.width}x${viewport.height} 键盘完成五项核心任务`, async ({ page }) => {
    await page.setViewportSize(viewport)
    await installLocalContracts(page)
    await page.goto('/?preview=1')

    // 开聊：只用Tab与Enter到达主控制。
    await tabTo(page, '开始对话')
    await page.keyboard.press('Enter')
    await expect(page.getByRole('button', { name: '结束对话' })).toBeVisible()
    await expect(page.getByText('嗯，我在。')).toBeVisible()

    // 打断：服务端真实事件合同驱动到speaking，再用键盘打断。
    await page.evaluate(() => (window as any).__ac11Emit('state.changed', 'speaking'))
    await expect(page.getByRole('button', { name: '打断她' })).toBeFocused()
    await page.keyboard.press('Enter')
    await expect(page.getByText('嗯，你说。')).toBeVisible()
    await page.keyboard.press('Enter')
    await expect(page.getByRole('button', { name: '开始对话' })).toBeVisible()

    // 设置 + 改人设。
    await tabTo(page, '设置')
    await page.keyboard.press('Enter')
    await expect(page.getByRole('dialog', { name: '她的世界' })).toBeVisible()
    await tabTo(page, '人设')
    await page.keyboard.press('Enter')
    await tabTo(page, '相处方式')
    await page.keyboard.press('Control+A')
    await page.keyboard.type('清醒、温柔、自然')
    await tabTo(page, '保存人设')
    await page.keyboard.press('Enter')
    await expect(page.getByTestId('settings-api-status')).toContainText('人设已保存')

    // 删除隔离测试记忆并确认。
    await tabTo(page, '记忆')
    await page.keyboard.press('Enter')
    await expect(page.getByText('ACC1 隔离测试记忆')).toBeVisible()
    await tabTo(page, '删除')
    await page.keyboard.press('Enter')
    await expect(page.getByRole('alertdialog')).toBeVisible()
    await tabTo(page, '确认删除')
    await page.keyboard.press('Enter')
    await expect(page.getByText('ACC1 隔离测试记忆')).toHaveCount(0)

    await page.keyboard.press('Escape')
    await expect(page.getByRole('button', { name: '设置' })).toBeFocused()
    const overflow = await page.evaluate(() => Math.max(
      document.documentElement.scrollWidth - document.documentElement.clientWidth,
      document.body.scrollWidth - document.body.clientWidth,
    ))
    expect(overflow).toBeLessThanOrEqual(1)
    const results = await new AxeBuilder({ page }).analyze()
    expect(results.violations.filter((item) => ['serious', 'critical'].includes(item.impact || ''))).toEqual([])
  })
}
