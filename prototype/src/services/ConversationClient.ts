// ConversationClient — REST + WebSocket 客户端。
//
// 公共实现-contracts §6 REST 端点与 §6 WS 事件合同。
// M1 阶段：实现 GET/PUT onboarding/draft、GET/PUT profile、GET health。
// M2 起逐步接入全部 17 REST + 8 WS。

import { MediaSession } from "./MediaSession";
import { AvatarSession } from "./AvatarSession";

const GATEWAY_BASE = (typeof window !== "undefined" && (window as any).CYBERWIFE_GATEWAY) || "http://127.0.0.1:7860";
const WS_BASE = GATEWAY_BASE.replace(/^http/, "ws");

export interface HealthResponse {
  status: "ready" | "loading" | "degraded" | "error";
  components: Record<string, { status: string; logical_id?: string; fallback_active?: boolean }>;
  resources: {
    vram_used_gb: number | null;
    vram_total_gb: number | null;
    ram_used_gb: number | null;
    ram_total_gb: number | null;
    disk_free_gb: number | null;
    cache_writes_allowed?: boolean;
    storage_pressure?: "normal" | "low";
  };
  version: { app: string; schema: string };
}

export interface OnboardingDraft {
  id: 1;
  consent_granted: boolean;
  step_completed: number;
  asset_consent_at: string | null;
  profile_draft_json: Record<string, unknown>;
  settings_json: Record<string, unknown>;
  device_snapshot_json: Record<string, unknown>;
  updated_at: string;
}

export interface Profile {
  id: number;
  name: string;
  user_nickname: string;
  persona: string;
  relationship_context: string;
  example_dialogue: string;
  version: number;
  updated_at: string;
}

export interface ErrorEnvelope {
  code: string;
  message: string;
  user_action: string;
  trace_id: string;
  retryable: boolean;
}

// WS 6 字段 envelope（implementation-contracts §6）
export interface WsEnvelope {
  type: string;
  session_id: string;
  turn_id: number | null;
  event_seq: number;
  occurred_at: string;
  payload: Record<string, unknown>;
}

export interface ConversationState {
  previous: string;
  current: string;
  reason: string;
}

export interface SessionCreated {
  id: string;
  session_ref: string;
  state: string;
  recording_policy: "standard" | "none";
  next_turn_id: number;
  ws_url: string;
}

export interface AvatarBuild {
  id?: number;
  asset_id?: number;
  engine: "wav2lip" | "musetalk";
  avatar_id: string;
  source_sha256: string | null;
  status: "queued" | "building" | "ready" | "active" | "archived" | "failed" | "legacy_fallback";
  frame_count?: number;
  frame_size?: [number, number] | null;
  face_box?: [number, number, number, number] | null;
  error_code?: string | null;
}

export interface IdleGenerationJob {
  derivative_id: number;
  status: "queued" | "generating" | "awaiting_approval" | "failed" | "active";
  phase: string;
  progress: number;
  error_code?: string | null;
  has_frontal_preview: boolean;
  has_video_preview: boolean;
  updated_at: string;
}

export interface MemoryCandidate {
  content: string;
  confidence: number;
  source_session_id: number;
  source_turn_id: number;
  reason: string;
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const r = await fetch(`${GATEWAY_BASE}${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body !== undefined ? JSON.stringify(body) : undefined,
    // Health, consent and profile reads are live local state. Reusing a browser
    // HTTP cache entry can hide an owned-process failure and present stale UI.
    cache: "no-store",
  });
  if (!r.ok) {
    const err: ErrorEnvelope = await r.json().catch(() => ({
      code: "internal.error",
      message: `HTTP ${r.status}`,
      user_action: "retry_later",
      trace_id: "",
      retryable: true,
    }));
    throw new Error(`${err.code}: ${err.message} (trace=${err.trace_id})`);
  }
  return r.json();
}

async function upload<T>(path: string, file: File): Promise<T> {
  const body = new FormData();
  body.append("file", file, file.name);
  const response = await fetch(`${GATEWAY_BASE}${path}`, { method: "POST", body, cache: "no-store" });
  if (!response.ok) {
    const error: ErrorEnvelope = await response.json().catch(() => ({
      code: "internal.error", message: `HTTP ${response.status}`, user_action: "retry_later", trace_id: "", retryable: true,
    }));
    throw new Error(`${error.code}: ${error.message} (trace=${error.trace_id})`);
  }
  return response.json();
}

export const ConversationClient = {
  gatewayBase: () => GATEWAY_BASE,
  wsBase: () => WS_BASE,
  activeAssetUrl: (kind: "portrait" | "voice", revision = Date.now()) => `${GATEWAY_BASE}/api/v1/assets/${kind}/active/content?v=${revision}`,

  async getHealth(): Promise<HealthResponse> {
    return request("GET", "/api/v1/health");
  },
  async retryComponent(component: string) { return request("POST", `/api/v1/health/${encodeURIComponent(component)}/retry`); },
  async recoverAll() { return request("POST", "/api/v1/launcher/recover", { component: "all" }); },

  async getOnboardingDraft(): Promise<OnboardingDraft> {
    return request("GET", "/api/v1/onboarding/draft");
  },

  async putOnboardingDraft(patch: Partial<OnboardingDraft>): Promise<OnboardingDraft> {
    return request("PUT", "/api/v1/onboarding/draft", patch);
  },

  async getProfile(): Promise<Profile | null> {
    try {
      return await request<Profile>("GET", "/api/v1/profile");
    } catch (e: any) {
      if (String(e).includes("profile_not_found")) return null;
      throw e;
    }
  },

  async putProfile(payload: Partial<Profile> & { name: string; user_nickname: string; expected_version?: number }): Promise<Profile> {
    return request("PUT", "/api/v1/profile", payload);
  },

  async getConsents() { return request<{ items: Array<Record<string, unknown>> }>("GET", "/api/v1/consents"); },
  async grantConsent(scope: "portrait" | "voice" | "all") { return request("POST", "/api/v1/consents", { scope, policy_version: "v1" }); },
  async revokeConsent(scope: "portrait" | "voice" | "all") { return request("DELETE", `/api/v1/consents/${scope}`); },
  async getAssets(kind: "portrait" | "voice") { return request<{ kind: string; items: Array<Record<string, unknown>> }>("GET", `/api/v1/assets/${kind}`); },
  async uploadAsset(kind: "portrait" | "voice", file: File) {
    return upload<{ id: number; entity_id_hash: string; mime: string; size_bytes: number }>(`/api/v1/assets/${kind}/preview`, file);
  },
  async activateAsset(id: number) { return request("POST", `/api/v1/assets/${id}/activate`); },
  async createAvatarBuild(id: number) { return request<AvatarBuild>("POST", `/api/v1/assets/${id}/avatar-builds`); },
  async getAvatarBuild(id: number) { return request<AvatarBuild>("GET", `/api/v1/avatar-builds/${id}`); },
  async activateAvatarBuild(id: number) { return request<AvatarBuild>("POST", `/api/v1/avatar-builds/${id}/activate`); },
  async startIdleGeneration(id: number) { return request<IdleGenerationJob>("POST", `/api/v1/avatar-builds/${id}/idle-generation`); },
  async getIdleGeneration(id: number) { return request<IdleGenerationJob>("GET", `/api/v1/avatar-builds/${id}/idle-generation`); },
  idlePreviewUrl: (id: number, kind: "frontal" | "video", revision: string | number = Date.now()) =>
    `${GATEWAY_BASE}/api/v1/avatar-builds/${id}/idle-generation/${kind}?v=${encodeURIComponent(String(revision))}`,
  async approveIdleGeneration(id: number) { return request<AvatarBuild>("POST", `/api/v1/avatar-builds/${id}/idle-generation/approve`); },
  async getActiveAvatar() { return request<AvatarBuild>("GET", "/api/v1/avatar/active"); },
  async restoreAsset(kind: "portrait" | "voice") { return request<AvatarBuild | Record<string, unknown>>("POST", `/api/v1/assets/${kind}/restore`); },
  async getMemories(query = "") { return request<{ items: Array<any> }>("GET", `/api/v1/memories?q=${encodeURIComponent(query)}`); },
  async createMemory(content: string) { return request<Record<string, any>>("POST", "/api/v1/memories", { content }); },
  async editMemory(id: number, content: string) { return request("PATCH", `/api/v1/memories/${id}`, { content }); },
  async deleteMemory(id: number) { return request("DELETE", `/api/v1/memories/${id}`); },
  async purgeMemories() { return request("DELETE", "/api/v1/memories", { confirmation: "PURGE_ALL" }); },
  async getMemoryCandidates() { return request<{ items: MemoryCandidate[] }>("GET", "/api/v1/memory-candidates"); },
  async confirmMemoryCandidate(candidate: MemoryCandidate) {
    return request<Record<string, any>>("POST", "/api/v1/memory-candidates/confirm", {
      session_id: candidate.source_session_id,
      turn_id: candidate.source_turn_id,
      content: candidate.content,
    });
  },
  async rejectMemoryCandidate(candidate: MemoryCandidate) {
    return request("POST", "/api/v1/memory-candidates/reject", {
      session_id: candidate.source_session_id,
      turn_id: candidate.source_turn_id,
      content: candidate.content,
    });
  },
  async getRetention() { return request("GET", "/api/v1/retention/now"); },
  async previewVoice(text: string): Promise<Blob> {
    const response = await fetch(`${GATEWAY_BASE}/api/v1/tts/preview`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
      cache: "no-store",
    });
    if (!response.ok) throw new Error(`声音试听失败（HTTP ${response.status}）`);
    return response.blob();
  },
  async createSession(recordingPolicy: "standard" | "none" = "standard"): Promise<SessionCreated> {
    return request("POST", "/api/v1/sessions", { recording_policy: recordingPolicy });
  },
  async endSession(sessionRef: string) {
    return request("DELETE", `/api/v1/sessions/${encodeURIComponent(sessionRef)}`);
  },
  async enableNoRecord(sessionRef: string): Promise<SessionCreated> {
    return request("PATCH", `/api/v1/sessions/${encodeURIComponent(sessionRef)}/no_record`);
  },

  /**
   * M3-06：打开一个会话的 WebSocket 连接。返回带消息订阅的对象。
   * 后端推送的事件顺序：state.changed → transcript.partial → reply.text.delta → reply.audio.chunk → ...
   * 迟到事件（event_seq ≤ seen）由前端 reducer 丢弃。
   */
  openSessionWebSocket(sessionRef: string | number, onEvent: (env: WsEnvelope) => void): WebSocket {
    const url = `${WS_BASE}/ws/v1/sessions/${encodeURIComponent(String(sessionRef))}`;
    const ws = new WebSocket(url);
    ws.onmessage = (e) => {
      try {
        const env = JSON.parse(e.data) as WsEnvelope;
        void MediaSession.handleServerEvent(env, ws).catch((err) => {
          console.error("[Audio] playback error", err);
        });
        if (env.type === "barge_in.detected" || env.type === "turn.cancelled") {
          const generation = Number(env.payload.cancelled_generation);
          AvatarSession.cancelGeneration(Number.isFinite(generation) ? generation : undefined, env.session_id);
        }
        if (env.type === "reply.audio.chunk") {
          const generation = Number(env.payload.generation);
          if (Number.isFinite(generation)) AvatarSession.setGeneration(generation, env.session_id);
        }
        onEvent(env);
      } catch (err) {
        console.error("[WS] parse error", err);
      }
    };
    ws.onerror = (e) => console.error("[WS] error", e);
    return ws;
  },

  /**
   * M3-06：发送音频二进制帧（§7 WS 二进制帧格式）。
   * turn_id (uint32 LE, 4B) + chunk_seq (uint16 LE, 2B) + PCM Int16 LE (640B)
   */
  packAudioChunk(turnId: number, chunkSeq: number, pcm: ArrayBuffer): ArrayBuffer {
    const out = new ArrayBuffer(6 + pcm.byteLength);
    const view = new DataView(out);
    view.setUint32(0, turnId, true);    // little-endian
    view.setUint16(4, chunkSeq, true);
    new Uint8Array(out, 6).set(new Uint8Array(pcm));
    return out;
  },
};
