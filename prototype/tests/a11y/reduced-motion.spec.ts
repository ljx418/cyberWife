import { expect, test } from '@playwright/test'

test.use({ reducedMotion: 'reduce', viewport: { width: 420, height: 720 } })

test('减少动效时核心状态与主控制仍完整可读', async ({ page }) => {
  await page.goto('/?preview=1')
  expect(await page.evaluate(() => matchMedia('(prefers-reduced-motion: reduce)').matches)).toBe(true)
  await expect(page.locator('.conversation-copy')).not.toBeEmpty()
  await expect(page.locator('.voice-button')).toBeVisible()
  await expect(page.locator('.voice-button')).toHaveAttribute('aria-label', /.+/)
})
