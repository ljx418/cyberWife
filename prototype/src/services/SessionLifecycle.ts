export type LifecycleState = "stopped" | "idle" | "active" | "recovering" | "error";

export type LifecycleSnapshot = {
  state: LifecycleState;
  generation: number;
  recoveryCount: number;
  reason: string | null;
  lastError: string | null;
};

export type LifecycleHooks = {
  stopResources: (generation: number) => Promise<void>;
  probeGateway: (generation: number) => Promise<boolean>;
  onState?: (snapshot: LifecycleSnapshot) => void;
};

export class SessionLifecycleController {
  private state: LifecycleState = "stopped";
  private generation = 0;
  private recoveryCount = 0;
  private reason: string | null = null;
  private lastError: string | null = null;
  private sessionActive = false;
  private hiddenObserved = false;
  private recovery: Promise<LifecycleSnapshot> | null = null;
  private listening = false;

  constructor(private readonly hooks: LifecycleHooks) {}

  snapshot(): LifecycleSnapshot {
    return { state: this.state, generation: this.generation, recoveryCount: this.recoveryCount, reason: this.reason, lastError: this.lastError };
  }

  start(): void {
    if (this.listening) return;
    this.listening = true;
    this.state = "idle";
    document.addEventListener("visibilitychange", this.onVisibility);
    window.addEventListener("online", this.onOnline);
    window.addEventListener("pageshow", this.onPageShow);
    this.emit();
  }

  stop(): void {
    if (!this.listening) return;
    this.listening = false;
    document.removeEventListener("visibilitychange", this.onVisibility);
    window.removeEventListener("online", this.onOnline);
    window.removeEventListener("pageshow", this.onPageShow);
    this.generation += 1;
    this.sessionActive = false;
    this.state = "stopped";
    this.emit();
  }

  markSessionActive(): void {
    this.sessionActive = true;
    this.state = "active";
    this.reason = null;
    this.lastError = null;
    this.emit();
  }

  markIdle(): void {
    this.sessionActive = false;
    if (this.state !== "recovering") this.state = "idle";
    this.emit();
  }

  isRecovering(): boolean {
    return this.state === "recovering";
  }

  requestRecovery(reason: string): Promise<LifecycleSnapshot> {
    if (this.recovery) return this.recovery;
    if (!this.sessionActive && this.state !== "error") return Promise.resolve(this.snapshot());
    const generation = ++this.generation;
    this.recoveryCount += 1;
    this.reason = reason;
    this.lastError = null;
    this.state = "recovering";
    this.emit();
    this.recovery = (async () => {
      try {
        await this.hooks.stopResources(generation);
        if (generation !== this.generation) return this.snapshot();
        this.sessionActive = false;
        const ready = await this.hooks.probeGateway(generation);
        if (generation !== this.generation) return this.snapshot();
        this.state = ready ? "idle" : "error";
        this.lastError = ready ? null : "gateway_not_ready";
      } catch (value) {
        if (generation === this.generation) {
          this.sessionActive = false;
          this.state = "error";
          this.lastError = value instanceof Error ? value.message : String(value);
        }
      } finally {
        if (generation === this.generation) this.emit();
        this.recovery = null;
      }
      return this.snapshot();
    })();
    return this.recovery;
  }

  private emit(): void {
    this.hooks.onState?.(this.snapshot());
  }

  private onVisibility = (): void => {
    if (document.hidden) {
      this.hiddenObserved = this.sessionActive;
      return;
    }
    if (this.hiddenObserved) {
      this.hiddenObserved = false;
      void this.requestRecovery("visibility_restored");
    }
  };

  private onOnline = (): void => {
    if (this.sessionActive || this.state === "error") void this.requestRecovery("network_restored");
  };

  private onPageShow = (event: PageTransitionEvent): void => {
    if (event.persisted && (this.sessionActive || this.state === "error")) void this.requestRecovery("page_restored");
  };
}
