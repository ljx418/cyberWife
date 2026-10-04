import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import AxeBuilder from '../../prototype/node_modules/@axe-core/playwright/dist/index.js'
import { chromium } from '../../prototype/node_modules/playwright/index.mjs'

const [output, apiBase = 'http://127.0.0.1:7860'] = process.argv.slice(2)
const browser = await chromium.connectOverCDP(process.env.CW_CHROME_CDP || 'http://127.0.0.1:9226')
const sizes = [[1920, 1080], [1366, 768], [420, 720]]
const runs = []
let focusTrap = null
let reducedMotion = null

try {
  for (const [width, height] of sizes) {
    const context = await browser.newContext({ viewport: { width, height }, reducedMotion: 'reduce' })
    const page = await context.newPage()
    await page.addInitScript(base => { window.CYBERWIFE_GATEWAY = base }, apiBase)
    await page.goto(`http://127.0.0.1:4173/?preview=1&a11y=${width}`, { waitUntil: 'networkidle' })
    const overflow = await page.evaluate(() => ({
      document: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      body: document.body.scrollWidth - document.body.clientWidth,
    }))
    const axe = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']).analyze()
    const blocking = axe.violations.filter(item => item.impact === 'critical' || item.impact === 'serious')
    const statusText = await page.getByTestId('local-status').innerText()
    const voiceName = await page.locator('.voice-button').getAttribute('aria-label')
    runs.push({ width, height, overflow, status_text: statusText, voice_name: voiceName, blocking: blocking.map(item => ({ id: item.id, impact: item.impact, nodes: item.nodes.map(node => ({ target: node.target, summary: node.failureSummary })) })) })

    if (width === 1366) {
      const trigger = page.getByRole('button', { name: '设置' })
      await trigger.click()
      const dialog = page.getByRole('dialog')
      await dialog.waitFor()
      await page.waitForTimeout(100)
      const focusableSelector = 'button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [href], [tabindex]:not([tabindex="-1"])'
      await dialog.evaluate((root, selector) => Array.from(root.querySelectorAll(selector)).filter(element => element.offsetParent !== null)[0]?.focus(), focusableSelector)
      await page.keyboard.press('Shift+Tab')
      const backwardWrapped = await dialog.evaluate((root, selector) => {
        const items = Array.from(root.querySelectorAll(selector)).filter(element => element.offsetParent !== null)
        return document.activeElement === items[items.length - 1]
      }, focusableSelector)
      const backwardActive = await page.evaluate(() => ({ tag: document.activeElement?.tagName, text: document.activeElement?.textContent?.trim(), cls: document.activeElement?.className }))
      await page.keyboard.press('Tab')
      const forwardWrapped = await dialog.evaluate((root, selector) => {
        const items = Array.from(root.querySelectorAll(selector)).filter(element => element.offsetParent !== null)
        return document.activeElement === items[0]
      }, focusableSelector)
      await page.keyboard.press('Escape')
      const focusRestored = await trigger.evaluate(element => document.activeElement === element)
      focusTrap = { backward_wrapped: backwardWrapped, forward_wrapped: forwardWrapped, backward_active: backwardActive, escape_closed: !(await dialog.isVisible()), focus_restored: focusRestored }
    }
    if (width === 420) {
      reducedMotion = await page.evaluate(() => ({
        matches: matchMedia('(prefers-reduced-motion: reduce)').matches,
        state_text: document.querySelector('.conversation-copy')?.textContent?.trim().length || 0,
        primary_control: document.querySelector('.voice-button')?.getAttribute('aria-label') || '',
      }))
    }
    await context.close()
  }
} finally {
  await browser.close().catch(() => {})
}

const result = {
  schema_version: 1,
  evidence_level: 'windows_chrome_real_gateway_axe',
  runs,
  focus_trap: focusTrap,
  reduced_motion: reducedMotion,
}
result.pass = runs.length === 3 && runs.every(run => run.overflow.document <= 0 && run.overflow.body <= 0 && run.blocking.length === 0 && run.voice_name) &&
  focusTrap?.backward_wrapped && focusTrap?.forward_wrapped && focusTrap?.escape_closed && focusTrap?.focus_restored &&
  reducedMotion?.matches && reducedMotion.state_text > 0 && Boolean(reducedMotion.primary_control)
fs.mkdirSync(path.dirname(output), { recursive: true })
fs.writeFileSync(output, JSON.stringify(result, null, 2) + '\n')
console.log(JSON.stringify(result, null, 2))
process.exit(result.pass ? 0 : 2)
