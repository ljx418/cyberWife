// Browser PCM playback and first-non-silent render confirmation (B2.5-O1).

type PlaybackEnvelope = {
  type: string;
  session_id: string;
  turn_id: number | null;
  payload: Record<string, unknown>;
};

type Marker = {
  key: string;
  sessionId: string;
  turnId: number;
  traceId: string;
  generation: number;
  asrFinalWallMs: number;
  serverElapsedMs: number;
  browserReceivedPerfMs: number;
};

const WORKLET_SOURCE = `
class CyberWifeFirstSoundMeter extends AudioWorkletProcessor {
  constructor() {
    super();
    this.armed = false;
    this.key = '';
    this.port.onmessage = (event) => {
      if (event.data && event.data.type === 'arm') {
        this.armed = true;
        this.key = event.data.key;
      }
    };
  }
  process(inputs, outputs) {
    const input = inputs[0] || [];
    const output = outputs[0] || [];
    for (let channel = 0; channel < output.length; channel += 1) {
      const source = input[channel] || input[0];
      if (source) output[channel].set(source);
    }
    if (this.armed && input.some(channel => channel.some(sample => Math.abs(sample) >= 0.002))) {
      this.armed = false;
      this.port.postMessage({ type: 'first-non-silent', key: this.key });
    }
    return true;
  }
}
registerProcessor('cyberwife-first-sound-meter', CyberWifeFirstSoundMeter);
`;

// Wav2Lip consumes two 20ms PCM chunks per video frame and needs right-side
// context before its first generated frame.  On the target RTX machine a
// batch of four reaches the browser in 218-370ms (warm/cold). Holding only
// the first audio source of each generation aligns audible onset with that
// real mouth frame;
// subsequent chunks remain gapless on nextStartAt.  This stays well inside
// the PRD's 7s first-sound budget and is cancelled by the existing generation
// fence during barge-in.
export const AVATAR_AUDIO_PREROLL_SECONDS = 0.295;

let context: AudioContext | null = null;
let meter: AudioWorkletNode | null = null;
let outputGain: GainNode | null = null;
let outputCompressor: DynamicsCompressorNode | null = null;
let outputPromise: Promise<AudioContext> | null = null;
let nextStartAt = 0;
let lastFirstChunkLeadSeconds = 0;
let armedKey = "";
let activeSocket: WebSocket | null = null;
const markers = new Map<string, Marker>();
const confirmed = new Set<string>();
const activeSources = new Map<string, Set<AudioBufferSourceNode>>();
const cancelledGenerations = new Set<string>();
const latestGenerations = new Map<string, number>();
const playbackComplete = new Set<string>();
const playbackEndedSent = new Set<string>();
const replaySources = new Set<AudioBufferSourceNode>();
let replayKey = "";
let replayChunks: Array<{ pcm: Int16Array; sampleRate: number }> = [];
let replayBytes = 0;
let replayOverflowed = false;
let outputVolume = 1;
let outputMuted = false;
let compressionEnabled = true;
const MAX_REPLAY_BYTES = 16 * 1024 * 1024;

export function appendBoundedReplayChunk(
  chunks: Array<{ pcm: Int16Array; sampleRate: number }>,
  currentBytes: number,
  pcm: Int16Array,
  sampleRate: number,
  maxBytes = MAX_REPLAY_BYTES,
): { chunks: Array<{ pcm: Int16Array; sampleRate: number }>; bytes: number; overflowed: boolean } {
  if (currentBytes + pcm.byteLength > maxBytes) {
    return { chunks: [], bytes: 0, overflowed: true };
  }
  return {
    chunks: [...chunks, { pcm: pcm.slice(), sampleRate }],
    bytes: currentBytes + pcm.byteLength,
    overflowed: false,
  };
}

function generationKey(sessionId: string, generation: number): string {
  return `${sessionId}:${generation}`;
}

function confirmRendered(key: string): void {
  const marker = markers.get(key);
  if (!marker || confirmed.has(marker.key)) return;
  confirmed.add(marker.key);
  const browserWallMs = Date.now();
  const ws = activeSocket;
  if (ws?.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({
      type: "audio.playback.started",
      session_id: marker.sessionId,
      turn_id: marker.turnId,
      trace_id: marker.traceId,
      generation: marker.generation,
      asr_to_playback_ms: marker.serverElapsedMs + Math.max(
        0,
        performance.now() - marker.browserReceivedPerfMs,
      ),
      browser_first_non_silent_wall_ms: browserWallMs,
    }));
  }
}

function confirmEnded(key: string): void {
  if (!playbackComplete.has(key) || playbackEndedSent.has(key)) return;
  const marker = markers.get(key);
  if (!marker || cancelledGenerations.has(generationKey(marker.sessionId, marker.generation))) return;
  const sources = activeSources.get(generationKey(marker.sessionId, marker.generation));
  if (sources && sources.size > 0) return;
  const ws = activeSocket;
  if (ws?.readyState !== WebSocket.OPEN) return;
  playbackEndedSent.add(key);
  ws.send(JSON.stringify({
    type: "audio.playback.ended",
    session_id: marker.sessionId,
    turn_id: marker.turnId,
    trace_id: marker.traceId,
    generation: marker.generation,
    browser_playback_ended_wall_ms: Date.now(),
  }));
}

async function ensureOutput(): Promise<AudioContext> {
  if (outputPromise) return outputPromise;
  if (context && context.state !== "closed") {
    if (context.state === "suspended") await context.resume();
    return context;
  }
  outputPromise = (async () => {
    const created = new AudioContext({ latencyHint: "interactive", sampleRate: 16000 });
    context = created;
    const moduleUrl = URL.createObjectURL(new Blob([WORKLET_SOURCE], { type: "text/javascript" }));
    try {
      await created.audioWorklet.addModule(moduleUrl);
    } finally {
      URL.revokeObjectURL(moduleUrl);
    }
    meter = new AudioWorkletNode(created, "cyberwife-first-sound-meter", {
      numberOfInputs: 1,
      numberOfOutputs: 1,
      outputChannelCount: [1],
    });
    outputGain = created.createGain();
    outputCompressor = created.createDynamicsCompressor();
    outputCompressor.threshold.value = -18;
    outputCompressor.knee.value = 18;
    outputCompressor.ratio.value = compressionEnabled ? 3 : 1;
    outputCompressor.attack.value = 0.003;
    outputCompressor.release.value = 0.18;
    outputGain.gain.value = outputMuted ? 0 : outputVolume;
    outputGain.connect(outputCompressor).connect(meter).connect(created.destination);
    meter.port.onmessage = (event: MessageEvent<{ type: string; key: string }>) => {
      if (event.data?.type === "first-non-silent") confirmRendered(event.data.key);
    };
    nextStartAt = created.currentTime;
    return created;
  })();
  try {
    return await outputPromise;
  } catch (error) {
    outputPromise = null;
    context = null;
    meter = null;
    throw error;
  }
}

function decodePcm16(base64: string): Int16Array {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return new Int16Array(bytes.buffer);
}

export const MediaSession = {
  async start(): Promise<void> {
    await ensureOutput();
  },

  async handleServerEvent(env: PlaybackEnvelope, ws: WebSocket): Promise<boolean> {
    if (env.type === "barge_in.detected") {
      this.cancelGeneration(undefined, env.session_id);
      this.clearReplay();
      return true;
    }
    if (env.type === "turn.cancelled") {
      const cancelled = Number(env.payload.cancelled_generation);
      this.cancelGeneration(Number.isFinite(cancelled) ? cancelled : undefined, env.session_id);
      this.clearReplay();
      return true;
    }
    if (env.type === "reply.audio.complete" && env.turn_id !== null) {
      const traceId = env.payload.trace_id;
      const generation = env.payload.generation;
      if (typeof traceId !== "string" || typeof generation !== "number") return false;
      const key = `${env.session_id}:${env.turn_id}:${generation}:${traceId}`;
      playbackComplete.add(key);
      confirmEnded(key);
      return true;
    }
    if (env.type !== "reply.audio.chunk" || env.turn_id === null) return false;
    const payload = env.payload;
    const base64 = payload.audio_chunk_b64;
    const traceId = payload.trace_id;
    const generation = payload.generation;
    const asrFinalWallMs = payload.asr_final_wall_ms;
    const serverElapsedMs = payload.server_elapsed_ms;
    if (
      typeof base64 !== "string" || typeof traceId !== "string" ||
      typeof generation !== "number" || typeof asrFinalWallMs !== "number" ||
      typeof serverElapsedMs !== "number"
    ) return false;
    const generationId = generationKey(env.session_id, generation);
    const latestGeneration = latestGenerations.get(env.session_id) ?? 0;
    if (cancelledGenerations.has(generationId) || generation < latestGeneration) return false;
    latestGenerations.set(env.session_id, Math.max(latestGeneration, generation));

    const audioContext = await ensureOutput();
    if (!meter) return false;
    activeSocket = ws;
    const key = `${env.session_id}:${env.turn_id}:${generation}:${traceId}`;
    const firstChunkForTurn = armedKey !== key;
    if (firstChunkForTurn) {
      if (replayKey !== key) {
        this.clearReplay();
        replayKey = key;
      }
      armedKey = key;
      markers.set(key, {
        key,
        sessionId: env.session_id,
        turnId: env.turn_id,
        traceId,
        generation,
        asrFinalWallMs,
        serverElapsedMs,
        browserReceivedPerfMs: performance.now(),
      });
      meter.port.postMessage({ type: "arm", key });
    }

    const pcm = decodePcm16(base64);
    const buffer = audioContext.createBuffer(1, pcm.length, Number(payload.sample_rate) || 16000);
    const channel = buffer.getChannelData(0);
    for (let i = 0; i < pcm.length; i += 1) channel[i] = pcm[i] / 32768;
    const source = audioContext.createBufferSource();
    source.buffer = buffer;
    if (!outputGain) return false;
    source.connect(outputGain);
    if (!replayOverflowed) {
      const buffered = appendBoundedReplayChunk(
        replayChunks,
        replayBytes,
        pcm,
        Number(payload.sample_rate) || 16000,
      );
      replayChunks = buffered.chunks;
      replayBytes = buffered.bytes;
      replayOverflowed = buffered.overflowed;
    }
    const hasNonSilent = pcm.some((sample) => Math.abs(sample) >= 66);
    const sources = activeSources.get(generationId) ?? new Set<AudioBufferSourceNode>();
    sources.add(source);
    activeSources.set(generationId, sources);
    source.onended = () => {
      sources.delete(source);
      if (sources.size === 0) activeSources.delete(generationId);
      if (hasNonSilent && !cancelledGenerations.has(generationId)) confirmRendered(key);
      confirmEnded(key);
    };
    const minimumLead = firstChunkForTurn ? AVATAR_AUDIO_PREROLL_SECONDS : 0.005;
    const scheduledAt = Math.max(audioContext.currentTime + minimumLead, nextStartAt);
    if (firstChunkForTurn) {
      lastFirstChunkLeadSeconds = Math.max(0, scheduledAt - audioContext.currentTime);
    }
    source.start(scheduledAt);
    nextStartAt = scheduledAt + buffer.duration;
    return true;
  },

  cancelGeneration(generation?: number, sessionId?: string): number {
    this.clearReplay();
    const targets = [...activeSources.keys()].filter((key) => {
      const separator = key.lastIndexOf(":");
      const keySession = key.slice(0, separator);
      const keyGeneration = Number(key.slice(separator + 1));
      return (sessionId === undefined || keySession === sessionId) &&
        (generation === undefined || keyGeneration === generation);
    });
    let stopped = 0;
    for (const target of targets) {
      cancelledGenerations.add(target);
      const sources = activeSources.get(target);
      if (!sources) continue;
      for (const source of sources) {
        try {
          source.stop();
          stopped += 1;
        } catch {
          // Already-ended WebAudio sources are harmless and still removed.
        }
        source.disconnect();
      }
      activeSources.delete(target);
      for (const [key, marker] of markers) {
        if (generationKey(marker.sessionId, marker.generation) === target) markers.delete(key);
        playbackComplete.delete(key);
        playbackEndedSent.delete(key);
      }
    }
    if (context) nextStartAt = context.currentTime;
    armedKey = "";
    return stopped;
  },

  snapshot() {
    return {
      contextState: context?.state ?? "closed",
      activeSources: [...activeSources.values()].reduce((sum, sources) => sum + sources.size, 0),
      latestGeneration: Math.max(0, ...latestGenerations.values()),
      cancelledGenerationKeys: [...cancelledGenerations],
      latestGenerationBySession: Object.fromEntries(latestGenerations),
      lastFirstChunkLeadSeconds,
      outputVolume,
      outputMuted,
      compressionEnabled,
      replayBytes,
      replayAvailable: replayChunks.length > 0 && !replayOverflowed,
      replayOverflowed,
      replaySources: replaySources.size,
      outputDeviceSelectionSupported: Boolean(context && "setSinkId" in context),
    };
  },

  setVolume(value: number): void {
    outputVolume = Math.max(0, Math.min(1, Number.isFinite(value) ? value : 1));
    if (outputGain) outputGain.gain.value = outputMuted ? 0 : outputVolume;
  },

  setMuted(muted: boolean): void {
    outputMuted = Boolean(muted);
    if (outputGain) outputGain.gain.value = outputMuted ? 0 : outputVolume;
  },

  setCompression(enabled: boolean): void {
    compressionEnabled = Boolean(enabled);
    if (outputCompressor) outputCompressor.ratio.value = compressionEnabled ? 3 : 1;
  },

  async setOutputDevice(deviceId: string): Promise<"selected" | "unsupported"> {
    const audioContext = await ensureOutput();
    const selectable = audioContext as AudioContext & { setSinkId?: (sinkId: string) => Promise<void> };
    if (typeof selectable.setSinkId !== "function") return "unsupported";
    await selectable.setSinkId(deviceId);
    return "selected";
  },

  async replayCurrent(): Promise<boolean> {
    if (!replayChunks.length || replayOverflowed) return false;
    const audioContext = await ensureOutput();
    if (!outputGain) return false;
    for (const source of replaySources) {
      try { source.stop(); } catch { /* already ended */ }
      source.disconnect();
    }
    replaySources.clear();
    let cursor = audioContext.currentTime + 0.01;
    for (const item of replayChunks) {
      const buffer = audioContext.createBuffer(1, item.pcm.length, item.sampleRate);
      const channel = buffer.getChannelData(0);
      for (let index = 0; index < item.pcm.length; index += 1) channel[index] = item.pcm[index] / 32768;
      const source = audioContext.createBufferSource();
      source.buffer = buffer;
      source.connect(outputGain);
      replaySources.add(source);
      source.onended = () => replaySources.delete(source);
      source.start(cursor);
      cursor += buffer.duration;
    }
    return true;
  },

  clearReplay(): void {
    for (const source of replaySources) {
      try { source.stop(); } catch { /* already ended */ }
      source.disconnect();
    }
    replaySources.clear();
    replayKey = "";
    replayChunks = [];
    replayBytes = 0;
    replayOverflowed = false;
  },

  async stop(): Promise<void> {
    const current = context;
    context = null;
    meter = null;
    outputGain = null;
    outputCompressor = null;
    outputPromise = null;
    nextStartAt = 0;
    lastFirstChunkLeadSeconds = 0;
    armedKey = "";
    activeSocket = null;
    markers.clear();
    confirmed.clear();
    playbackComplete.clear();
    playbackEndedSent.clear();
    activeSources.clear();
    cancelledGenerations.clear();
    latestGenerations.clear();
    this.clearReplay();
    if (current && current.state !== "closed") await current.close();
  },
};
