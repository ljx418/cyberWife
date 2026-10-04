/** Capture the B2 steady-state resource and loopback-boundary evidence. */
import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { execFileSync } from 'node:child_process'

const root = path.resolve(import.meta.dirname, '../..')
const output = path.resolve(process.argv[2] || path.join(root, 'audit/v1/B2/avatar-recovery/resource-audit.json'))

function sh(command) {
  return execFileSync('bash', ['-lc', command], { encoding: 'utf8' }).trim()
}

function ps(command) {
  return execFileSync('powershell.exe', ['-NoProfile', '-Command', command], { encoding: 'utf8' }).trim()
}

function swapCounters() {
  const rows = Object.fromEntries(sh("awk '/^pswp(in|out) / {print $1, $2}' /proc/vmstat").split('\n').map(row => row.split(/\s+/)))
  return { in: Number(rows.pswpin), out: Number(rows.pswpout) }
}

function projectLinuxProcesses() {
  const patterns = [
    '-m cyberwife.api.server',
    'app.py --bind 127.0.0.1 --listenport 8010',
    '-m workers.speech_worker.server',
    'node /mnt/c/workspace/cyberwife/prototype/node_modules/.bin/vite',
  ]
  return sh('ps -eo pid=,rss=,args=')
    .split('\n')
    .map(line => line.trim().match(/^(\d+)\s+(\d+)\s+(.+)$/))
    .filter(Boolean)
    .map(match => ({ pid: Number(match[1]), rss_kib: Number(match[2]), command: match[3] }))
    .filter(row => patterns.some(pattern => row.command.includes(pattern)))
}

const started = swapCounters()
const swapSamples = []
let previousSwap = started
for (let second = 1; second <= 10; second += 1) {
  await new Promise(resolve => setTimeout(resolve, 1000))
  const current = swapCounters()
  swapSamples.push({ second, in_pages: current.in - previousSwap.in, out_pages: current.out - previousSwap.out })
  previousSwap = current
}
const ended = swapCounters()
const linuxProcesses = projectLinuxProcesses()
const launcher = JSON.parse(ps(`& '${path.win32.join('C:\\workSpace\\cyberWife', 'ops\\windows\\RuntimeLauncher.ps1')}' -Action status`))
const llamaPid = launcher.components.llama.pid
const windows = JSON.parse(ps(`$p=Get-Process -Id ${llamaPid}; @{ pid=$p.Id; name=$p.ProcessName; private_bytes=$p.PrivateMemorySize64; working_set_bytes=$p.WorkingSet64 } | ConvertTo-Json`))
const os = JSON.parse(ps('Get-CimInstance Win32_OperatingSystem | Select-Object TotalVisibleMemorySize,FreePhysicalMemory | ConvertTo-Json'))
const gpuValues = ps('nvidia-smi --query-gpu=memory.total,memory.used,memory.free --format=csv,noheader,nounits').split(',').map(value => Number(value.trim()))
const listenerRows = sh("ss -lntH | awk '$4 ~ /:(4173|7860|8010|8091)$/ {print $4}'").split('\n').filter(Boolean)
const windowsListener = JSON.parse(ps("Get-NetTCPConnection -State Listen -LocalPort 8090 | Select-Object LocalAddress,LocalPort,OwningProcess | ConvertTo-Json"))
const expectedPorts = [4173, 7860, 8010, 8090, 8091]
const windowsListeners = (Array.isArray(windowsListener) ? windowsListener : [windowsListener])
const loopbackOnly = [4173, 7860, 8010, 8091].every(port => listenerRows.includes(`127.0.0.1:${port}`)) &&
  windowsListeners.some(row => row.LocalPort === 8090 && ['127.0.0.1', '::1'].includes(row.LocalAddress)) &&
  listenerRows.every(address => address.startsWith('127.0.0.1:') || address.startsWith('[::1]:')) &&
  windowsListeners.every(row => ['127.0.0.1', '::1'].includes(row.LocalAddress))
const linuxRssBytes = linuxProcesses.reduce((sum, row) => sum + row.rss_kib * 1024, 0)
const projectBytes = linuxRssBytes + Number(windows.private_bytes)
let consecutiveSwapIn = 0
let maxConsecutiveSwapIn = 0
for (const sample of swapSamples) {
  consecutiveSwapIn = sample.in_pages > 0 ? consecutiveSwapIn + 1 : 0
  maxConsecutiveSwapIn = Math.max(maxConsecutiveSwapIn, consecutiveSwapIn)
}
const result = {
  measured_at: new Date().toISOString(),
  measurement: 'Windows llama private bytes + Linux project-process RSS; excludes unrelated WSL and browser processes',
  project: {
    bytes: projectBytes,
    gib: Number((projectBytes / 1024 ** 3).toFixed(3)),
    limit_gib: 14,
    linux_rss_bytes: linuxRssBytes,
    windows_llama_private_bytes: Number(windows.private_bytes),
    linux_processes: linuxProcesses,
    windows_process: windows,
  },
  host: {
    total_bytes: Number(os.TotalVisibleMemorySize) * 1024,
    free_bytes: Number(os.FreePhysicalMemory) * 1024,
    free_gib: Number((Number(os.FreePhysicalMemory) * 1024 / 1024 ** 3).toFixed(3)),
  },
  wsl: JSON.parse(sh("free -b | awk '/^Mem:/ {printf \"{\\\"total_bytes\\\":%s,\\\"available_bytes\\\":%s}\", $2, $7}'")),
  gpu: { total_mib: gpuValues[0], used_mib: gpuValues[1], free_mib: gpuValues[2], limit_mib: 22 * 1024 },
  swap: {
    before: started,
    after: ended,
    delta_in_pages: ended.in - started.in,
    delta_out_pages: ended.out - started.out,
    samples: swapSamples,
    max_consecutive_active_seconds: maxConsecutiveSwapIn,
    sustained: maxConsecutiveSwapIn >= 3 || ended.in - started.in > 256 || ended.out - started.out > 256,
  },
  network: { expected_ports: expectedPorts, loopback_only: loopbackOnly, wsl_listeners: listenerRows, windows_listeners: windowsListeners },
  launcher,
}
result.pass = result.project.gib <= 14 && result.host.free_gib >= 2 &&
  result.wsl.available_bytes >= 2 * 1024 ** 3 && result.gpu.used_mib <= result.gpu.limit_mib &&
  result.gpu.free_mib >= 2 * 1024 && !result.swap.sustained && loopbackOnly &&
  Object.values(launcher.components).every(component => component.healthy && component.owned)

fs.mkdirSync(path.dirname(output), { recursive: true })
fs.writeFileSync(output, `${JSON.stringify(result, null, 2)}\n`)
process.stdout.write(`${JSON.stringify(result, null, 2)}\n`)
process.exit(result.pass ? 0 : 1)
