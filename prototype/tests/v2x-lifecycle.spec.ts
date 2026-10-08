import { expect, test } from '@playwright/test'

test('X0.2 重复恢复事件合并且只清理一次后安全回Idle', async ({ page }) => {
  await page.goto('/?preview=1')
  const result = await page.evaluate(async () => {
    const module = await import('/src/services/SessionLifecycle.ts')
    let stops = 0
    let probes = 0
    const states: string[] = []
    const controller = new module.SessionLifecycleController({
      stopResources: async () => { stops += 1; await new Promise((resolve) => setTimeout(resolve, 20)) },
      probeGateway: async () => { probes += 1; return true },
      onState: (snapshot) => states.push(snapshot.state),
    })
    controller.start()
    controller.markSessionActive()
    const first = controller.requestRecovery('visibility_restored')
    const second = controller.requestRecovery('network_restored')
    const [a, b] = await Promise.all([first, second])
    const snapshot = controller.snapshot()
    controller.stop()
    return { stops, probes, states, a, b, snapshot }
  })
  expect(result.stops).toBe(1)
  expect(result.probes).toBe(1)
  expect(result.snapshot.state).toBe('idle')
  expect(result.snapshot.recoveryCount).toBe(1)
  expect(result.a.generation).toBe(result.b.generation)
  expect(result.states).toContain('recovering')
})

test('X0.2 controller停止使迟到恢复失效且不执行probe', async ({ page }) => {
  await page.goto('/?preview=1')
  const result = await page.evaluate(async () => {
    const module = await import('/src/services/SessionLifecycle.ts')
    let release!: () => void
    let probes = 0
    const controller = new module.SessionLifecycleController({
      stopResources: () => new Promise<void>((resolve) => { release = resolve }),
      probeGateway: async () => { probes += 1; return true },
    })
    controller.start(); controller.markSessionActive()
    const pending = controller.requestRecovery('network_restored')
    await Promise.resolve()
    controller.stop()
    release()
    await pending
    return { probes, snapshot: controller.snapshot() }
  })
  expect(result.probes).toBe(0)
  expect(result.snapshot.state).toBe('stopped')
})

test('X0.2 探测失败后可由下一恢复事件重试', async ({ page }) => {
  await page.goto('/?preview=1')
  const result = await page.evaluate(async () => {
    const module = await import('/src/services/SessionLifecycle.ts')
    let attempts = 0
    const controller = new module.SessionLifecycleController({
      stopResources: async () => undefined,
      probeGateway: async () => { attempts += 1; return attempts > 1 },
    })
    controller.start(); controller.markSessionActive()
    const failed = await controller.requestRecovery('visibility_restored')
    const recovered = await controller.requestRecovery('network_restored')
    const snapshot = controller.snapshot()
    controller.stop()
    return { attempts, failed, recovered, snapshot }
  })
  expect(result.failed.state).toBe('error')
  expect(result.recovered.state).toBe('idle')
  expect(result.attempts).toBe(2)
  expect(result.snapshot.recoveryCount).toBe(2)
})
