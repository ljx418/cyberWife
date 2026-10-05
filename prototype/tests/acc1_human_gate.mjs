import { chromium } from '@playwright/test'
import { mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import readline from 'node:readline/promises'
import process from 'node:process'
import { healthReady, redactError, sanitizeControl, summarizeMachineEvidence } from './acc1_human_gate_core.mjs'

function parseArgs(argv) {
  const result = {}
  for (let index = 0; index < argv.length; index += 1) {
    const key = argv[index]
    if (key === '--no-fake-media') result.noFakeMedia = true
    else if (key.startsWith('--')) result[key.slice(2)] = argv[++index]
  }
  return result
}

const args = parseArgs(process.argv.slice(2))
if (!args.noFakeMedia) throw new Error('--no-fake-media is required for the physical microphone gate')
if (!args.operator?.trim()) throw new Error('--operator is required')
if (!/^[a-f0-9]{40,64}$/.test(args['workspace-revision'] || '')) throw new Error('--workspace-revision is required')
if (!args.output) throw new Error('--output is required')

const pageUrl = args.url || 'http://127.0.0.1:7860/?preview=1'
const chromePath = args['chrome-path'] || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
const reportPath = path.resolve(args.output)
const profile = await mkdtemp(path.join(os.tmpdir(), 'cyberwife-acc1-'))
const prompt = readline.createInterface({ input: process.stdin, output: process.stdout })
const startedAt = new Date().toISOString()
const received = []
const sentControls = []
const eventCounts = new Map()
const avatarSockets = []
let order = 0
let maxEmittedFrames = 0
let maxActiveTracks = 0
let liveCanvasObserved = false
let context

function safeControl(payload, direction) {
  const item = sanitizeControl(payload, direction, ++order)
  if (!item) return
  eventCounts.set(item.type, (eventCounts.get(item.type) || 0) + 1)
  if (direction === 'received') received.push(item)
  else sentControls.push(item)
}

function machineProgress() {
  return summarizeMachineEvidence(received, sentControls, eventCounts)
}

async function askYesNo(message) {
  while (true) {
    const answer = (await prompt.question(`${message} [y/n] `)).trim().toLowerCase()
    if (answer === 'y') return true
    if (answer === 'n') return false
  }
}

async function askScore(message) {
  while (true) {
    const score = Number((await prompt.question(`${message} [1-5] `)).trim())
    if (Number.isInteger(score) && score >= 1 && score <= 5) return score
  }
}

async function publicHealth(page) {
  return page.evaluate(async () => {
    const response = await fetch('/api/v1/health', { cache: 'no-store' })
    if (!response.ok) throw new Error(`health ${response.status}`)
    const body = await response.json()
    return {
      status: body.status,
      components: Object.fromEntries(Object.entries(body.components || {}).map(([key, value]) => [key, value.status])),
    }
  })
}

let result
try {
  context = await chromium.launchPersistentContext(profile, {
    headless: false,
    executablePath: chromePath,
    viewport: { width: 1366, height: 768 },
    args: ['--new-window', '--no-first-run'],
  })
  const page = context.pages()[0] || await context.newPage()
  page.on('websocket', (socket) => {
    if (socket.url().includes('/ws/v1/avatar')) avatarSockets.push(socket.url())
    if (!socket.url().includes('/ws/v1/sessions/')) return
    socket.on('framereceived', (frame) => safeControl(frame.payload, 'received'))
    socket.on('framesent', (frame) => safeControl(frame.payload, 'sent'))
  })

  await page.goto(pageUrl, { waitUntil: 'domcontentloaded' })
  const healthBefore = await publicHealth(page)
  const activeAvatar = await page.evaluate(async () => {
    const response = await fetch('/api/v1/avatar/active', { cache: 'no-store' })
    if (!response.ok) throw new Error(`active avatar ${response.status}`)
    const body = await response.json()
    return { id: body.id, avatar_id: body.avatar_id, engine: body.engine, status: body.status }
  })

  console.log('\n已打开安装版 Chrome。只允许为 127.0.0.1 页面授予麦克风权限。')
  console.log('请完成至少三轮完整回复，并在她说话时插话一次；插话后再完成一轮回复。')
  await prompt.question('准备好后按 Enter 开始机器取证（最长15分钟）：')

  const deadline = Date.now() + 15 * 60 * 1000
  let lastProgress = ''
  while (Date.now() < deadline) {
    const snapshot = await page.evaluate(() => {
      const api = window.__CYBERWIFE_SESSION__
      return api?.input ? api.input() : null
    }).catch(() => null)
    if (snapshot) {
      maxEmittedFrames = Math.max(maxEmittedFrames, Number(snapshot.emittedFrames) || 0)
      maxActiveTracks = Math.max(maxActiveTracks, Number(snapshot.activeTracks) || 0)
    }
    const canvasLive = await page.locator('.avatar-video').evaluate((canvas) =>
      canvas.dataset.avatarLayer === 'live' && !canvas.hidden,
    ).catch(() => false)
    liveCanvasObserved ||= canvasLive
    const progress = machineProgress()
    const display = `${progress.completedTurns.length}/3完整轮，打断${progress.cancelled_count}，打断后接续${progress.postCancelCompleted ? '是' : '否'}`
    if (display !== lastProgress) {
      console.log(`机器证据：${display}`)
      lastProgress = display
    }
    if (
      progress.completedTurns.length >= 3
      && progress.barge_in_count >= 1
      && progress.cancelled_count >= 1
      && progress.postCancelCompleted
      && maxEmittedFrames > 0
      && maxActiveTracks >= 1
    ) break
    await page.waitForTimeout(500)
  }

  const progress = machineProgress()
  const narrator = {
    settings: await askYesNo('Narrator可独立打开设置并识别关闭按钮'),
    start: await askYesNo('Narrator可启动对话并听到状态变化'),
    interrupt: await askYesNo('Narrator可理解打断操作与恢复状态'),
    persona: await askYesNo('Narrator可编辑并保存人设'),
    delete_memory: await askYesNo('Narrator可理解删除确认框并取消/确认'),
  }
  const perception = {
    lip_sync_score: await askScore('当前人物口型同步度'),
    mouth_naturalness_score: await askScore('当前人物嘴部自然度'),
    idle_naturalness_score: await askScore('当前人物Idle自然度'),
    idle_continues_after_stop: await askYesNo('结束对话后Idle持续播放且无黑屏'),
  }

  const voiceButton = page.getByRole('button', { name: /结束对话|打断她/ })
  if (await voiceButton.count()) await voiceButton.first().click().catch(() => {})
  await page.waitForTimeout(300)
  const idleBefore = await page.getByTestId('idle-avatar-video').evaluate((video) => video.currentTime).catch(() => null)
  await page.waitForTimeout(900)
  const idleAfter = await page.getByTestId('idle-avatar-video').evaluate((video) => video.currentTime).catch(() => null)
  const idleAdvance = idleBefore !== null && idleAfter !== null ? idleAfter - idleBefore : 0
  const healthAfter = await publicHealth(page)
  const avatarBound = avatarSockets.some((url) => url.includes(`avatar_id=${encodeURIComponent(activeAvatar.avatar_id)}`))
  const machinePass = progress.completedTurns.length >= 3
    && progress.transcripts >= 3
    && progress.replies >= 3
    && progress.audio_turns >= 3
    && progress.barge_in_count >= 1
    && progress.cancelled_count >= 1
    && progress.postCancelCompleted
    && progress.error_count === 0
    && maxEmittedFrames > 0
    && maxActiveTracks >= 1
    && liveCanvasObserved
    && avatarBound
    && idleAdvance >= 0.5
    && healthReady(healthBefore)
    && healthReady(healthAfter)
  const humanPass = Object.values(narrator).every(Boolean)
    && perception.lip_sync_score >= 4
    && perception.mouth_naturalness_score >= 4
    && perception.idle_naturalness_score >= 4
    && perception.idle_continues_after_stop

  result = {
    schema_version: 2,
    gate: 'ACC1-and-UX6-human-machine-bound-gate',
    started_at: startedAt,
    completed_at: new Date().toISOString(),
    operator: args.operator.trim(),
    workspace_revision: args['workspace-revision'],
    browser: { product: 'installed Google Chrome', version: await context.browser()?.version() },
    page_origin: new URL(pageUrl).origin,
    screen_reader: 'Windows Narrator',
    stores_raw_audio: false,
    stores_transcript_or_reply_content: false,
    health_before: healthBefore,
    health_after: healthAfter,
    active_avatar: activeAvatar,
    evidence: {
      emitted_pcm_frames: maxEmittedFrames,
      max_active_microphone_tracks: maxActiveTracks,
      distinct_transcript_turns: progress.transcripts,
      distinct_reply_turns: progress.replies,
      distinct_audio_turns: progress.audio_turns,
      completed_turn_ids: progress.completedTurns,
      barge_in_count: progress.barge_in_count,
      cancelled_count: progress.cancelled_count,
      post_cancel_completed: progress.postCancelCompleted,
      error_count: progress.error_count,
      live_canvas_observed: liveCanvasObserved,
      active_avatar_socket_bound: avatarBound,
      idle_advance_after_stop_seconds: Number(idleAdvance.toFixed(3)),
      event_type_counts: Object.fromEntries([...eventCounts.entries()].sort()),
    },
    narrator,
    perception,
    machine_result: machinePass ? 'PASS' : 'FAIL',
    human_result: humanPass ? 'PASS' : 'FAIL',
    result: machinePass && humanPass ? 'PASS' : 'FAIL',
  }
} catch (error) {
  result = {
    schema_version: 2,
    gate: 'ACC1-and-UX6-human-machine-bound-gate',
    started_at: startedAt,
    completed_at: new Date().toISOString(),
    operator: args.operator?.trim() || '',
    workspace_revision: args['workspace-revision'] || '',
    stores_raw_audio: false,
    stores_transcript_or_reply_content: false,
    result: 'ERROR',
    error: redactError(error instanceof Error ? error.message : String(error)),
  }
} finally {
  prompt.close()
  await context?.close().catch(() => {})
  await rm(profile, { recursive: true, force: true })
}

await mkdir(path.dirname(reportPath), { recursive: true })
await writeFile(reportPath, `${JSON.stringify(result, null, 2)}\n`, 'utf8')
console.log(JSON.stringify(result, null, 2))
if (result.result !== 'PASS') process.exitCode = 2
