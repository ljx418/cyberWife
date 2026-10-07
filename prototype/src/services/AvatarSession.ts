// Loopback-only Avatar H.264/WebCodecs session with bounded, same-page recovery.

export type AvatarConnectionState = "stopped" | "connecting" | "ready" | "static_fallback";

export type AvatarSnapshot = {
  avatarId: string;
  state: AvatarConnectionState;
  connectionGeneration: number;
  reconnectAttempts: number;
  sessionId: string | null;
  decodedFrames: number;
  clientFps: number;
  mediaFps: number;
  decoderBacklog: number;
  mediaGeneration: number;
  conversationSessionId: string | null;
  staleFramesDropped: number;
  lastMediaActivityMs: number;
  mediaActivityAgeMs: number;
  fallbackKind: "none" | "soft" | "hard";
  controlStatus: "unknown" | "ready" | "unavailable";
  changedAtMs: number;
};

type Options = {
  baseUrl?: string;
  controlUrl?: string;
  pollIntervalMs?: number;
  reconnectMaxMs?: number;
  mediaStaleMs?: number;
  controlTimeoutMs?: number;
};

type Listener = (snapshot: AvatarSnapshot) => void;

type VideoConfigMessage = {
  type: "video.config";
  version: 1 | 2;
  session_id: string;
  codec: string;
  format: "annexb";
  fps: number;
  queue_limit: number;
  audio: "gateway-pcm";
};

type AvatarHeartbeatMessage = {
  type: "avatar.heartbeat";
  version: 1;
  session_id: string;
  monotonic_ms: number;
};

function loopbackBase(raw: string): URL {
  const parsed = new URL(raw);
  if (parsed.protocol !== "http:" || !["127.0.0.1", "localhost", "[::1]"].includes(parsed.hostname)) {
    throw new Error("Avatar endpoint must be loopback HTTP");
  }
  return parsed;
}

export class AvatarSessionController {
  private readonly baseUrl: URL;
  private readonly controlUrl: URL;
  private readonly pollIntervalMs: number;
  private readonly reconnectMaxMs: number;
  private readonly mediaStaleMs: number;
  private readonly controlTimeoutMs: number;
  private socket: WebSocket | null = null;
  private decoder: VideoDecoder | null = null;
  private decoderConfig: VideoDecoderConfig | null = null;
  private mediaGeneration = 0;
  private conversationSessionId: string | null = null;
  private canvas: HTMLCanvasElement | null = null;
  private canvasClearTimer: number | null = null;
  private avatarId = "wav2lip256_avatar1";
  private timer: number | null = null;
  private active = false;
  private connecting: Promise<void> | null = null;
  private frameTimes: number[] = [];
  private mediaTimes: number[] = [];
  private listeners = new Set<Listener>();
  private current: AvatarSnapshot = {
    avatarId: this.avatarId,
    state: "stopped",
    connectionGeneration: 0,
    reconnectAttempts: 0,
    sessionId: null,
    decodedFrames: 0,
    clientFps: 0,
    mediaFps: 0,
    decoderBacklog: 0,
    mediaGeneration: 0,
    conversationSessionId: null,
    staleFramesDropped: 0,
    lastMediaActivityMs: 0,
    mediaActivityAgeMs: 0,
    fallbackKind: "none",
    controlStatus: "unknown",
    changedAtMs: Date.now(),
  };

  constructor(options: Options = {}) {
    this.baseUrl = loopbackBase(options.baseUrl ?? "http://127.0.0.1:8010");
    const defaultControl = new URL(this.baseUrl);
    defaultControl.port = "8011";
    this.controlUrl = loopbackBase(options.controlUrl ?? defaultControl.toString());
    this.pollIntervalMs = Math.max(25, options.pollIntervalMs ?? 500);
    this.reconnectMaxMs = Math.max(this.pollIntervalMs, options.reconnectMaxMs ?? 10000);
    this.mediaStaleMs = Math.max(500, options.mediaStaleMs ?? 1200);
    this.controlTimeoutMs = Math.max(100, options.controlTimeoutMs ?? 500);
  }

  snapshot(): AvatarSnapshot {
    const mediaActivityAgeMs = this.current.lastMediaActivityMs > 0
      ? Math.max(0, Date.now() - this.current.lastMediaActivityMs)
      : 0;
    return { ...this.current, mediaActivityAgeMs };
  }

  subscribe(listener: Listener): () => void {
    this.listeners.add(listener);
    listener(this.snapshot());
    return () => this.listeners.delete(listener);
  }

  async start(canvas?: HTMLCanvasElement, avatarId?: string): Promise<void> {
    this.cancelCanvasClear();
    const requestedAvatarId = avatarId && /^[A-Za-z0-9_-]{1,80}$/.test(avatarId)
      ? avatarId
      : this.avatarId;
    const avatarChanged = requestedAvatarId !== this.avatarId;
    const requestedCanvas = canvas ?? this.canvas ?? undefined;
    if (avatarChanged && this.active) {
      await this.stop();
    }
    if (requestedCanvas) this.canvas = requestedCanvas;
    this.avatarId = requestedAvatarId;
    this.current = { ...this.current, avatarId: this.avatarId };
    if (!this.canvas) {
      this.canvas = document.createElement("canvas");
      this.canvas.hidden = true;
    }
    this.setCanvasLive(false);
    if (this.active && this.current.state === "ready") return;
    this.active = true;
    this.setState("connecting");
    try {
      await this.connect();
    } catch {
      this.degrade();
    }
    this.schedule(this.current.state === "ready" ? this.pollIntervalMs : this.retryDelay());
  }

  async stop(): Promise<void> {
    this.active = false;
    if (this.timer !== null) window.clearTimeout(this.timer);
    this.timer = null;
    this.closeTransport();
    this.setCanvasLive(false);
    this.scheduleCanvasClear();
    this.canvas = null;
    this.decoderConfig = null;
    this.mediaGeneration = 0;
    this.conversationSessionId = null;
    this.current = {
      ...this.current,
      avatarId: this.avatarId,
      state: "stopped",
      reconnectAttempts: 0,
      sessionId: null,
      decodedFrames: 0,
      clientFps: 0,
      mediaFps: 0,
      decoderBacklog: 0,
      mediaGeneration: 0,
      conversationSessionId: null,
      staleFramesDropped: 0,
      lastMediaActivityMs: 0,
      mediaActivityAgeMs: 0,
      fallbackKind: "none",
      controlStatus: "unknown",
      changedAtMs: Date.now(),
    };
    this.emit();
  }

  private setState(state: AvatarConnectionState, patch: Partial<AvatarSnapshot> = {}): void {
    this.current = { ...this.current, ...patch, state, changedAtMs: Date.now() };
    this.emit();
  }

  private emit(): void {
    const value = this.snapshot();
    for (const listener of this.listeners) listener(value);
  }

  private async probe(): Promise<void> {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), this.controlTimeoutMs);
    try {
      const response = await fetch(new URL("/healthz", this.controlUrl), {
        cache: "no-store",
        signal: controller.signal,
      });
      if (!response.ok) throw new Error("Avatar control probe failed");
      const payload = await response.json() as { status?: string; protocol?: string };
      if (payload.status !== "ready" || payload.protocol !== "avatar-control-v1") {
        throw new Error("Avatar control endpoint is not ready");
      }
      this.current = { ...this.current, controlStatus: "ready" };
    } catch (error) {
      this.current = { ...this.current, controlStatus: "unavailable" };
      throw error;
    } finally {
      window.clearTimeout(timeout);
    }
  }

  private async connect(): Promise<void> {
    if (this.connecting) return this.connecting;
    this.connecting = (async () => {
      await this.probe();
      if (!this.active) return;
      if (typeof VideoDecoder === "undefined") throw new Error("WebCodecs VideoDecoder unavailable");
      const wsUrl = new URL("/ws/v1/avatar", this.baseUrl);
      wsUrl.protocol = "ws:";
      wsUrl.searchParams.set("avatar_id", this.avatarId);
      const socket = new WebSocket(wsUrl);
      socket.binaryType = "arraybuffer";
      this.frameTimes = [];
      this.mediaTimes = [];
      let config: VideoConfigMessage | null = null;
      let sessionId: string | null = null;
      let acceptedFirstFrame = false;
      let firstFrameResolve: (() => void) | null = null;
      let firstFrameReject: ((error: Error) => void) | null = null;
      const firstFrame = new Promise<void>((resolve, reject) => {
        firstFrameResolve = resolve;
        firstFrameReject = reject;
      });
      const decoder = new VideoDecoder({
        output: (frame) => {
          try {
            if (!this.canvas) return;
            if (this.canvas.width !== frame.displayWidth) this.canvas.width = frame.displayWidth;
            if (this.canvas.height !== frame.displayHeight) this.canvas.height = frame.displayHeight;
            this.canvas.getContext("2d", { alpha: true })?.drawImage(frame, 0, 0);
            this.setCanvasLive(true);
            const now = performance.now();
            this.frameTimes.push(now);
            if (this.frameTimes.length > 128) this.frameTimes.shift();
            this.mediaTimes.push(frame.timestamp);
            if (this.mediaTimes.length > 128) this.mediaTimes.shift();
            const elapsed = this.frameTimes.length > 1 ? now - this.frameTimes[0] : 0;
            const clientFps = elapsed > 0 ? (this.frameTimes.length - 1) * 1000 / elapsed : 0;
            const mediaElapsed = this.mediaTimes.length > 1 ? frame.timestamp - this.mediaTimes[0] : 0;
            const mediaFps = mediaElapsed > 0 ? (this.mediaTimes.length - 1) * 1_000_000 / mediaElapsed : 0;
            this.current = {
              ...this.current,
              decodedFrames: this.current.decodedFrames + 1,
              clientFps: Number(clientFps.toFixed(3)),
              mediaFps: Number(mediaFps.toFixed(3)),
              lastMediaActivityMs: Date.now(),
              fallbackKind: "none",
              controlStatus: "ready",
            };
            if (this.current.state === "static_fallback" && this.socket === socket) {
              this.setState("ready");
            }
            firstFrameResolve?.();
            firstFrameResolve = null;
          } finally {
            frame.close();
          }
        },
        error: (error) => firstFrameReject?.(new Error(`Avatar decode failed: ${error.message}`)),
      });
      socket.onmessage = async (event) => {
        try {
          if (typeof event.data === "string") {
            const candidate = JSON.parse(event.data) as VideoConfigMessage | AvatarHeartbeatMessage;
            if (candidate.type === "avatar.heartbeat") {
              if (candidate.version !== 1 || (sessionId && candidate.session_id !== sessionId)) {
                throw new Error("invalid Avatar heartbeat");
              }
              this.current = { ...this.current, lastMediaActivityMs: Date.now() };
              return;
            }
            if (candidate.type !== "video.config" || ![1, 2].includes(candidate.version) || candidate.format !== "annexb") {
              throw new Error("unsupported Avatar video protocol");
            }
            // Headless Chrome and some Windows GPU/driver combinations expose
            // H.264 WebCodecs but reject an explicit hardware-only preference.
            // Keep hardware as the first choice, then let Chrome select its
            // supported decoder instead of degrading a valid stream.
            let supported = await VideoDecoder.isConfigSupported({
              codec: candidate.codec,
              hardwareAcceleration: "prefer-hardware",
              optimizeForLatency: true,
            });
            if (!supported.supported) {
              supported = await VideoDecoder.isConfigSupported({
                codec: candidate.codec,
                hardwareAcceleration: "no-preference",
                optimizeForLatency: true,
              });
            }
            if (!supported.supported) throw new Error(`unsupported Avatar codec: ${candidate.codec}`);
            decoder.configure(supported.config!);
            this.decoderConfig = supported.config!;
            config = candidate;
            sessionId = candidate.session_id;
            return;
          }
          if (!config || decoder.state !== "configured" || !(event.data instanceof ArrayBuffer)) return;
          const bytes = new Uint8Array(event.data);
          const headerSize = config.version === 2 ? 18 : 14;
          if (bytes.byteLength <= headerSize || bytes[0] !== config.version) throw new Error("invalid Avatar frame");
          const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
          this.current = { ...this.current, lastMediaActivityMs: Date.now() };
          const generation = config.version === 2 ? view.getUint32(14, true) : this.mediaGeneration;
          // A freshly created Avatar transport starts with a generation-0 idle
          // keyframe even when the conversation survived an Avatar process
          // restart at a later generation.  The new WS session cannot contain
          // frames from the dead process, so permit its first decodable frame
          // to establish the canvas.  Once assigned, enforce the conversation
          // generation fence exactly as before.
          if (generation !== this.mediaGeneration && acceptedFirstFrame) {
            this.current = {
              ...this.current,
              staleFramesDropped: this.current.staleFramesDropped + 1,
            };
            return;
          }
          acceptedFirstFrame = true;
          decoder.decode(new EncodedVideoChunk({
            type: (bytes[1] & 1) === 1 ? "key" : "delta",
            timestamp: view.getUint32(6, true) * 1000,
            data: bytes.subarray(headerSize),
          }));
          this.current = { ...this.current, decoderBacklog: decoder.decodeQueueSize };
        } catch (error) {
          firstFrameReject?.(error instanceof Error ? error : new Error(String(error)));
        }
      };
      socket.onerror = () => firstFrameReject?.(new Error("Avatar WebSocket failed"));
      socket.onclose = () => {
        firstFrameReject?.(new Error("Avatar WebSocket closed before first frame"));
        if (this.active && this.socket === socket) this.hardDegrade();
      };
      try {
        await Promise.race([
          firstFrame,
          new Promise<never>((_, reject) => window.setTimeout(() => reject(new Error("Avatar first frame timeout")), 10000)),
        ]);
        if (!this.active || !config || !sessionId) {
          socket.close();
          decoder.close();
          return;
        }
        this.closeTransport();
        this.socket = socket;
        this.decoder = decoder;
        this.setState("ready", {
          connectionGeneration: this.current.connectionGeneration + 1,
          reconnectAttempts: 0,
          sessionId,
          lastMediaActivityMs: Date.now(),
          fallbackKind: "none",
          controlStatus: "ready",
        });
      } catch (error) {
        socket.onclose = null;
        socket.close();
        decoder.close();
        throw error;
      }
    })();
    try {
      await this.connecting;
    } finally {
      this.connecting = null;
    }
  }

  private clearCanvas(canvas: HTMLCanvasElement | null = this.canvas): void {
    if (canvas) canvas.getContext("2d")?.clearRect(0, 0, canvas.width, canvas.height);
  }

  private cancelCanvasClear(): void {
    if (this.canvasClearTimer !== null) window.clearTimeout(this.canvasClearTimer);
    this.canvasClearTimer = null;
  }

  private scheduleCanvasClear(): void {
    const canvas = this.canvas;
    this.cancelCanvasClear();
    if (!canvas) return;
    this.canvasClearTimer = window.setTimeout(() => {
      this.clearCanvas(canvas);
      canvas.hidden = true;
      this.canvasClearTimer = null;
    }, 260);
  }

  private setCanvasLive(live: boolean): void {
    if (!this.canvas) return;
    if (live) this.cancelCanvasClear();
    const wasLive = this.canvas.dataset.avatarLayer === "live" && !this.canvas.hidden;
    this.canvas.hidden = live ? false : !wasLive;
    this.canvas.dataset.avatarLayer = live ? "live" : "static";
    this.canvas.style.opacity = live ? "1" : "0";
  }

  private softDegrade(): void {
    if (!this.active) return;
    this.setCanvasLive(false);
    this.scheduleCanvasClear();
    this.setState("static_fallback", { fallbackKind: "soft", controlStatus: "ready" });
    this.schedule(this.pollIntervalMs);
  }

  private hardDegrade(): void {
    if (!this.active) return;
    this.closeTransport();
    this.setCanvasLive(false);
    this.scheduleCanvasClear();
    this.setState("static_fallback", {
      reconnectAttempts: this.current.reconnectAttempts + 1,
      sessionId: null,
      fallbackKind: "hard",
      controlStatus: "unavailable",
    });
    this.schedule(this.retryDelay());
  }

  private degrade(): void {
    this.hardDegrade();
  }

  private retryDelay(): number {
    const exponent = Math.min(4, Math.max(0, this.current.reconnectAttempts - 1));
    return Math.min(this.reconnectMaxMs, this.pollIntervalMs * 2 ** exponent);
  }

  private schedule(delayMs: number): void {
    if (!this.active) return;
    if (this.timer !== null) window.clearTimeout(this.timer);
    this.timer = window.setTimeout(async () => {
      this.timer = null;
      if (!this.active) return;
      try {
        if (this.socket && this.current.state === "ready") {
          const ageMs = Date.now() - this.current.lastMediaActivityMs;
          if (ageMs >= this.mediaStaleMs) {
            try {
              await this.probe();
              this.softDegrade();
              return;
            } catch {
              this.hardDegrade();
              return;
            }
          }
        } else if (this.socket && this.current.state === "static_fallback") {
          try {
            await this.probe();
          } catch {
            this.hardDegrade();
            return;
          }
        } else {
          this.setState("connecting");
          await this.connect();
        }
      } catch {
        this.degrade();
        return;
      }
      this.schedule(this.pollIntervalMs);
    }, delayMs);
  }

  private closeTransport(): void {
    const socket = this.socket;
    this.socket = null;
    if (socket) {
      socket.onclose = null;
      socket.onmessage = null;
      socket.close();
    }
    const decoder = this.decoder;
    this.decoder = null;
    if (decoder && decoder.state !== "closed") decoder.close();
  }



  cancelGeneration(generation?: number, sessionId?: string): boolean {
    if (sessionId && this.conversationSessionId && sessionId !== this.conversationSessionId) return false;
    if (generation !== undefined && generation < this.mediaGeneration) return false;
    if (generation !== undefined) this.mediaGeneration = generation + 1;
    this.current = { ...this.current, mediaGeneration: this.mediaGeneration };
    const decoder = this.decoder;
    if (decoder && decoder.state === "configured" && this.decoderConfig) {
      decoder.reset();
      decoder.configure(this.decoderConfig);
      this.current = { ...this.current, decoderBacklog: 0 };
    }
    this.setCanvasLive(false);
    this.scheduleCanvasClear();
    this.emit();
    return true;
  }

  setGeneration(generation: number, sessionId?: string): void {
    let timelineChanged = false;
    if (sessionId && sessionId !== this.conversationSessionId) {
      this.conversationSessionId = sessionId;
      this.mediaGeneration = 0;
      timelineChanged = true;
    }
    if (Number.isFinite(generation) && generation >= this.mediaGeneration) {
      if (generation > this.mediaGeneration) timelineChanged = true;
      this.mediaGeneration = generation;
    }
    if (timelineChanged) {
      // Client FPS is meaningful only within one media generation.  A process
      // recovery may contribute one generation-0 idle frame before the next
      // answer; carrying that timestamp into the answer would manufacture a
      // low FPS result despite a steady 25fps stream.
      this.frameTimes = [];
      this.mediaTimes = [];
    }
    this.current = {
      ...this.current,
      mediaGeneration: this.mediaGeneration,
      conversationSessionId: this.conversationSessionId,
      ...(timelineChanged ? { clientFps: 0, mediaFps: 0 } : {}),
    };
  }
}

export const AvatarSession = new AvatarSessionController();
