// Continuous browser microphone capture for the Gateway's 16 kHz/20 ms PCM contract.

export type InputAudioSnapshot = {
  state: "stopped" | "starting" | "listening" | "capturing" | "error";
  emittedFrames: number;
  activeTracks: number;
  contextState: AudioContextState | "closed";
  lastError: string | null;
};

export type InputAudioCallbacks = {
  onUtteranceStart: (preroll: ArrayBuffer[]) => boolean;
  onFrame: (pcm: ArrayBuffer) => void;
  onUtteranceEnd: () => void;
  onError: (error: Error) => void;
};

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
  private capturing = false;
  private voicedFrames = 0;
  private silentFrames = 0;
  private emittedFrames = 0;
  private lastError: string | null = null;
  private state: InputAudioSnapshot["state"] = "stopped";

  async start(callbacks: InputAudioCallbacks): Promise<void> {
    if (this.context || this.stream) return;
    this.callbacks = callbacks;
    this.state = "starting";
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
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
    // Roughly 200 ms pre-roll, 60 ms onset and 600 ms hangover. The backend
    // remains the authoritative ASR/VAD; this detector only creates utterance boundaries.
    const voiced = rms >= 0.012;
    if (!this.capturing) {
      this.preroll.push(pcm.slice(0));
      if (this.preroll.length > 10) this.preroll.shift();
      this.voicedFrames = voiced ? this.voicedFrames + 1 : 0;
      if (this.voicedFrames >= 3) {
        const accepted = this.callbacks?.onUtteranceStart(this.preroll.map((frame) => frame.slice(0))) ?? false;
        if (accepted) {
          this.capturing = true;
          this.state = "capturing";
          for (const frame of this.preroll) this.emitFrame(frame);
        }
        this.preroll = [];
        this.voicedFrames = 0;
      }
      return;
    }
    this.emitFrame(pcm);
    this.silentFrames = voiced ? 0 : this.silentFrames + 1;
    if (this.silentFrames >= 30) {
      this.capturing = false;
      this.silentFrames = 0;
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
    };
  }

  async stop(): Promise<void> {
    const stream = this.stream;
    const context = this.context;
    this.stream = null;
    this.context = null;
    this.callbacks = null;
    this.capturing = false;
    this.preroll = [];
    this.voicedFrames = 0;
    this.silentFrames = 0;
    this.worklet?.disconnect();
    this.silentGain?.disconnect();
    this.worklet = null;
    this.silentGain = null;
    for (const track of stream?.getTracks() ?? []) track.stop();
    if (context && context.state !== "closed") await context.close();
    this.state = "stopped";
  }
}

export const InputAudioSession = new InputAudioSessionController();
