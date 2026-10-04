// ConversationScreen — 六态对话主屏（FR-07/08/09）
// M1 阶段：仅 UI 骨架 + 真实健康状态拉取；M3 起接入 ASR/TTS/Avatar。

import { useEffect, useState } from "react";
import { ConversationClient } from "../../services/ConversationClient";
import { MediaSession } from "../../services/MediaSession";

export type ConversationState =
  | "idle" | "listening" | "thinking" | "speaking" | "interrupted" | "error";

export function ConversationScreen() {
  const [state, setState] = useState<ConversationState>("idle");
  const [health, setHealth] = useState<{
    status: string;
    components: Record<string, { status: string }>;
  } | null>(null);

  useEffect(() => {
    ConversationClient.getHealth().then(setHealth).catch(console.error);
    const t = setInterval(() => {
      ConversationClient.getHealth().then(setHealth).catch(() => {});
    }, 5000);
    return () => clearInterval(t);
  }, []);

  const start = () => {
    MediaSession.start().then(() => setState("listening")).catch((e) => {
      console.error("[Conversation] start failed", e);
      setState("error");
    });
  };

  const stop = () => {
    MediaSession.stop().then(() => setState("idle")).catch(console.error);
  };

  const healthy = health && health.status !== "error" && Object.values(health.components).some((c) => c.status === "ready");

  return (
    <div className="conversation">
      <div className="health-banner" role="status">
        {health ? (
          <>
            <span data-status={health.status}>{health.status}</span>
            {" · "}
            {Object.entries(health.components).map(([k, v]) => (
              <span key={k} data-comp={k} data-status={v.status} style={{ marginRight: 8 }}>
                {k}:{v.status}
              </span>
            ))}
          </>
        ) : (
          <span>加载中…</span>
        )}
      </div>

      <div className="state-badge" aria-live="polite">
        {state}
      </div>

      <div className="voice-orb">
        <button
          onClick={state === "idle" ? start : stop}
          disabled={!healthy}
          aria-label={state === "idle" ? "开始对话" : "结束对话"}
        >
          {state === "idle" ? "开始对话" : "结束"}
        </button>
      </div>

      <div className="subtitles" aria-live="polite">
        <p className="user-subtitle">用户字幕：—</p>
        <p className="assistant-subtitle">角色字幕：—</p>
      </div>
    </div>
  );
}
