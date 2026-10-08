// Continuous browser microphone capture for the Gateway's 16 kHz/20 ms PCM contract.

export type InputAudioSnapshot = {
  state: "stopped" | "starting" | "listening" | "capturing" | "error";
  emittedFrames: number;
  activeTracks: number;
  contextState: AudioContextState | "closed";
  lastError: string | null;
  mode: InputMode;
  selectedDeviceId: string | null;
  pushToTalkActive: boolean;
  calibration: InputCalibration | null;
  boundary: {
    capturing: boolean;
    voicedFrames: number;
    silentFrames: number;
    hangoverMs: number;
  };
};

export type InputMode = "automatic" | "manual" | "push_to_talk";

export type InputDevice = { deviceId: string; label: string; isDefault: boolean };

export type InputCalibration = {
  algorithmVersion: 1;
  sampleCount: number;
  noiseP50: number;
  noiseP95: number;
  voiceThreshold: number;
  bargeInThreshold: number;
  calibratedAt: string;
};

export type InputAudioOptions = {
  deviceId?: string | null;
  mode?: InputMode;
  manualThreshold?: number;
  calibration?: InputCalibration | null;
};

export type InputAudioCallbacks = {
  boundaryMode?: () => "normal" | "barge_in";
  onUtteranceStart: (preroll: ArrayBuffer[]) => boolean;
  onFrame: (pcm: ArrayBuffer) => void;
  onUtteranceEnd: () => void;
  onError: (error: Error) => void;
};

export const INPUT_VOICE_RMS_THRESHOLD = 0.018;
export const INPUT_BARGE_IN_RMS_THRESHOLD = 0.035;
export const INPUT_ONSET_FRAMES = 5; // 100 ms at the 20 ms PCM contract.
export const INPUT_BARGE_IN_ONSET_FRAMES = 12; // 240 ms rejects brief noise during playback.
export const INPUT_HANGOVER_FRAMES = 45; // 900 ms: preserve natural clause pauses.

const clamp = (value: number, minimum: number, maximum: number) => Math.max(minimum, Math.min(maximum, value));

export function deriveInputCalibration(samples: number[], calibratedAt = new Date().toISOString()): InputCalibration {
  const finite = samples.filter((value) => Number.isFinite(value) && value >= 0 && value <= 1).sort((a, b) => a - b);
  if (finite.length < 20) throw new Error("calibration requires at least 20 valid RMS samples");
  const percentile = (ratio: number) => finite[Math.min(finite.length - 1, Math.floor((finite.length - 1) * ratio))];
  const noiseP50 = percentile(0.5);
  const noiseP95 = percentile(0.95);
  // P95 catches steady fans while the cap prevents a short impact from making
  // normal speech unreachable. Barge-in remains deliberately stricter.
  const voiceThreshold = clamp(Math.max(noiseP50 * 2.8, noiseP95 * 1.35), 0.012, 0.055);
  const bargeInThreshold = clamp(Math.max(voiceThreshold * 1.65, noiseP95 * 1.8), 0.030, 0.095);
  return {
    algorithmVersion: 1,
    sampleCount: finite.length,
    noiseP50,
    noiseP95,
    voiceThreshold,
    bargeInThreshold,
    calibratedAt,
  };
}

export class UtteranceBoundaryDetector {
  private capturing = false;
  private voicedFrames = 0;
  private silentFrames = 0;

  observe(
    voiced: boolean,
    acceptStart: () => boolean,
    onsetFrames = INPUT_ONSET_FRAMES,
  ): "start" | "end" | null {
    if (!this.capturing) {
      this.voicedFrames = voiced ? this.voicedFrames + 1 : 0;
      if (this.voicedFrames < onsetFrames) return null;
      this.voicedFrames = 0;
      if (!acceptStart()) return null;
      this.capturing = true;
      this.silentFrames = 0;
      return "start";
    }
    this.silentFrames = voiced ? 0 : this.silentFrames + 1;
    if (this.silentFrames < INPUT_HANGOVER_FRAMES) return null;
    this.capturing = false;
    this.silentFrames = 0;
    return "end";
  }

  observeLevel(
    rms: number,
    mode: "normal" | "barge_in",
    acceptStart: () => boolean,
    thresholds: { normal: number; bargeIn: number } = {
      normal: INPUT_VOICE_RMS_THRESHOLD,
      bargeIn: INPUT_BARGE_IN_RMS_THRESHOLD,
    },
  ): "start" | "end" | null {
    const bargeIn = mode === "barge_in";
    const threshold = bargeIn ? thresholds.bargeIn : thresholds.normal;
    const onsetFrames = bargeIn ? INPUT_BARGE_IN_ONSET_FRAMES : INPUT_ONSET_FRAMES;
    return this.observe(rms >= threshold, acceptStart, onsetFrames);
  }

  snapshot() {
    return {
      capturing: this.capturing,
      voicedFrames: this.voicedFrames,
      silentFrames: this.silentFrames,
      hangoverMs: INPUT_HANGOVER_FRAMES * 20,
    };
  }

  reset(): void {
    this.capturing = false;
    this.voicedFrames = 0;
    this.silentFrames = 0;
  }
}

const WORKLET_SOURCE = `
class CyberWifePcmInput extends AudioWorkletProcessor {
  constructor() {
    super();
    this.step = sampleRate / 16000;
    this.position = 0;
    this.samples = [];
    this.outputSamples = [];
  }
  process(inputs) {
    const input = inputs[0] && inputs[0][0];
    if (!input) return true;
    for (let i = 0; i < input.length; i += 1) this.samples.push(input[i]);
    while (this.position + 1 < this.samples.length) {
      const base = Math.floor(this.position);
      const fraction = this.position - base;
      this.outputSamples.push(this.samples[base] * (1 - fraction) + this.samples[base + 1] * fraction);
      this.position += this.step;
    }
    const consumed = Math.floor(this.position);
    if (consumed > 0) {
      this.samples.splice(0, consumed);
      this.position -= consumed;
    }
    while (this.outputSamples.length >= 320) {
      const pcm = new Int16Array(320);
      let energy = 0;
      for (let i = 0; i < 320; i += 1) {
        const value = Math.max(-1, Math.min(1, this.outputSamples.shift()));
        energy += value * value;
        pcm[i] = value < 0 ? value * 32768 : value * 32767;
      }
      this.port.postMessage({ type: 'frame', pcm: pcm.buffer, rms: Math.sqrt(energy / 320) }, [pcm.buffer]);
    }
    return true;
  }
}
registerProcessor('cyberwife-pcm-input', CyberWifePcmInput);
`;

export class InputAudioSessionController {
  private context: AudioContext | null = null;
  private stream: MediaStream | null = null;
  private worklet: AudioWorkletNode | null = null;
  private silentGain: GainNode | null = null;
  private callbacks: InputAudioCallbacks | null = null;
  private preroll: ArrayBuffer[] = [];
  private boundary = new UtteranceBoundaryDetector();
  private emittedFrames = 0;
  private lastError: string | null = null;
  private state: InputAudioSnapshot["state"] = "stopped";
  private mode: InputMode = "automatic";
  private selectedDeviceId: string | null = null;
  private manualThreshold = INPUT_VOICE_RMS_THRESHOLD;
  private calibration: InputCalibration | null = null;
  private pushToTalkActive = false;

  async start(callbacks: InputAudioCallbacks, options: InputAudioOptions = {}): Promise<void> {
    if (this.context || this.stream) return;
    this.callbacks = callbacks;
    this.configure(options);
    this.state = "starting";
    try {
      const deviceConstraint = this.selectedDeviceId ? { exact: this.selectedDeviceId } : undefined;
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          ...(deviceConstraint ? { deviceId: deviceConstraint } : {}),
        },
        video: false,
      });
      const context = new AudioContext({ latencyHint: "interactive" });
      const moduleUrl = URL.createObjectURL(new Blob([WORKLET_SOURCE], { type: "text/javascript" }));
      try {
        await context.audioWorklet.addModule(moduleUrl);
      } finally {
        URL.revokeObjectURL(moduleUrl);
      }
      const source = context.createMediaStreamSource(stream);
      const worklet = new AudioWorkletNode(context, "cyberwife-pcm-input", {
        numberOfInputs: 1, numberOfOutputs: 1, outputChannelCount: [1],
      });
      // An AudioWorklet must stay connected to be scheduled. A zero-gain node
      // prevents microphone monitoring/feedback while preserving processing.
      const silentGain = context.createGain();
      silentGain.gain.value = 0;
      source.connect(worklet).connect(silentGain).connect(context.destination);
      worklet.port.onmessage = (event: MessageEvent<{ type: string; pcm: ArrayBuffer; rms: number }>) => {
        if (event.data?.type === "frame") this.consumeFrame(event.data.pcm, event.data.rms);
      };
      this.stream = stream;
      this.context = context;
      this.worklet = worklet;
      this.silentGain = silentGain;
      this.state = "listening";
    } catch (value) {
      const error = value instanceof Error ? value : new Error(String(value));
      this.lastError = error.message;
      this.state = "error";
      await this.stop();
      callbacks.onError(error);
      throw error;
    }
  }

  private consumeFrame(pcm: ArrayBuffer, rms: number): void {
    // Roughly 200 ms pre-roll, 100 ms normal onset and a stricter 240 ms
    // playback-state onset. The backend remains the authoritative ASR/VAD;
    // this detector only creates utterance boundaries.
    const mode = this.callbacks?.boundaryMode?.() ?? "normal";
    if (this.mode === "push_to_talk" && !this.pushToTalkActive) {
      this.boundary.reset();
      this.preroll = [];
      if (this.state === "capturing") this.state = "listening";
      return;
    }
    const normalThreshold = this.mode === "manual"
      ? this.manualThreshold
      : this.calibration?.voiceThreshold ?? INPUT_VOICE_RMS_THRESHOLD;
    const bargeInThreshold = this.calibration?.bargeInThreshold
      ?? Math.max(INPUT_BARGE_IN_RMS_THRESHOLD, normalThreshold * 1.65);
    const thresholds = { normal: normalThreshold, bargeIn: bargeInThreshold };
    const wasCapturing = this.boundary.snapshot().capturing;
    if (!wasCapturing) {
      this.preroll.push(pcm.slice(0));
      if (this.preroll.length > 10) this.preroll.shift();
      const event = this.boundary.observeLevel(
        rms,
        mode,
        () => this.callbacks?.onUtteranceStart(this.preroll.map((frame) => frame.slice(0))) ?? false,
        thresholds,
      );
      if (event === "start") {
        this.state = "capturing";
        for (const frame of this.preroll) this.emitFrame(frame);
        this.preroll = [];
      }
      return;
    }
    this.emitFrame(pcm);
    if (this.boundary.observeLevel(rms, mode, () => false, thresholds) === "end") {
      this.state = "listening";
      this.callbacks?.onUtteranceEnd();
    }
  }

  private emitFrame(pcm: ArrayBuffer): void {
    if (pcm.byteLength !== 640) {
      const error = new Error(`input frame must be 640 bytes, received ${pcm.byteLength}`);
      this.lastError = error.message;
      this.callbacks?.onError(error);
      return;
    }
    this.emittedFrames += 1;
    this.callbacks?.onFrame(pcm);
  }

  snapshot(): InputAudioSnapshot {
    return {
      state: this.state,
      emittedFrames: this.emittedFrames,
      activeTracks: this.stream?.getTracks().filter((track) => track.readyState === "live").length ?? 0,
      contextState: this.context?.state ?? "closed",
      lastError: this.lastError,
      mode: this.mode,
      selectedDeviceId: this.selectedDeviceId,
      pushToTalkActive: this.pushToTalkActive,
      calibration: this.calibration ? { ...this.calibration } : null,
      boundary: this.boundary.snapshot(),
    };
  }

  async stop(): Promise<void> {
    const stream = this.stream;
    const context = this.context;
    this.stream = null;
    this.context = null;
    this.callbacks = null;
    this.boundary.reset();
    this.preroll = [];
    this.worklet?.disconnect();
    this.silentGain?.disconnect();
    this.worklet = null;
    this.silentGain = null;
    for (const track of stream?.getTracks() ?? []) track.stop();
    if (context && context.state !== "closed") await context.close();
    this.state = "stopped";
    this.pushToTalkActive = false;
  }

  configure(options: InputAudioOptions): void {
    if (options.mode !== undefined) this.mode = options.mode;
    if (options.deviceId !== undefined) this.selectedDeviceId = options.deviceId || null;
    if (options.manualThreshold !== undefined) this.manualThreshold = clamp(options.manualThreshold, 0.008, 0.080);
    if (options.calibration !== undefined) this.calibration = options.calibration ? { ...options.calibration } : null;
  }

  setPushToTalk(active: boolean): void {
    this.pushToTalkActive = this.mode === "push_to_talk" && active;
    if (!this.pushToTalkActive) {
      const wasCapturing = this.boundary.snapshot().capturing;
      this.boundary.reset();
      this.preroll = [];
      if (wasCapturing) this.callbacks?.onUtteranceEnd();
      if (this.state === "capturing") this.state = "listening";
    }
  }

  async selectDevice(deviceId: string | null): Promise<void> {
    const callbacks = this.callbacks;
    const wasRunning = Boolean(this.context || this.stream);
    await this.stop();
    this.selectedDeviceId = deviceId || null;
    if (wasRunning && callbacks) {
      try {
        await this.start(callbacks, { deviceId: this.selectedDeviceId });
      } catch (error) {
        this.selectedDeviceId = null;
        await this.start(callbacks, { deviceId: null });
        throw error;
      }
    }
  }

  async listDevices(): Promise<InputDevice[]> {
    if (!navigator.mediaDevices?.enumerateDevices) return [];
    const devices = await navigator.mediaDevices.enumerateDevices();
    let ordinal = 0;
    return devices.filter((item) => item.kind === "audioinput").map((item) => {
      ordinal += 1;
      return {
        deviceId: item.deviceId,
        label: item.label || `麦克风 ${ordinal}`,
        isDefault: item.deviceId === "default",
      };
    });
  }

  async calibrate(deviceId: string | null = this.selectedDeviceId, durationMs = 2000): Promise<InputCalibration> {
    if (this.context || this.stream) throw new Error("请先结束当前对话再校准麦克风");
    if (!navigator.mediaDevices?.getUserMedia) throw new Error("当前浏览器不支持麦克风校准");
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
        ...(deviceId ? { deviceId: { exact: deviceId } } : {}),
      },
      video: false,
    });
    const audioContext = new AudioContext({ latencyHint: "interactive" });
    const analyser = audioContext.createAnalyser();
    analyser.fftSize = 1024;
    const source = audioContext.createMediaStreamSource(stream);
    const silentGain = audioContext.createGain();
    silentGain.gain.value = 0;
    source.connect(analyser).connect(silentGain).connect(audioContext.destination);
    const values = new Float32Array(analyser.fftSize);
    const samples: number[] = [];
    const deadline = performance.now() + clamp(durationMs, 400, 5000);
    try {
      while (performance.now() < deadline) {
        analyser.getFloatTimeDomainData(values);
        let energy = 0;
        for (const value of values) energy += value * value;
        samples.push(Math.sqrt(energy / values.length));
        await new Promise((resolve) => window.setTimeout(resolve, 20));
      }
      const result = deriveInputCalibration(samples);
      this.calibration = result;
      this.selectedDeviceId = deviceId || null;
      return { ...result };
    } finally {
      source.disconnect();
      analyser.disconnect();
      silentGain.disconnect();
      for (const track of stream.getTracks()) track.stop();
      await audioContext.close();
    }
  }
}

export const InputAudioSession = new InputAudioSessionController();
