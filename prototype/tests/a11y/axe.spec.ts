import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

for (const viewport of [
  { width: 1920, height: 1080 },
  { width: 1366, height: 768 },
  { width: 420, height: 720 },
]) {
  test(`主舞台 ${viewport.width}x${viewport.height} 无严重可访问性错误或横向溢出`, async ({ page }) => {
    await page.setViewportSize(viewport)
    await page.goto('/?preview=1')
    const overflow = await page.evaluate(() => ({
      document: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      body: document.body.scrollWidth - document.body.clientWidth,
    }))
    const audit = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'])
      .analyze()
    const blocking = audit.violations.filter(
      (violation) => violation.impact === 'critical' || violation.impact === 'serious',
    )

    expect(overflow.document).toBeLessThanOrEqual(0)
    expect(overflow.body).toBeLessThanOrEqual(0)
    expect(blocking).toEqual([])
    await expect(page.locator('.voice-button')).toHaveAttribute('aria-label', /.+/)
  })
}
