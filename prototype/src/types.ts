export type ConversationState =
  | 'idle'
  | 'listening'
  | 'thinking'
  | 'speaking'
  | 'interrupted'
  | 'error'

export type ThemeMode = 'cinematic-dark' | 'soft-light' | 'system'
export type VisualVariant = 'cinematic' | 'quiet' | 'signal'
export type SettingsTab = 'profile' | 'sources' | 'voice' | 'input' | 'persona' | 'memory' | 'privacy' | 'runtime'

export interface MemoryRecord {
  id: string
  content: string
  source: string
  createdAt: string
  edited?: boolean
}

export interface RuntimeService {
  id: string
  name: string
  detail: string
  status: 'ready' | 'loading' | 'degraded' | 'error'
}
