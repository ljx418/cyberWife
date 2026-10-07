import { useEffect, useRef, useState } from 'react'
import type {
  ConversationState,
  MemoryRecord,
  RuntimeService,
  SettingsTab,
  ThemeMode,
  VisualVariant,
} from './types'
import { ConversationClient, type AvatarBuild, type HealthResponse, type IdleGenerationJob, type MemoryCandidate, type Profile as ApiProfile, type WsEnvelope } from './services/ConversationClient'
import { InputAudioSession } from './services/InputAudioSession'
import { MediaSession } from './services/MediaSession'
import { AvatarSession } from './services/AvatarSession'

const stateContent: Record<ConversationState, { eyebrow: string; title: string; subtitle: string }> = {
  idle: {
    eyebrow: '今晚 22:08',
    title: '你回来啦。',
    subtitle: '今晚想聊点什么？',
  },
  listening: {
    eyebrow: '正在聆听',
    title: '嗯，我在。',
    subtitle: '慢慢说，我听着。',
  },
  thinking: {
    eyebrow: '正在回应',
    title: '让我想想。',
    subtitle: '有些话，要认真一点回答。',
  },
  speaking: {
    eyebrow: '她正在说',
    title: '其实我一直都记得。',
    subtitle: '你上次说想把周末留空一点，我们就不安排太多事，好不好？',
  },
  interrupted: {
    eyebrow: '已停下',
    title: '嗯，你说。',
    subtitle: '我在听你。',
  },
  error: {
    eyebrow: '连接暂停',
    title: '我好像暂时听不见。',
    subtitle: '麦克风服务没有响应，重新连接后可以继续刚才的话题。',
  },
}

const onboardingSteps = [
  { id: 'privacy', label: '本地与授权' },
  { id: 'runtime', label: '运行检查' },
  { id: 'portrait', label: '人物形象' },
  { id: 'voice', label: '声音样本' },
  { id: 'persona', label: '人设关系' },
]

const defaultMemories: MemoryRecord[] = []

const sceneBackgrounds = [
  { id: 'blue-hour-living', label: '蓝调客厅', description: '暖灯与城市蓝调', src: '/backgrounds/blue-hour-living.webp' },
  { id: 'morning-bedroom', label: '清晨卧室', description: '柔和晨光与浅木色', src: '/backgrounds/morning-bedroom.webp' },
  { id: 'rainy-library', label: '雨夜书房', description: '安静深色与雨窗', src: '/backgrounds/rainy-library.webp' },
  { id: 'garden-sunroom', label: '花园阳光房', description: '自然绿意与午后光', src: '/backgrounds/garden-sunroom.webp' },
] as const

type LayoutMode = 'standard' | 'portrait' | 'ultratall' | 'strip'
type AvatarSequencePhase = 'legacy' | 'intro' | 'idle' | 'outro'

const classifyLayout = (width: number, height: number): LayoutMode => {
  const ratio = width / Math.max(1, height)
  if (height <= 260 && ratio >= 4) return 'strip'
  if (ratio <= 0.72) return 'ultratall'
  if (ratio < 1) return 'portrait'
  return 'standard'
}

const toMemoryRecord = (item: Record<string, any>): MemoryRecord => ({
  id: String(item.id),
  content: String(item.content || ''),
  source: item.source === 'manual'
    ? '手工记忆'
    : item.source_session_id
      ? `会话 ${item.source_session_id}`
      : '已保留事实',
  createdAt: item.created_at ? new Date(item.created_at).toLocaleString() : '刚刚',
  edited: Boolean(item.edited),
})

const runtimeServices: RuntimeService[] = [
  { id: 'llm', name: '对话模型', detail: '正在读取真实状态', status: 'loading' },
  { id: 'asr', name: '语音识别', detail: '正在读取真实状态', status: 'loading' },
  { id: 'vad', name: '语音边界', detail: '正在读取真实状态', status: 'loading' },
  { id: 'tts', name: '声音合成', detail: '正在读取真实状态', status: 'loading' },
  { id: 'avatar', name: '人物口型', detail: '正在读取真实状态', status: 'loading' },
  { id: 'embedding', name: '记忆检索', detail: '正在读取真实状态', status: 'loading' },
]

const toRuntimeStatus = (status: string): RuntimeService['status'] =>
  status === 'ready' || status === 'error' || status === 'degraded' ? status : 'loading'

function App() {
  const previewMode = new URLSearchParams(window.location.search).get('preview') === '1'
  const [onboardingDone, setOnboardingDone] = useState(
    () => previewMode,
  )
  const [onboardingStep, setOnboardingStep] = useState(0)
  const [consentChecked, setConsentChecked] = useState(false)
  const [characterName, setCharacterName] = useState('小雅')
  const [userNickname, setUserNickname] = useState('你')
  const [conversationState, setConversationState] = useState<ConversationState>('idle')
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [settingsTab, setSettingsTab] = useState<SettingsTab>('profile')
  const [theme, setTheme] = useState<ThemeMode>(() => {
    return (localStorage.getItem('cyberwife-theme') as ThemeMode | null) ?? 'cinematic-dark'
  })
  const [variant, setVariant] = useState<VisualVariant>('cinematic')
  const [compact, setCompact] = useState(false)
  const [tweaksOpen, setTweaksOpen] = useState(false)
  const [memories, setMemories] = useState<MemoryRecord[]>(defaultMemories)
  const [memoryQuery, setMemoryQuery] = useState('')
  const [editingMemory, setEditingMemory] = useState<string | null>(null)
  const [newMemory, setNewMemory] = useState('')
  const [memoryCandidates, setMemoryCandidates] = useState<MemoryCandidate[]>([])
  const [deleteTarget, setDeleteTarget] = useState<string | 'all' | null>(null)
  const [doNotRecord, setDoNotRecord] = useState(false)
  const [personaText, setPersonaText] = useState(
    '亲近、自然，偶尔会小小抱怨，但不会像客服一样说话。每次两三句，先回应感受，再说事情。',
  )
  const [profileVersion, setProfileVersion] = useState(0)
  const [settingsStatus, setSettingsStatus] = useState('尚未读取')
  const [assetCounts, setAssetCounts] = useState({ portrait: 0, voice: 0 })
  const [activePortraitRevision, setActivePortraitRevision] = useState<number | null>(null)
  const [activeAvatarId, setActiveAvatarId] = useState('wav2lip256_avatar1')
  const [activeAvatarDerivativeId, setActiveAvatarDerivativeId] = useState<number | null>(null)
  const [idleJob, setIdleJob] = useState<IdleGenerationJob | null>(null)
  const [idleVideoReady, setIdleVideoReady] = useState(false)
  const [sequenceOverlayReady, setSequenceOverlayReady] = useState(false)
  const [hasSceneSequence, setHasSceneSequence] = useState(false)
  const [hasSingleSceneSurface, setHasSingleSceneSurface] = useState(false)
  const [sequencePhase, setSequencePhase] = useState<AvatarSequencePhase>('legacy')
  const [avatarFocus, setAvatarFocus] = useState({ x: 50, y: 32 })
  const [backgroundId, setBackgroundId] = useState(() => localStorage.getItem('cyberwife-background') || sceneBackgrounds[0].id)
  const [layoutMode, setLayoutMode] = useState<LayoutMode>(() => classifyLayout(window.innerWidth, window.innerHeight))
  const [runtimeRows, setRuntimeRows] = useState<RuntimeService[]>(runtimeServices)
  const [onboardingStatus, setOnboardingStatus] = useState('正在读取本机设置…')
  const [voiceTranscript, setVoiceTranscript] = useState('')
  const [userTranscript, setUserTranscript] = useState('')
  const [assistantTranscript, setAssistantTranscript] = useState('')
  const [conversationError, setConversationError] = useState('')
  const settingsTriggerRef = useRef<HTMLButtonElement>(null)
  const drawerCloseRef = useRef<HTMLButtonElement>(null)
  const deleteReturnFocusRef = useRef<HTMLElement | null>(null)
  const avatarCanvasRef = useRef<HTMLCanvasElement>(null)
  const conversationStateRef = useRef<ConversationState>('idle')
  const socketRef = useRef<WebSocket | null>(null)
  const sessionRef = useRef<string | null>(null)
  const nextTurnRef = useRef(1)

  const requestDelete = (target: string | 'all') => {
    deleteReturnFocusRef.current = document.activeElement as HTMLElement | null
    setDeleteTarget(target)
  }

  const closeDelete = () => {
    setDeleteTarget(null)
    window.setTimeout(() => {
      const previous = deleteReturnFocusRef.current
      if (previous?.isConnected) previous.focus()
      else drawerCloseRef.current?.focus()
    }, 0)
  }
  const inputTurnRef = useRef<number | null>(null)
  const currentServerTurnRef = useRef<number | null>(null)
  const chunkSeqRef = useRef(0)
  const awaitingAsrRef = useRef(false)
  const lastEventSeqRef = useRef(0)

  useEffect(() => { conversationStateRef.current = conversationState }, [conversationState])

  useEffect(() => {
    const update = () => setLayoutMode(classifyLayout(window.innerWidth, window.innerHeight))
    window.addEventListener('resize', update)
    update()
    return () => window.removeEventListener('resize', update)
  }, [])

  useEffect(() => {
    localStorage.setItem('cyberwife-background', backgroundId)
  }, [backgroundId])

  useEffect(() => {
    let active = true
    void Promise.all([ConversationClient.getOnboardingDraft(), ConversationClient.getProfile(), ConversationClient.getHealth()])
      .then(([draft, profile, health]) => {
        if (!active) return
        setConsentChecked(draft.consent_granted)
        setOnboardingStep(Math.min(4, Math.max(0, draft.step_completed)))
        const profileDraft = draft.profile_draft_json || {}
        if (profile) {
          setCharacterName(profile.name); setUserNickname(profile.user_nickname)
          setPersonaText(profile.persona); setProfileVersion(profile.version)
        } else {
          if (typeof profileDraft.name === 'string') setCharacterName(profileDraft.name)
          if (typeof profileDraft.user_nickname === 'string') setUserNickname(profileDraft.user_nickname)
          if (typeof profileDraft.persona === 'string') setPersonaText(profileDraft.persona)
        }
        if (typeof draft.settings_json?.voice_transcript === 'string') setVoiceTranscript(draft.settings_json.voice_transcript)
        setRuntimeRows(Object.entries(health.components).map(([id, item]) => ({
          id, name: id.toUpperCase(), detail: item.logical_id || '本机组件',
          status: toRuntimeStatus(item.status),
        })))
        if (!previewMode && draft.settings_json?.completed === true) setOnboardingDone(true)
        setOnboardingStatus('草稿已从本机恢复')
      })
      .catch((error) => { if (active) setOnboardingStatus(`读取失败：${String(error)}`) })
    return () => { active = false }
  }, [])

  useEffect(() => {
    let cancelled = false
    let timer: number | null = null
    const refreshUntilSettled = async () => {
      try {
        const health = await ConversationClient.getHealth()
        if (cancelled) return
        const rows = Object.entries(health.components).map(([id, item]) => ({
          id, name: id.toUpperCase(), detail: item.logical_id || '本机组件', status: toRuntimeStatus(item.status),
        }))
        setRuntimeRows(rows)
        if (rows.some((row) => row.status === 'loading')) timer = window.setTimeout(refreshUntilSettled, 2000)
      } catch {
        if (!cancelled) setRuntimeRows((rows) => rows.map((row) => ({ ...row, status: 'error', detail: 'Gateway 不可达' })))
      }
    }
    timer = window.setTimeout(refreshUntilSettled, 1200)
    return () => { cancelled = true; if (timer !== null) window.clearTimeout(timer) }
  }, [])

  useEffect(() => {
    void Promise.all([ConversationClient.getAssets('portrait'), ConversationClient.getActiveAvatar()]).then(([response, avatar]) => {
      const active = response.items.find((item) => Boolean(item.is_active))
      if (active) setActivePortraitRevision(Number(active.id) || Date.now())
      if (avatar.avatar_id) setActiveAvatarId(avatar.avatar_id)
      if (avatar.id) {
        setActiveAvatarDerivativeId(avatar.id)
        void ConversationClient.getIdleGeneration(avatar.id)
          .then(async (job) => {
            const resumed = job.status === 'queued' || job.status === 'generating'
              ? await ConversationClient.startIdleGeneration(avatar.id!)
              : job
            setIdleJob(resumed)
            const sequenceReady = resumed.status === 'active'
              && resumed.has_sequence_previews === true
              && resumed.has_intro_preview === true
              && resumed.has_outro_preview === true
            setHasSceneSequence(sequenceReady)
            setHasSingleSceneSurface(
              sequenceReady
              && resumed.single_surface_ready === true
              && resumed.speaking_avatar_id === avatar.avatar_id,
            )
            if (sequenceReady) {
              setSequenceOverlayReady(false)
              setSequencePhase('intro')
            }
          })
          .catch(() => {})
      }
      if (avatar.face_box && avatar.frame_size) {
        const [y1, y2, x1, x2] = avatar.face_box
        const [width, height] = avatar.frame_size
        setAvatarFocus({ x: ((x1 + x2) / 2 / width) * 100, y: ((y1 + y2) / 2 / height) * 100 })
      }
    }).catch(() => {})
  }, [])

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem('cyberwife-theme', theme)
  }, [theme])

  useEffect(() => {
    if (settingsOpen) {
      window.setTimeout(() => drawerCloseRef.current?.focus(), 60)
    }
  }, [settingsOpen])

  useEffect(() => {
    if (!deleteTarget) return
    window.setTimeout(() => {
      document.querySelector<HTMLElement>('.confirm-dialog button')?.focus()
    }, 0)
  }, [deleteTarget])

  useEffect(() => {
    if (!settingsOpen) return
    const load = async () => {
      setSettingsStatus('正在读取本机数据…')
      try {
        if (settingsTab === 'profile' || settingsTab === 'voice') {
          const kind = settingsTab === 'profile' ? 'portrait' : 'voice'
          const response = await ConversationClient.getAssets(kind)
          setAssetCounts((value) => ({ ...value, [kind]: response.items.length }))
        } else if (settingsTab === 'persona') {
          const profile = await ConversationClient.getProfile()
          if (profile) {
            setCharacterName(profile.name); setUserNickname(profile.user_nickname)
            setPersonaText(profile.persona); setProfileVersion(profile.version)
          }
        } else if (settingsTab === 'memory') {
          const [response, candidates] = await Promise.all([
            ConversationClient.getMemories(memoryQuery),
            ConversationClient.getMemoryCandidates(),
          ])
          setMemories(response.items.map(toMemoryRecord))
          setMemoryCandidates(candidates.items)
        } else if (settingsTab === 'privacy') {
          await Promise.all([ConversationClient.getConsents(), ConversationClient.getRetention()])
        } else if (settingsTab === 'runtime') {
          const health: HealthResponse = await ConversationClient.getHealth()
          setRuntimeRows(Object.entries(health.components).map(([id, item]) => ({
            id, name: id.toUpperCase(), detail: item.logical_id || '本机组件',
            status: toRuntimeStatus(item.status),
          })))
        }
        setSettingsStatus('已连接真实本机服务')
      } catch (error) {
        setSettingsStatus(`读取失败：${String(error)}`)
      }
    }
    void load()
  }, [settingsOpen, settingsTab])

  useEffect(() => {
    if (!settingsOpen || settingsTab !== 'runtime') return
    let cancelled = false
    let timer: number | null = null
    const poll = async () => {
      try {
        const health = await ConversationClient.getHealth()
        if (cancelled) return
        setRuntimeRows(Object.entries(health.components).map(([id, item]) => ({
          id, name: id.toUpperCase(), detail: item.logical_id || '本机组件',
          status: toRuntimeStatus(item.status),
        })))
      } catch {
        if (cancelled) return
        setRuntimeRows((rows) => rows.map((row) => ({ ...row, status: 'error', detail: 'Gateway 不可达；对话控制暂停' })))
        setSettingsStatus('本机 Gateway 不可达；请运行一键恢复')
      } finally {
        if (!cancelled) timer = window.setTimeout(poll, 1500)
      }
    }
    void poll()
    return () => {
      cancelled = true
      if (timer !== null) window.clearTimeout(timer)
    }
  }, [settingsOpen, settingsTab])

  useEffect(() => {
    if (!settingsOpen) return
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        if (deleteTarget) closeDelete()
        else closeSettings()
        return
      }
      if (event.key !== 'Tab') return
      const dialog = document.querySelector<HTMLElement>('.confirm-dialog[role="alertdialog"]')
        ?? document.querySelector<HTMLElement>('.settings-drawer[role="dialog"]')
      if (!dialog) return
      const focusable = Array.from(dialog.querySelectorAll<HTMLElement>(
        'button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [href], [tabindex]:not([tabindex="-1"])',
      )).filter((element) => element.offsetParent !== null)
      if (!focusable.length) return
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault(); last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault(); first.focus()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [settingsOpen, deleteTarget])

  const closeSettings = () => {
    setSettingsOpen(false)
    window.setTimeout(() => settingsTriggerRef.current?.focus(), 0)
  }

  const handleServerEvent = (event: WsEnvelope) => {
    if (event.event_seq <= lastEventSeqRef.current) return
    lastEventSeqRef.current = event.event_seq
    if (typeof event.turn_id === 'number') currentServerTurnRef.current = event.turn_id
    if (event.type === 'state.changed') {
      const state = String(event.payload.current || '') as ConversationState
      if (['idle', 'listening', 'thinking', 'speaking', 'interrupted', 'error'].includes(state)) setConversationState(state)
    } else if (event.type === 'transcript.final') {
      setUserTranscript(String(event.payload.text || ''))
      if (typeof event.turn_id === 'number') nextTurnRef.current = event.turn_id + 1
      awaitingAsrRef.current = false
    } else if (event.type === 'transcript.partial' && event.payload.speech_detected === false) {
      awaitingAsrRef.current = false
    } else if (event.type === 'reply.text.delta') {
      setAssistantTranscript((value) => value + String(event.payload.text_delta || ''))
    } else if (event.type === 'reply.text.final') {
      setAssistantTranscript(String(event.payload.text_final || ''))
    } else if (event.type === 'barge_in.detected') {
      setConversationState('interrupted')
    } else if (event.type === 'turn.cancelled') {
      setConversationState('listening')
      awaitingAsrRef.current = false
    } else if (event.type === 'error') {
      setConversationError(String(event.payload.message || event.payload.code || '本机对话出现错误'))
      setConversationState('error')
      awaitingAsrRef.current = false
    }
  }

  const stopConversation = async (notifyServer = true, playOutro = notifyServer) => {
    const socket = socketRef.current
    const ref = sessionRef.current
    socketRef.current = null
    sessionRef.current = null
    inputTurnRef.current = null
    awaitingAsrRef.current = false
    if (notifyServer && socket?.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: 'conversation.stop' }))
    } else if (notifyServer && ref) {
      try { await ConversationClient.endSession(ref) } catch { /* server may already be gone */ }
    }
    socket?.close()
    await Promise.allSettled([InputAudioSession.stop(), MediaSession.stop(), AvatarSession.stop()])
    setConversationState('idle')
    if (hasSceneSequence && playOutro) {
      setSequenceOverlayReady(false)
      setSequencePhase('outro')
    }
  }

  const synchronizeConversationAvatar = async (): Promise<{
    avatarId: string
    singleSurfaceReady: boolean
  }> => {
    let active: Awaited<ReturnType<typeof ConversationClient.getActiveAvatar>>
    try {
      active = await ConversationClient.getActiveAvatar()
    } catch {
      setHasSingleSceneSurface(false)
      return { avatarId: activeAvatarId, singleSurfaceReady: false }
    }
    setActiveAvatarId(active.avatar_id)
    setActiveAvatarDerivativeId(active.id ?? null)
    if (active.face_box && active.frame_size) {
      const [y1, y2, x1, x2] = active.face_box
      const [width, height] = active.frame_size
      setAvatarFocus({ x: ((x1 + x2) / 2 / width) * 100, y: ((y1 + y2) / 2 / height) * 100 })
    }
    if (!active.id) {
      setHasSingleSceneSurface(false)
      return { avatarId: active.avatar_id, singleSurfaceReady: false }
    }
    let job: IdleGenerationJob
    try {
      job = await ConversationClient.getIdleGeneration(active.id)
    } catch {
      setHasSceneSequence(false)
      setHasSingleSceneSurface(false)
      return { avatarId: active.avatar_id, singleSurfaceReady: false }
    }
    setIdleJob(job)
    const sequenceReady = job.status === 'active'
      && job.has_sequence_previews === true
      && job.has_intro_preview === true
      && job.has_outro_preview === true
    const singleSurfaceReady = sequenceReady
      && job.single_surface_ready === true
      && job.speaking_avatar_id === active.avatar_id
    setHasSceneSequence(sequenceReady)
    setHasSingleSceneSurface(singleSurfaceReady)
    if (sequenceReady) {
      setSequenceOverlayReady(false)
      setSequencePhase((current) => current === 'outro' ? 'intro' : 'idle')
    }
    return { avatarId: active.avatar_id, singleSurfaceReady }
  }

  const startConversation = async () => {
    if (socketRef.current) return
    setConversationError('')
    setUserTranscript('')
    setAssistantTranscript('')
    try {
      const health = await ConversationClient.getHealth()
      if (health.status === 'error' || ['llm', 'asr', 'tts'].some((id) => health.components[id]?.status === 'error')) {
        throw new Error('核心本机服务尚未就绪，请先在运行状态中恢复')
      }
      const avatarBinding = await synchronizeConversationAvatar()
      if (avatarCanvasRef.current) {
        avatarCanvasRef.current.dataset.presentation = avatarBinding.singleSurfaceReady
          ? 'complete-scene'
          : 'portrait'
      }
      await MediaSession.start()
      const created = await ConversationClient.createSession(doNotRecord ? 'none' : 'standard')
      sessionRef.current = created.session_ref
      nextTurnRef.current = created.next_turn_id
      lastEventSeqRef.current = 0
      const socket = ConversationClient.openSessionWebSocket(created.session_ref, handleServerEvent)
      socketRef.current = socket
      await new Promise<void>((resolve, reject) => {
        const timeout = window.setTimeout(() => reject(new Error('本机会话连接超时')), 5000)
        socket.addEventListener('open', () => { window.clearTimeout(timeout); resolve() }, { once: true })
        socket.addEventListener('error', () => { window.clearTimeout(timeout); reject(new Error('本机会话连接失败')) }, { once: true })
      })
      void AvatarSession.start(avatarCanvasRef.current ?? undefined, avatarBinding.avatarId)
      await InputAudioSession.start({
        boundaryMode: () => conversationStateRef.current === 'speaking' ? 'barge_in' : 'normal',
        onUtteranceStart: () => {
          const ws = socketRef.current
          const state = conversationStateRef.current
          if (!ws || ws.readyState !== WebSocket.OPEN || awaitingAsrRef.current || !['listening', 'speaking'].includes(state)) return false
          if (state === 'speaking') {
            const activeTurn = currentServerTurnRef.current
            if (activeTurn === null) return false
            ws.send(JSON.stringify({ type: 'barge_in.detected', turn_id: activeTurn }))
            MediaSession.cancelGeneration(undefined, created.session_ref)
            AvatarSession.cancelGeneration(undefined, created.session_ref)
            setConversationState('interrupted')
          }
          inputTurnRef.current = nextTurnRef.current
          chunkSeqRef.current = 0
          setAssistantTranscript('')
          return true
        },
        onFrame: (pcm) => {
          const ws = socketRef.current
          const turn = inputTurnRef.current
          if (ws?.readyState === WebSocket.OPEN && turn !== null) {
            ws.send(ConversationClient.packAudioChunk(turn, chunkSeqRef.current++, pcm))
          }
        },
        onUtteranceEnd: () => {
          const ws = socketRef.current
          const turn = inputTurnRef.current
          if (ws?.readyState === WebSocket.OPEN && turn !== null) {
            ws.send(JSON.stringify({ type: 'audio.silence', turn_id: turn }))
            awaitingAsrRef.current = true
          }
          inputTurnRef.current = null
        },
        onError: (error) => {
          setConversationError(error.message)
          setConversationState('error')
        },
      })
      setConversationState('listening')
      ;(window as typeof window & { __CYBERWIFE_SESSION__?: unknown }).__CYBERWIFE_SESSION__ = {
        input: () => InputAudioSession.snapshot(), avatar: () => AvatarSession.snapshot(), sessionRef: created.session_ref,
      }
    } catch (value) {
      await stopConversation(false, false)
      setConversationError(value instanceof Error ? value.message : String(value))
      setConversationState('error')
    }
  }

  const handleVoiceButton = () => {
    if (conversationState === 'idle' || conversationState === 'error') void startConversation()
    else if (conversationState === 'speaking') {
      const socket = socketRef.current
      const turn = currentServerTurnRef.current
      if (socket?.readyState === WebSocket.OPEN && turn !== null) socket.send(JSON.stringify({ type: 'barge_in.detected', turn_id: turn }))
    } else void stopConversation()
  }

  const simulateError = () => {
    setConversationState('error')
    setTweaksOpen(false)
  }

  useEffect(() => () => { void stopConversation(false, false) }, [])

  const filteredMemories = memories.filter((memory) =>
    memory.content.toLowerCase().includes(memoryQuery.toLowerCase()),
  )

  const confirmDelete = async () => {
    try {
      if (deleteTarget === 'all') { await ConversationClient.purgeMemories(); setMemories([]) }
      else if (deleteTarget) { await ConversationClient.deleteMemory(Number(deleteTarget)); setMemories((items) => items.filter((item) => item.id !== deleteTarget)) }
      setSettingsStatus('删除已由本机数据库确认')
    } catch (error) { setSettingsStatus(`删除失败：${String(error)}`) }
    finally { closeDelete() }
  }

  const uploadAndActivate = async (kind: 'portrait' | 'voice', file: File): Promise<AvatarBuild | void> => {
    try {
      if (kind === 'voice' && !voiceTranscript.trim()) throw new Error('请先填写与录音完全一致的逐字稿')
      setOnboardingStatus(`正在校验${kind === 'portrait' ? '照片' : '声音'}…`)
      const uploaded = await ConversationClient.uploadAsset(kind, file)
      if (kind === 'portrait') {
        setOnboardingStatus('照片已保存，正在生成本机人物数据…')
        let build = await ConversationClient.createAvatarBuild(uploaded.id)
        const deadline = Date.now() + 30_000
        while (build.status === 'queued' || build.status === 'building') {
          if (!build.id || Date.now() >= deadline) throw new Error('人物数据生成超时，旧人物保持不变')
          await new Promise((resolve) => window.setTimeout(resolve, 250))
          build = await ConversationClient.getAvatarBuild(build.id)
        }
        if (build.status !== 'ready' && build.status !== 'active') {
          throw new Error(build.error_code || '人物数据生成失败，旧人物保持不变')
        }
        if (!build.id) throw new Error('人物数据缺少本机标识')
        const active = await ConversationClient.activateAvatarBuild(build.id)
        setActiveAvatarId(active.avatar_id)
        setActiveAvatarDerivativeId(active.id ?? build.id)
        setIdleJob(null)
        setIdleVideoReady(false)
        if (active.face_box && active.frame_size) {
          const [y1, y2, x1, x2] = active.face_box
          const [width, height] = active.frame_size
          setAvatarFocus({ x: ((x1 + x2) / 2 / width) * 100, y: ((y1 + y2) / 2 / height) * 100 })
        }
        const response = await ConversationClient.getAssets(kind)
        setAssetCounts((value) => ({ ...value, [kind]: response.items.length }))
        setActivePortraitRevision(uploaded.id)
        setOnboardingStatus('人物照片已保存；可继续生成动态待机形象')
        return active
      } else {
        await ConversationClient.activateAsset(uploaded.id)
      }
      const response = await ConversationClient.getAssets(kind)
      setAssetCounts((value) => ({ ...value, [kind]: response.items.length }))
      setOnboardingStatus('声音已保存并激活到本机')
    } catch (error) {
      setOnboardingStatus(`文件未保存：${String(error)}`)
      throw error
    }
  }

  const generateIdleAvatar = async (derivativeId: number) => {
    try {
      setOnboardingStatus('正在准备本机生成；对话模型会暂时释放显存…')
      let job = await ConversationClient.startIdleGeneration(derivativeId)
      setIdleJob(job)
      const deadline = Date.now() + 30 * 60_000
      while (job.status === 'queued' || job.status === 'generating') {
        if (Date.now() >= deadline) throw new Error('动态形象生成超时；当前人物保持不变')
        setOnboardingStatus(`本机生成中：${job.phase}（${job.progress}%）`)
        await new Promise((resolve) => window.setTimeout(resolve, 2000))
        job = await ConversationClient.getIdleGeneration(derivativeId)
        setIdleJob(job)
      }
      if (job.status === 'failed') throw new Error(job.error_code || '动态形象生成失败；当前人物保持不变')
      setOnboardingStatus('动态形象已生成，请检查正面照片与 10 秒循环视频后确认使用')
    } catch (error) {
      setOnboardingStatus(`动态形象未启用：${String(error)}`)
      throw error
    }
  }

  const approveIdleAvatar = async (derivativeId: number) => {
    try {
      setOnboardingStatus('正在构建实时口型数据并切换形象…')
      const active = await ConversationClient.approveIdleGeneration(derivativeId)
      setActiveAvatarId(active.avatar_id)
      setActiveAvatarDerivativeId(active.id ?? derivativeId)
      setIdleVideoReady(false)
      setIdleJob((current) => current ? { ...current, status: 'active', phase: 'complete', progress: 100 } : current)
      setOnboardingStatus('动态形象已启用；待机循环与实时口型均使用本次素材')
    } catch (error) {
      setOnboardingStatus(`启用失败，旧人物保持不变：${String(error)}`)
      throw error
    }
  }

  const advanceOnboarding = async () => {
    try {
      setOnboardingStatus('正在保存到本机…')
      if (onboardingStep === 0) {
        if (!consentChecked) return
        await ConversationClient.grantConsent('all')
      }
      const profileDraft = { name: characterName, user_nickname: userNickname, persona: personaText }
      if (onboardingStep === onboardingSteps.length - 1) {
        const saved = await ConversationClient.putProfile({
          name: characterName, user_nickname: userNickname, persona: personaText,
          relationship_context: '私人日常伴侣', example_dialogue: `${characterName}：我陪你。`, expected_version: profileVersion,
        })
        setProfileVersion(saved.version)
        await ConversationClient.putOnboardingDraft({
          consent_granted: true, step_completed: 4, profile_draft_json: profileDraft,
          settings_json: { completed: true, voice_transcript: voiceTranscript },
        })
        setOnboardingStatus('设置已完成')
        setOnboardingDone(true)
        return
      }
      const next = onboardingStep + 1
      await ConversationClient.putOnboardingDraft({
        consent_granted: consentChecked, step_completed: next, profile_draft_json: profileDraft,
        settings_json: { completed: false, voice_transcript: voiceTranscript },
        device_snapshot_json: onboardingStep === 1 ? { components: runtimeRows.map((row) => ({ id: row.id, status: row.status })) } : {},
      })
      setOnboardingStep(next)
      setOnboardingStatus('草稿已保存到本机')
    } catch (error) {
      setOnboardingStatus(`保存失败：${String(error)}`)
    }
  }

  const previewVoice = async (text = '你好，很高兴在这里陪你。') => {
    try {
      setOnboardingStatus('正在用当前声音生成本机试听…')
      const blob = await ConversationClient.previewVoice(text)
      const url = URL.createObjectURL(blob)
      const audio = new Audio(url)
      audio.addEventListener('ended', () => URL.revokeObjectURL(url), { once: true })
      await audio.play()
      setOnboardingStatus('正在播放本机试听')
    } catch (error) {
      setOnboardingStatus(`试听失败：${String(error)}`)
      throw error
    }
  }

  const changeNoRecord = async (enabled: boolean) => {
    if (!sessionRef.current) { setDoNotRecord(enabled); return }
    if (!enabled) {
      setSettingsStatus('本次会话已进入不记录模式，结束前不能改回记录模式')
      return
    }
    try {
      const switched = await ConversationClient.enableNoRecord(sessionRef.current)
      const previous = socketRef.current
      const next = ConversationClient.openSessionWebSocket(switched.session_ref, handleServerEvent)
      await new Promise<void>((resolve, reject) => {
        const timeout = window.setTimeout(() => reject(new Error('不记录会话迁移超时')), 5000)
        next.addEventListener('open', () => { window.clearTimeout(timeout); resolve() }, { once: true })
        next.addEventListener('error', () => { window.clearTimeout(timeout); reject(new Error('不记录会话迁移失败')) }, { once: true })
      })
      socketRef.current = next
      sessionRef.current = switched.session_ref
      previous?.close()
      setDoNotRecord(true)
      setSettingsStatus('本次会话已由后端切换为不记录，既有本次记录已清除')
    } catch (error) {
      setSettingsStatus(`切换失败，仍保持原记录策略：${String(error)}`)
    }
  }

  if (!onboardingDone) {
    return (
      <Onboarding
        step={onboardingStep}
        consentChecked={consentChecked}
        setConsentChecked={setConsentChecked}
        characterName={characterName}
        setCharacterName={setCharacterName}
        userNickname={userNickname}
        setUserNickname={setUserNickname}
        personaText={personaText}
        setPersonaText={setPersonaText}
        voiceTranscript={voiceTranscript}
        setVoiceTranscript={setVoiceTranscript}
        runtimeRows={runtimeRows}
        status={onboardingStatus}
        onPortrait={(file) => uploadAndActivate('portrait', file)}
        idleJob={idleJob}
        onGenerateIdle={generateIdleAvatar}
        onApproveIdle={approveIdleAvatar}
        onVoice={async (file) => { await uploadAndActivate('voice', file) }}
        onPreviewVoice={() => previewVoice()}
        onNext={advanceOnboarding}
        onBack={() => setOnboardingStep((current) => Math.max(0, current - 1))}
      />
    )
  }

  const content = stateContent[conversationState]
  const liveSubtitle = conversationState === 'speaking' && assistantTranscript
    ? assistantTranscript
    : conversationState === 'thinking' && userTranscript
      ? `你：${userTranscript}`
      : content.subtitle
  const voiceButtonLabel =
    conversationState === 'idle'
      ? '开始对话'
      : conversationState === 'speaking'
        ? '打断她'
        : conversationState === 'error'
          ? '重新连接'
          : '结束对话'
  const runtimeHeadline = runtimeRows.some((row) => row.status === 'error')
    ? '本机服务异常'
    : runtimeRows.some((row) => row.status === 'loading')
      ? '本机加载中'
      : runtimeRows.some((row) => row.status === 'degraded')
        ? '本机降级运行'
      : '本地在线'
  const activePortraitUrl = activePortraitRevision
    ? ConversationClient.activeAssetUrl('portrait', activePortraitRevision)
    : null
  const activeBackground = sceneBackgrounds.find((item) => item.id === backgroundId) ?? sceneBackgrounds[0]
  const activeIdleVideoUrl = activeAvatarDerivativeId !== null
    && idleJob?.derivative_id === activeAvatarDerivativeId
    && idleJob.status === 'active'
    && idleJob.has_video_preview
      ? idleJob.has_scene_previews && idleJob.scene_ids?.includes(activeBackground.id)
        ? ConversationClient.idleScenePreviewUrl(activeAvatarDerivativeId, activeBackground.id, idleJob.updated_at)
        : ConversationClient.idlePreviewUrl(activeAvatarDerivativeId, 'video', idleJob.updated_at)
      : null
  const sequenceOverlayVideoUrl = hasSceneSequence
    && (sequencePhase === 'intro' || sequencePhase === 'outro')
    && activeAvatarDerivativeId !== null
    && idleJob
    ? ConversationClient.idlePreviewUrl(
      activeAvatarDerivativeId,
      sequencePhase,
      `${idleJob.updated_at}-${sequencePhase}`,
    )
    : null

  return (
    <main
      className={`experience experience--${variant} ${compact ? 'experience--compact' : ''}`}
      data-layout={layoutMode}
      data-background={activeBackground.id}
      data-avatar-presentation={hasSingleSceneSurface ? 'complete-scene' : 'portrait'}
      aria-label="cyberWife 交互原型"
    >
      <div
        className="scene-background"
        data-testid="scene-background"
        aria-hidden="true"
        style={{ backgroundImage: `url("${activeBackground.src}")` }}
      />
      <div
        className="portrait portrait--backdrop"
        aria-hidden="true"
        style={activePortraitUrl ? {
          backgroundImage: `url("${activePortraitUrl}")`,
          backgroundPosition: `${avatarFocus.x}% ${avatarFocus.y}%`,
        } : undefined}
      />
      <div
        className="portrait portrait--foreground"
        role="img"
        aria-label="本机人物形象"
        style={activePortraitUrl ? { backgroundImage: `url("${activePortraitUrl}")` } : undefined}
      />
      {activeIdleVideoUrl && (
        <video
          key={activeIdleVideoUrl}
          className={`idle-avatar-video ${hasSceneSequence ? 'idle-avatar-video--scene' : ''} ${idleVideoReady ? 'idle-avatar-video--ready' : ''}`}
          data-testid="idle-avatar-video"
          data-avatar-layer="idle"
          data-sequence-phase={hasSceneSequence ? 'idle' : 'legacy'}
          src={activeIdleVideoUrl}
          autoPlay
          loop
          muted
          playsInline
          preload="auto"
          aria-label="本机人物动态待机画面"
          onCanPlay={() => setIdleVideoReady(true)}
          onPlaying={() => setIdleVideoReady(true)}
          onError={() => {
            setIdleVideoReady(false)
            if (hasSceneSequence) {
              setHasSceneSequence(false)
              setSequencePhase('legacy')
            }
          }}
        />
      )}
      {sequenceOverlayVideoUrl && (
        <video
          key={sequenceOverlayVideoUrl}
          className={`sequence-avatar-video idle-avatar-video--scene ${sequenceOverlayReady ? 'sequence-avatar-video--ready' : ''}`}
          data-testid="sequence-avatar-video"
          data-avatar-layer="sequence"
          data-sequence-phase={sequencePhase}
          src={sequenceOverlayVideoUrl}
          autoPlay
          muted
          playsInline
          preload="auto"
          aria-label={sequencePhase === 'intro' ? '人物走近镜头' : '人物返回沙发'}
          onCanPlay={() => setSequenceOverlayReady(true)}
          onPlaying={() => setSequenceOverlayReady(true)}
          onEnded={() => {
            if (sequencePhase === 'intro') {
              setSequenceOverlayReady(false)
              setSequencePhase('idle')
            }
          }}
          onError={() => {
            setSequenceOverlayReady(false)
            setSequencePhase('idle')
          }}
        />
      )}
      <canvas
        ref={avatarCanvasRef}
        className="avatar-video"
        data-presentation={hasSingleSceneSurface ? 'complete-scene' : 'portrait'}
        aria-label="本机实时人物画面"
        style={{ objectPosition: hasSingleSceneSurface ? 'center center' : 'right center' }}
      />
      <div className="portrait-shade" />
      <div className="ambient-grain" />

      <header className="topbar">
        <div className="brand" aria-label="cyberWife">
          <span className="brand__mark" aria-hidden="true"><i /></span>
          <span className="brand__name">cyberWife</span>
          <span className="brand__edition">LOCAL / PROTOTYPE</span>
        </div>
        <div className="topbar__actions">
          <span className="local-status" role="status" aria-live="polite" data-testid="local-status"><i />{runtimeHeadline}</span>
          <button
            ref={settingsTriggerRef}
            className="text-button"
            type="button"
            onClick={() => setSettingsOpen(true)}
          >
            设置
          </button>
        </div>
      </header>

      <section className="conversation-copy" aria-live="polite" aria-atomic="true">
        <p className="eyebrow">{content.eyebrow}</p>
        <h1>{content.title}</h1>
        <p className="subtitle" data-testid="live-subtitle">{liveSubtitle}</p>
      </section>

      {conversationState === 'error' && (
        <section className="error-card" role="alert">
          <span className="error-card__code">MIC / 01</span>
          <div>
            <strong>本机对话暂时不可用</strong>
            <p>{conversationError || '请检查麦克风权限或在运行状态中恢复对应组件。'}</p>
          </div>
          <button type="button" onClick={() => void startConversation()}>重新连接</button>
        </section>
      )}

      <section className="voice-dock" aria-label="对话控制">
        <div className={`voice-orbit voice-orbit--${conversationState}`} aria-hidden="true">
          <span /><span /><span />
        </div>
        <button
          className={`voice-button voice-button--${conversationState}`}
          type="button"
          onClick={handleVoiceButton}
          aria-label={voiceButtonLabel}
        >
          <span className="voice-button__core" aria-hidden="true">
            <i /><i /><i /><i /><i />
          </span>
        </button>
        <div className="voice-caption">
          <strong>{voiceButtonLabel}</strong>
          <span>{conversationState === 'idle' ? '点击后进入连续聆听' : '真实本机语音会话'}</span>
        </div>
      </section>

      {variant === 'signal' && (
        <aside className="signal-rail" aria-label="轻量运行信息">
          <span>SESSION 00:08:42</span>
          <span>LATENCY — 1.24s</span>
          <span>LOCAL ONLY</span>
        </aside>
      )}

      <button
        className="tweaks-trigger"
        type="button"
        onClick={() => setTweaksOpen((open) => !open)}
        aria-expanded={tweaksOpen}
      >
        {tweaksOpen ? '关闭调试' : 'Tweaks'}
      </button>

      {tweaksOpen && (
        <aside className="tweaks-panel" aria-label="原型调试面板">
          <div className="panel-heading">
            <div>
              <span className="panel-kicker">PROTOTYPE</span>
              <h2>Tweaks</h2>
            </div>
            <button type="button" onClick={() => setTweaksOpen(false)}>关闭</button>
          </div>
          <label>
            视觉方案
            <select value={variant} onChange={(event) => setVariant(event.target.value as VisualVariant)}>
              <option value="cinematic">Cinematic</option>
              <option value="quiet">Quiet</option>
              <option value="signal">Signal</option>
            </select>
          </label>
          <label className="switch-row">
            <span>紧凑窗口预览</span>
            <input type="checkbox" checked={compact} onChange={(event) => setCompact(event.target.checked)} />
          </label>
          <button className="secondary-button" type="button" onClick={simulateError}>模拟麦克风错误</button>
          <button className="secondary-button" type="button" onClick={() => setOnboardingDone(false)}>重看首次设置</button>
        </aside>
      )}

      {settingsOpen && (
        <SettingsDrawer
          activeTab={settingsTab}
          setActiveTab={setSettingsTab}
          onClose={closeSettings}
          closeRef={drawerCloseRef}
          characterName={characterName}
          setCharacterName={setCharacterName}
          userNickname={userNickname}
          setUserNickname={setUserNickname}
          personaText={personaText}
          setPersonaText={setPersonaText}
          theme={theme}
          setTheme={setTheme}
          backgroundId={activeBackground.id}
          setBackgroundId={setBackgroundId}
          memories={filteredMemories}
          memoryQuery={memoryQuery}
          setMemoryQuery={setMemoryQuery}
          editingMemory={editingMemory}
          setEditingMemory={setEditingMemory}
          setMemories={setMemories}
          newMemory={newMemory}
          setNewMemory={setNewMemory}
          memoryCandidates={memoryCandidates}
          onCreateMemory={async () => {
            const content = newMemory.trim()
            if (!content) { setSettingsStatus('请输入需要记住的内容'); return }
            try {
              const created = await ConversationClient.createMemory(content)
              setMemories((items) => [toMemoryRecord(created), ...items.filter((item) => item.id !== String(created.id))])
              setNewMemory('')
              setSettingsStatus('记忆已保存到本机并建立检索索引')
            } catch (error) { setSettingsStatus(`记忆未保存：${String(error)}`) }
          }}
          onConfirmCandidate={async (candidate) => {
            try {
              const created = await ConversationClient.confirmMemoryCandidate(candidate)
              setMemories((items) => [toMemoryRecord(created), ...items.filter((item) => item.id !== String(created.id))])
              setMemoryCandidates((items) => items.filter((item) => item !== candidate))
              setSettingsStatus('候选已确认并进入长期记忆')
            } catch (error) { setSettingsStatus(`候选未确认：${String(error)}`) }
          }}
          onRejectCandidate={async (candidate) => {
            try {
              await ConversationClient.rejectMemoryCandidate(candidate)
              setMemoryCandidates((items) => items.filter((item) => item !== candidate))
              setSettingsStatus('候选已忽略，不会进入长期记忆')
            } catch (error) { setSettingsStatus(`候选未忽略：${String(error)}`) }
          }}
          requestDelete={requestDelete}
          doNotRecord={doNotRecord}
          setDoNotRecord={(enabled) => { void changeNoRecord(enabled) }}
          profileVersion={profileVersion}
          setProfileVersion={setProfileVersion}
          settingsStatus={settingsStatus}
          setSettingsStatus={setSettingsStatus}
          assetCounts={assetCounts}
          runtimeRows={runtimeRows}
          idleJob={idleJob}
          onPortrait={async (file) => {
            setSettingsStatus('正在保存照片并创建安全版本…')
            try {
              const build = await uploadAndActivate('portrait', file)
              setSettingsStatus('照片已保存，正在等待动态形象生成')
              return build
            } catch (error) {
              setSettingsStatus(`照片未保存：${String(error)}`)
              throw error
            }
          }}
          onGenerateIdle={async (derivativeId) => {
            setSettingsStatus('正在本机生成动态形象；实时对话暂时不可用')
            try {
              await generateIdleAvatar(derivativeId)
              setSettingsStatus('候选已生成，请预览后确认')
            } catch (error) {
              setSettingsStatus(`动态形象生成失败：${String(error)}`)
              throw error
            }
          }}
          onApproveIdle={async (derivativeId) => {
            try {
              await approveIdleAvatar(derivativeId)
              setSettingsStatus('动态人物新版本已激活')
            } catch (error) {
              setSettingsStatus(`动态人物未激活：${String(error)}`)
              throw error
            }
          }}
          onPortraitRestored={(active) => {
            setActiveAvatarId(active.avatar_id)
            setActiveAvatarDerivativeId(active.id ?? null)
            setIdleJob(null)
            setIdleVideoReady(false)
            if (active.id) {
              void ConversationClient.getIdleGeneration(active.id)
                .then(setIdleJob)
                .catch(() => {})
            }
            if (active.asset_id) setActivePortraitRevision(active.asset_id)
            if (active.face_box && active.frame_size) {
              const [y1, y2, x1, x2] = active.face_box
              const [width, height] = active.frame_size
              setAvatarFocus({ x: ((x1 + x2) / 2 / width) * 100, y: ((y1 + y2) / 2 / height) * 100 })
            }
          }}
          onAssetUploaded={async (kind, file) => { try { await uploadAndActivate(kind, file); setSettingsStatus(`${kind === 'portrait' ? '人物' : '声音'}新版本已激活`) } catch (error) { setSettingsStatus(`新版本未激活：${String(error)}`) } }}
          onPreviewVoice={async () => { try { await previewVoice(); setSettingsStatus('正在播放当前声音的真实本机试听') } catch (error) { setSettingsStatus(`试听失败：${String(error)}`) } }}
        />
      )}

      {deleteTarget && (
        <ConfirmDialog
          isAll={deleteTarget === 'all'}
          onCancel={closeDelete}
          onConfirm={confirmDelete}
        />
      )}
    </main>
  )
}

interface OnboardingProps {
  step: number
  consentChecked: boolean
  setConsentChecked: (checked: boolean) => void
  characterName: string
  setCharacterName: (value: string) => void
  userNickname: string
  setUserNickname: (value: string) => void
  personaText: string
  setPersonaText: (value: string) => void
  voiceTranscript: string
  setVoiceTranscript: (value: string) => void
  runtimeRows: RuntimeService[]
  status: string
  onPortrait: (file: File) => Promise<AvatarBuild | void>
  idleJob: IdleGenerationJob | null
  onGenerateIdle: (derivativeId: number) => Promise<void>
  onApproveIdle: (derivativeId: number) => Promise<void>
  onVoice: (file: File) => Promise<void>
  onPreviewVoice: () => Promise<void>
  onNext: () => Promise<void>
  onBack: () => void
}

function Onboarding(props: OnboardingProps) {
  const idleBusy = props.idleJob?.status === 'queued' || props.idleJob?.status === 'generating'
  const canContinue = (props.step !== 0 || props.consentChecked) && !idleBusy
  return (
    <main className="onboarding">
      <div className="onboarding__portrait" />
      <div className="onboarding__veil" />
      <header className="onboarding__header">
        <div className="brand">
          <span className="brand__mark" aria-hidden="true"><i /></span>
          <span className="brand__name">cyberWife</span>
        </div>
        <span className="local-status"><i />仅在本机保存</span>
      </header>
      <section className="setup-shell">
        <nav className="step-list" aria-label="首次设置步骤">
          {onboardingSteps.map((item, index) => (
            <div
              key={item.id}
              className={`step-list__item ${index === props.step ? 'is-active' : index < props.step ? 'is-done' : ''}`}
              aria-current={index === props.step ? 'step' : undefined}
            >
              <span>{String(index + 1).padStart(2, '0')}</span>
              {item.label}
            </div>
          ))}
        </nav>
        <div className="setup-card">
          <p className="panel-kicker">SETUP / {String(props.step + 1).padStart(2, '0')}</p>
          <SetupStep
            step={props.step}
            consentChecked={props.consentChecked}
            setConsentChecked={props.setConsentChecked}
            characterName={props.characterName}
            setCharacterName={props.setCharacterName}
            userNickname={props.userNickname}
            setUserNickname={props.setUserNickname}
            personaText={props.personaText}
            setPersonaText={props.setPersonaText}
            voiceTranscript={props.voiceTranscript}
            setVoiceTranscript={props.setVoiceTranscript}
            runtimeRows={props.runtimeRows}
            onPortrait={props.onPortrait}
            idleJob={props.idleJob}
            onGenerateIdle={props.onGenerateIdle}
            onApproveIdle={props.onApproveIdle}
            onVoice={props.onVoice}
            onPreviewVoice={props.onPreviewVoice}
          />
          <p role="status" data-testid="onboarding-status">{props.status}</p>
          <div className="setup-actions">
            <button className="secondary-button" type="button" onClick={props.onBack} disabled={props.step === 0}>上一步</button>
            <button className="primary-button" type="button" onClick={() => void props.onNext()} disabled={!canContinue}>
              {props.step === onboardingSteps.length - 1 ? '进入她的世界' : '继续'}
            </button>
          </div>
        </div>
      </section>
    </main>
  )
}

interface SetupStepProps {
  step: number
  consentChecked: boolean
  setConsentChecked: (checked: boolean) => void
  characterName: string
  setCharacterName: (value: string) => void
  userNickname: string
  setUserNickname: (value: string) => void
  personaText: string
  setPersonaText: (value: string) => void
  voiceTranscript: string
  setVoiceTranscript: (value: string) => void
  runtimeRows: RuntimeService[]
  onPortrait: (file: File) => Promise<AvatarBuild | void>
  idleJob: IdleGenerationJob | null
  onGenerateIdle: (derivativeId: number) => Promise<void>
  onApproveIdle: (derivativeId: number) => Promise<void>
  onVoice: (file: File) => Promise<void>
  onPreviewVoice: () => Promise<void>
}

function SetupStep(props: SetupStepProps) {
  if (props.step === 0) {
    return (
      <div className="setup-content">
        <p className="eyebrow">只属于这台电脑</p>
        <h1>把她留在本机。</h1>
        <p className="setup-lead">照片、声音、对话和记忆默认只在本机处理。日常体验会保持沉浸，真实素材的控制权始终属于你们。</p>
        <div className="privacy-points">
          <div><span>01</span><strong>本地推理</strong><p>断网后仍可完成完整对话。</p></div>
          <div><span>02</span><strong>随时删除</strong><p>素材、会话和记忆都有明确删除入口。</p></div>
        </div>
        <label className="consent-check">
          <input type="checkbox" checked={props.consentChecked} onChange={(event) => props.setConsentChecked(event.target.checked)} />
          <span>我确认拥有照片和声音的使用授权，并仅用于私人、非商业用途。</span>
        </label>
      </div>
    )
  }
  if (props.step === 1) {
    return (
      <div className="setup-content">
        <p className="eyebrow">真实运行检查</p>
        <h1>她需要的，都在这里。</h1>
        <p className="setup-lead">以下状态来自本机组件功能探针；未就绪的项目可稍后在运行状态中单项恢复。</p>
        <div className="runtime-grid">
          {props.runtimeRows.map((service) => (
            <div className="runtime-item" key={service.id} data-status={service.status}><i /><span><strong>{service.name}</strong><small>{service.detail}</small></span><b>{service.status === 'ready' ? '就绪' : service.status === 'error' ? '错误' : service.status === 'degraded' ? '已降级' : '加载中'}</b></div>
          ))}
        </div>
      </div>
    )
  }
  if (props.step === 2) {
    return <PortraitSetup onPortrait={props.onPortrait} idleJob={props.idleJob} onGenerateIdle={props.onGenerateIdle} onApproveIdle={props.onApproveIdle} />
  }
  if (props.step === 3) {
    return (
      <div className="setup-content">
        <p className="eyebrow">声音样本</p>
        <h1>声音，会记住语气。</h1>
        <p className="setup-lead">使用 5–15 秒干净单人录音，并填写完全一致的逐字稿。声音仅在本机校验并保存版本。</p>
        <div className="voice-upload-row">
          <label className="file-drop file-drop--compact">
            <input type="file" accept="audio/wav,audio/mpeg" onChange={(event) => { const file = event.target.files?.[0]; if (file) void props.onVoice(file).catch(() => {}) }} />
            <span>选择参考声音</span>
            <small>WAV 或 MP3</small>
          </label>
          <label className="field field--grow">录音逐字稿<textarea value={props.voiceTranscript} onChange={(event) => props.setVoiceTranscript(event.target.value)} /></label>
        </div>
        <button className="secondary-button" type="button" onClick={() => { void props.onPreviewVoice() }}>试听当前声音</button>
      </div>
    )
  }
  return (
    <div className="setup-content">
      <p className="eyebrow">人设关系</p>
      <h1>熟悉，不需要解释。</h1>
      <p className="setup-lead">这些信息会成为她说话的底色，后续可以随时修改。</p>
      <div className="form-grid">
        <label className="field">她的名字<input value={props.characterName} onChange={(event) => props.setCharacterName(event.target.value)} /></label>
        <label className="field">她如何称呼你<input value={props.userNickname} onChange={(event) => props.setUserNickname(event.target.value)} /></label>
        <label className="field field--wide">相处方式<textarea value={props.personaText} onChange={(event) => props.setPersonaText(event.target.value)} /></label>
      </div>
    </div>
  )
}

async function cropPortrait(file: File, zoom: number, positionX: number, positionY: number): Promise<File> {
  const bitmap = await createImageBitmap(file)
  const width = 768
  const height = 960
  const canvas = document.createElement('canvas')
  canvas.width = width; canvas.height = height
  const context = canvas.getContext('2d')
  if (!context) throw new Error('当前浏览器无法创建人物裁切画布')
  const baseScale = Math.max(width / bitmap.width, height / bitmap.height)
  const scale = baseScale * zoom
  const drawWidth = bitmap.width * scale
  const drawHeight = bitmap.height * scale
  const overflowX = Math.max(0, drawWidth - width)
  const overflowY = Math.max(0, drawHeight - height)
  const x = -overflowX * ((positionX + 100) / 200)
  const y = -overflowY * ((positionY + 100) / 200)
  context.drawImage(bitmap, x, y, drawWidth, drawHeight)
  bitmap.close()
  const blob = await new Promise<Blob>((resolve, reject) => canvas.toBlob((value) => value ? resolve(value) : reject(new Error('人物裁切失败')), 'image/png', 0.95))
  return new File([blob], `${file.name.replace(/\.[^.]+$/, '')}-crop.png`, { type: 'image/png' })
}

function PortraitSetup({ onPortrait, idleJob, onGenerateIdle, onApproveIdle, compact = false }: {
  onPortrait: (file: File) => Promise<AvatarBuild | void>
  idleJob: IdleGenerationJob | null
  onGenerateIdle: (derivativeId: number) => Promise<void>
  onApproveIdle: (derivativeId: number) => Promise<void>
  compact?: boolean
}) {
  const [source, setSource] = useState<File | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [zoom, setZoom] = useState(1)
  const [positionX, setPositionX] = useState(0)
  const [positionY, setPositionY] = useState(0)
  const [hidePreviousJob, setHidePreviousJob] = useState(false)
  const [reviewSceneId, setReviewSceneId] = useState('blue-hour-living')
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview) }, [preview])
  useEffect(() => {
    if (idleJob?.status === 'queued' || idleJob?.status === 'generating') setHidePreviousJob(false)
  }, [idleJob])
  const [submitting, setSubmitting] = useState(false)
  const saveCrop = async (file = source) => {
    if (!file) return
    setSubmitting(true)
    try {
      const build = await onPortrait(await cropPortrait(file, zoom, positionX, positionY))
      if (!build?.id) throw new Error('人物数据缺少本机标识')
      await onGenerateIdle(build.id)
    } finally {
      setSubmitting(false)
    }
  }
  return (
    <div className={`setup-content setup-content--split ${compact ? 'setup-content--compact' : ''}`}>
      <div>
        {!compact && <><p className="eyebrow">人物形象</p><h1>让她看起来熟悉。</h1></>}
        <p className="setup-lead">选择正面、自然闭嘴、下巴无遮挡的照片。可调整缩放和取景，裁切结果只发送到本机保存。</p>
        <label className="file-drop">
          <input type="file" accept="image/jpeg,image/png" onChange={(event) => {
            const file = event.target.files?.[0]
            if (!file) return
            if (preview) URL.revokeObjectURL(preview)
            setSource(file); setPreview(URL.createObjectURL(file)); setZoom(1); setPositionX(0); setPositionY(0); setHidePreviousJob(true)
          }} />
          <span>选择授权照片</span><small>JPG 或 PNG · 建议 1600px 以上</small>
        </label>
        {source && <div className="crop-controls">
          <label>缩放<input type="range" min="1" max="2.5" step="0.05" value={zoom} onChange={(event) => setZoom(Number(event.target.value))} /></label>
          <label>水平<input type="range" min="-100" max="100" value={positionX} onChange={(event) => setPositionX(Number(event.target.value))} /></label>
          <label>垂直<input type="range" min="-100" max="100" value={positionY} onChange={(event) => setPositionY(Number(event.target.value))} /></label>
          <button className="primary-button" type="button" disabled={submitting} onClick={() => { void saveCrop().catch(() => {}) }}>
            {submitting ? '正在本机生成…' : '生成动态形象'}
          </button>
        </div>}
      </div>
      <div className="portrait-review">
        <div className="portrait-preview" role="img" aria-label="人物裁切预览" style={preview ? { backgroundImage: `url("${preview}")`, backgroundSize: `${zoom * 100}% auto`, backgroundPosition: `${(positionX + 100) / 2}% ${(positionY + 100) / 2}%` } : undefined} />
        {idleJob && !hidePreviousJob && <div className="idle-job" aria-live="polite">
          {(idleJob.status === 'queued' || idleJob.status === 'generating') && <>
            <strong>正在生成动态形象</strong>
            <progress max="100" value={idleJob.progress} />
            <small>{idleJob.phase} · {idleJob.progress}%</small>
          </>}
          {(idleJob.status === 'awaiting_approval' || idleJob.status === 'active') && <>
            <strong>{idleJob.status === 'active' ? '当前动态形象' : '启用前人工检查'}</strong>
            <div className="idle-review-grid">
              <figure><img src={ConversationClient.idlePreviewUrl(idleJob.derivative_id, 'frontal', idleJob.updated_at)} alt="标准化正面照片" /><figcaption>正面标准照</figcaption></figure>
              <figure><video src={ConversationClient.idlePreviewUrl(idleJob.derivative_id, 'video', idleJob.updated_at)} autoPlay loop muted playsInline controls /><figcaption>10 秒首尾闭环待机</figcaption></figure>
              {idleJob.has_scene_previews && idleJob.scene_ids?.includes(reviewSceneId) && <figure>
                <video src={ConversationClient.idleScenePreviewUrl(idleJob.derivative_id, reviewSceneId, idleJob.updated_at)} autoPlay loop muted playsInline controls />
                <figcaption>整个人物离线抠像 · 场景预合成</figcaption>
              </figure>}
            </div>
            {idleJob.has_scene_previews && <div className="idle-scene-picker" aria-label="待机场景预览">
              {(idleJob.scene_ids || []).map((sceneId) => <button
                type="button"
                key={sceneId}
                aria-pressed={reviewSceneId === sceneId}
                onClick={() => setReviewSceneId(sceneId)}
              >{sceneBackgrounds.find((item) => item.id === sceneId)?.label || sceneId}</button>)}
            </div>}
            {idleJob.status === 'awaiting_approval' && <button className="primary-button" type="button" onClick={() => { void onApproveIdle(idleJob.derivative_id).catch(() => {}) }}>确认并使用动态形象</button>}
          </>}
          {idleJob.status === 'failed' && <small className="idle-job__error">生成失败：{idleJob.error_code || '未知错误'}；原人物未被替换。</small>}
        </div>}
      </div>
    </div>
  )
}

interface SettingsDrawerProps {
  activeTab: SettingsTab
  setActiveTab: (tab: SettingsTab) => void
  onClose: () => void
  closeRef: React.RefObject<HTMLButtonElement | null>
  characterName: string
  setCharacterName: (value: string) => void
  userNickname: string
  setUserNickname: (value: string) => void
  personaText: string
  setPersonaText: (value: string) => void
  theme: ThemeMode
  setTheme: (theme: ThemeMode) => void
  backgroundId: string
  setBackgroundId: (id: string) => void
  memories: MemoryRecord[]
  memoryQuery: string
  setMemoryQuery: (value: string) => void
  editingMemory: string | null
  setEditingMemory: (id: string | null) => void
  setMemories: React.Dispatch<React.SetStateAction<MemoryRecord[]>>
  newMemory: string
  setNewMemory: (content: string) => void
  memoryCandidates: MemoryCandidate[]
  onCreateMemory: () => Promise<void>
  onConfirmCandidate: (candidate: MemoryCandidate) => Promise<void>
  onRejectCandidate: (candidate: MemoryCandidate) => Promise<void>
  requestDelete: (id: string | 'all') => void
  doNotRecord: boolean
  setDoNotRecord: (enabled: boolean) => void
  profileVersion: number
  setProfileVersion: (version: number) => void
  settingsStatus: string
  setSettingsStatus: (status: string) => void
  assetCounts: { portrait: number; voice: number }
  runtimeRows: RuntimeService[]
  idleJob: IdleGenerationJob | null
  onPortrait: (file: File) => Promise<AvatarBuild | void>
  onGenerateIdle: (derivativeId: number) => Promise<void>
  onApproveIdle: (derivativeId: number) => Promise<void>
  onPortraitRestored: (active: AvatarBuild) => void
  onAssetUploaded: (kind: 'portrait' | 'voice', file: File) => Promise<void>
  onPreviewVoice: () => Promise<void>
}

function SettingsDrawer(props: SettingsDrawerProps) {
  const tabs: Array<{ id: SettingsTab; label: string }> = [
    { id: 'profile', label: '人物' },
    { id: 'voice', label: '声音' },
    { id: 'persona', label: '人设' },
    { id: 'memory', label: '记忆' },
    { id: 'privacy', label: '隐私' },
    { id: 'runtime', label: '运行状态' },
  ]
  return (
    <div className="drawer-layer" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && props.onClose()}>
      <aside className="settings-drawer" role="dialog" aria-modal="true" aria-labelledby="settings-title">
        <header className="drawer-header">
          <div><span className="panel-kicker">LOCAL SETTINGS</span><h2 id="settings-title">她的世界</h2></div>
          <button ref={props.closeRef} className="text-button" type="button" onClick={props.onClose}>关闭</button>
        </header>
        <nav className="drawer-tabs" aria-label="设置分类">
          {tabs.map((tab) => (
            <button type="button" key={tab.id} className={props.activeTab === tab.id ? 'is-active' : ''} onClick={() => props.setActiveTab(tab.id)}>{tab.label}</button>
          ))}
        </nav>
        <div className="drawer-content">
          <p role="status" data-testid="settings-api-status">{props.settingsStatus}</p>
          {props.activeTab === 'profile' && (
            <section>
              <SectionHeader index="01" title="人物形象" description="新文件先由本机校验并创建版本，成功后原子激活；上一可用版本始终可恢复。" />
              <div className="profile-preview"><div className="profile-preview__image" /><div><strong>{props.characterName}</strong><span>{props.assetCounts.portrait} 个本机版本</span><button className="secondary-button" type="button" onClick={async () => { try { const restored = await ConversationClient.restoreAsset('portrait') as AvatarBuild; props.onPortraitRestored(restored); props.setSettingsStatus('已恢复上一人物版本') } catch (error) { props.setSettingsStatus(`恢复失败：${String(error)}`) } }}>恢复上一版</button></div></div>
              <hr />
              <SectionHeader index="02" title="相处空间" description="背景与人物独立保存在本机；切换空间不会替换当前人物或中断对话。" />
              <div className="background-grid" role="radiogroup" aria-label="本地背景">
                {sceneBackgrounds.map((background) => (
                  <button
                    type="button"
                    role="radio"
                    aria-checked={props.backgroundId === background.id}
                    className={props.backgroundId === background.id ? 'background-card is-active' : 'background-card'}
                    key={background.id}
                    onClick={() => {
                      props.setBackgroundId(background.id)
                      props.setSettingsStatus(`已切换到${background.label}，选择只保存在本机`)
                    }}
                  >
                    <img src={background.src} alt="" />
                    <span><strong>{background.label}</strong><small>{background.description}</small></span>
                  </button>
                ))}
              </div>
              <hr />
              <PortraitSetup onPortrait={props.onPortrait} idleJob={props.idleJob} onGenerateIdle={props.onGenerateIdle} onApproveIdle={props.onApproveIdle} compact />
              <hr />
              <SectionHeader index="03" title="界面主题" description="默认使用电影感深色，也可选择柔和浅色或跟随系统。" />
              <div className="segmented" role="radiogroup" aria-label="界面主题">
                {([
                  ['cinematic-dark', '电影深色'],
                  ['soft-light', '柔和浅色'],
                  ['system', '跟随系统'],
                ] as Array<[ThemeMode, string]>).map(([id, label]) => (
                  <button role="radio" aria-checked={props.theme === id} className={props.theme === id ? 'is-active' : ''} type="button" key={id} onClick={() => props.setTheme(id)}>{label}</button>
                ))}
              </div>
            </section>
          )}
          {props.activeTab === 'voice' && (
            <section>
              <SectionHeader index="02" title="声音版本" description="参考声音只保存在本机；新版本通过校验后原子激活。" />
              <div className="profile-preview"><div><strong>CosyVoice 参考声音</strong><span>{props.assetCounts.voice} 个本机版本</span><label className="secondary-button asset-file-button">选择新声音<input type="file" accept="audio/wav,audio/mpeg" onChange={(event) => { const file = event.target.files?.[0]; if (file) void props.onAssetUploaded('voice', file) }} /></label><button className="secondary-button" type="button" onClick={() => { void props.onPreviewVoice() }}>试听当前声音</button><button className="secondary-button" type="button" onClick={async () => { try { await ConversationClient.restoreAsset('voice'); props.setSettingsStatus('已恢复上一声音版本') } catch (error) { props.setSettingsStatus(`恢复失败：${String(error)}`) } }}>恢复上一版</button></div></div>
            </section>
          )}
          {props.activeTab === 'persona' && (
            <section>
              <SectionHeader index="01" title="称呼与关系" description="这些内容决定日常对话的亲近程度。" />
              <div className="form-grid">
                <label className="field">她的名字<input value={props.characterName} onChange={(event) => props.setCharacterName(event.target.value)} /></label>
                <label className="field">她如何称呼你<input value={props.userNickname} onChange={(event) => props.setUserNickname(event.target.value)} /></label>
              </div>
              <label className="field">相处方式<textarea value={props.personaText} onChange={(event) => props.setPersonaText(event.target.value)} /></label>
              <div className="example-dialogue"><span>示例对话</span><p><b>你：</b>今天有点累。</p><p><b>{props.characterName}：</b>那就先别想别的了。坐一会儿，我陪你慢慢缓过来。</p></div>
              <button className="primary-button" type="button" onClick={async () => { try { const saved: ApiProfile = await ConversationClient.putProfile({ name: props.characterName, user_nickname: props.userNickname, persona: props.personaText, relationship_context: '私人日常伴侣', example_dialogue: `${props.characterName}：我陪你。`, expected_version: props.profileVersion }); props.setProfileVersion(saved.version); props.setSettingsStatus('人设已保存到本机') } catch (error) { props.setSettingsStatus(`保存失败：${String(error)}`) } }}>保存人设</button>
            </section>
          )}
          {props.activeTab === 'memory' && (
            <section>
              <SectionHeader index="03" title="她记得的事" description="你可以直接添加，也可以在一轮对话结束后确认候选；未确认候选不会参与回答。" />
              <div className="memory-create">
                <label className="field field--grow">添加一条长期记忆<input value={props.newMemory} maxLength={2000} onChange={(event) => props.setNewMemory(event.target.value)} placeholder="例如：我周末喜欢去公园散步" /></label>
                <button className="primary-button" type="button" onClick={() => { void props.onCreateMemory() }} disabled={!props.newMemory.trim()}>记住</button>
              </div>
              {props.memoryCandidates.length > 0 && (
                <section className="memory-candidates" aria-labelledby="memory-candidates-title">
                  <header><strong id="memory-candidates-title">等待你确认</strong><span>来自已结束的本机会话</span></header>
                  {props.memoryCandidates.map((candidate) => (
                    <article key={`${candidate.source_session_id}-${candidate.source_turn_id}-${candidate.content}`}>
                      <p>{candidate.content}</p>
                      <footer>
                        <span>会话 {candidate.source_session_id} · {candidate.reason === 'temporary_context' ? '可能只是临时信息' : candidate.reason}</span>
                        <div><button type="button" onClick={() => { void props.onRejectCandidate(candidate) }}>忽略</button><button type="button" onClick={() => { void props.onConfirmCandidate(candidate) }}>确认记住</button></div>
                      </footer>
                    </article>
                  ))}
                </section>
              )}
              <label className="search-field"><span>搜索记忆</span><input value={props.memoryQuery} onChange={(event) => props.setMemoryQuery(event.target.value)} placeholder="输入关键词" /></label>
              <div className="memory-list">
                {props.memories.length === 0 ? <div className="empty-state"><strong>还没有长期记忆</strong><span>你可以在上方直接添加；对话结束后，可能的信息会先等待你确认。</span></div> : props.memories.map((memory) => (
                  <article className="memory-card" key={memory.id}>
                    {props.editingMemory === memory.id ? (
                      <textarea autoFocus value={memory.content} onChange={(event) => props.setMemories((items) => items.map((item) => item.id === memory.id ? { ...item, content: event.target.value, edited: true } : item))} />
                    ) : <p>{memory.content}</p>}
                    <footer><span>{memory.source} · {memory.createdAt}{memory.edited ? ' · 已编辑' : ''}</span><div><button type="button" onClick={async () => { if (props.editingMemory === memory.id) { try { await ConversationClient.editMemory(Number(memory.id), memory.content); props.setSettingsStatus('记忆已更新') } catch (error) { props.setSettingsStatus(`更新失败：${String(error)}`); return } } props.setEditingMemory(props.editingMemory === memory.id ? null : memory.id) }}>{props.editingMemory === memory.id ? '完成' : '编辑'}</button><button className="danger-link" type="button" onClick={() => props.requestDelete(memory.id)}>删除</button></div></footer>
                  </article>
                ))}
              </div>
            </section>
          )}
          {props.activeTab === 'privacy' && (
            <section>
              <SectionHeader index="04" title="隐私与数据" description="授权、会话记录策略和删除动作均由本机后端确认。" />
              <label className="privacy-toggle"><span><strong>本次不记录</strong><small>立即清除本次既有业务记录，后续不生成会话或长期记忆</small></span><input type="checkbox" checked={props.doNotRecord} onChange={(event) => props.setDoNotRecord(event.target.checked)} /></label>
              <div><button className="secondary-button" type="button" onClick={async () => { await ConversationClient.grantConsent('all'); props.setSettingsStatus('真人素材授权已记录') }}>授予素材授权</button><button className="danger-link" type="button" onClick={async () => { await ConversationClient.revokeConsent('all'); props.setSettingsStatus('授权已撤销，素材已停用') }}>撤销素材授权</button></div>
              <div className="privacy-ledger"><div><span>人物与声音</span><b>仅本机</b></div><div><span>会话记录</span><b>仅本机</b></div><div><span>外部网络请求</span><b>关闭</b></div></div>
              <div className="danger-zone"><span className="panel-kicker">DANGER ZONE</span><h3>清空全部记忆</h3><p>确认后同时删除源记录、全文索引和向量索引，操作不可恢复。</p><button type="button" onClick={() => props.requestDelete('all')}>清空全部记忆</button></div>
            </section>
          )}
          {props.activeTab === 'runtime' && (
            <section>
              <SectionHeader index="06" title="运行状态" description="状态来自本机 Gateway 的真实组件快照。" />
              <div className="runtime-list">{props.runtimeRows.map((service) => <div className="runtime-row" key={service.id}><i /><span><strong>{service.name}</strong><small>{service.detail}</small></span><b>{service.status}</b><button type="button" onClick={async () => { props.setSettingsStatus(`${service.name} 正在恢复…`); try { await ConversationClient.retryComponent(service.id); props.setSettingsStatus(`${service.name} 已通过功能探针`) } catch (error) { props.setSettingsStatus(`${service.name} 恢复失败：${String(error)}`) } }}>恢复</button></div>)}</div>
              <div className="gpu-meter"><header><span>显存预算（模拟）</span><b>17.2 / 24 GB</b></header><div><i /></div><p>预计保留 6.8GB 缓冲；实际数据以后端监测为准。</p></div>
              <button className="secondary-button" type="button" onClick={async () => { props.setSettingsStatus('正在恢复并复检全部服务…'); try { await ConversationClient.recoverAll(); props.setSettingsStatus('全部服务已通过功能探针') } catch (error) { props.setSettingsStatus(`全量恢复失败：${String(error)}`) } }}>恢复并重新检查全部服务</button>
            </section>
          )}
        </div>
      </aside>
    </div>
  )
}

function SectionHeader({ index, title, description }: { index: string; title: string; description: string }) {
  return <header className="section-header"><span>{index}</span><div><h3>{title}</h3><p>{description}</p></div></header>
}

function ConfirmDialog({ isAll, onCancel, onConfirm }: { isAll: boolean; onCancel: () => void; onConfirm: () => void }) {
  return (
    <div className="confirm-layer" role="presentation">
      <section className="confirm-dialog" role="alertdialog" aria-modal="true" aria-labelledby="confirm-title">
        <span className="panel-kicker">IRREVERSIBLE</span>
        <h2 id="confirm-title">{isAll ? '清空全部记忆？' : '删除这条记忆？'}</h2>
        <p>{isAll ? '将同时删除源记录、全文索引和向量索引，无法恢复。' : '删除后，她不会再通过这条记录回忆相关内容。'}</p>
        <div><button className="secondary-button" type="button" onClick={onCancel}>取消</button><button className="danger-button" type="button" onClick={onConfirm}>确认删除</button></div>
      </section>
    </div>
  )
}

export default App
