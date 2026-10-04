import { expect, test } from '@playwright/test'

const focusable = 'button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [href], [tabindex]:not([tabindex="-1"])'

test('设置对话框圈闭焦点并在 Escape 后恢复到触发按钮', async ({ page }) => {
  await page.goto('/?preview=1')
  const trigger = page.getByRole('button', { name: '设置' })
  await trigger.click()
  const dialog = page.getByRole('dialog', { name: '她的世界' })
  await expect(dialog).toBeVisible()

  await dialog.evaluate((root, selector) => {
    const items = Array.from(root.querySelectorAll<HTMLElement>(selector))
      .filter((element) => element.offsetParent !== null)
    items[0]?.focus()
  }, focusable)
  await page.keyboard.press('Shift+Tab')
  expect(await dialog.evaluate((root, selector) => {
    const items = Array.from(root.querySelectorAll<HTMLElement>(selector))
      .filter((element) => element.offsetParent !== null)
    return document.activeElement === items.at(-1)
  }, focusable)).toBe(true)

  await page.keyboard.press('Tab')
  expect(await dialog.evaluate((root, selector) => {
    const items = Array.from(root.querySelectorAll<HTMLElement>(selector))
      .filter((element) => element.offsetParent !== null)
    return document.activeElement === items[0]
  }, focusable)).toBe(true)

  await page.keyboard.press('Escape')
  await expect(dialog).toBeHidden()
  await expect(trigger).toBeFocused()
})
