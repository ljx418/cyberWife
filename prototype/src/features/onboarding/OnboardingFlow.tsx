// OnboardingFlow — 五步首次设置（FR-01）
// M1 阶段：UI 骨架 + draft API；具体文件处理/试听在 M2 接入。

import { useEffect, useState } from "react";
import { ConversationClient } from "../../services/ConversationClient";

const STEPS = ["本地与授权", "运行检查", "人物形象", "声音样本", "人设关系"] as const;

export function OnboardingFlow() {
  const [step, setStep] = useState(0);
  const [draft, setDraft] = useState({
    consent_granted: false,
    step_completed: 0,
    profile_draft_json: {} as Record<string, unknown>,
  });

  useEffect(() => {
    ConversationClient.getOnboardingDraft().then(setDraft).catch(console.error);
  }, []);

  const advance = async (next: number) => {
    if (next < 0 || next > 4) return;
    const updated = { ...draft, step_completed: next };
    setDraft(updated);
    setStep(next);
    try {
      await ConversationClient.putOnboardingDraft({ step_completed: next });
    } catch (e) {
      console.error("[Onboarding] advance failed", e);
    }
  };

  const grantConsent = async () => {
    const updated = { ...draft, consent_granted: true };
    setDraft(updated);
    try {
      await ConversationClient.putOnboardingDraft({ consent_granted: true });
    } catch (e) {
      console.error("[Onboarding] consent failed", e);
    }
  };

  return (
    <div className="onboarding">
      <ol className="steps" aria-label="首次设置步骤">
        {STEPS.map((label, i) => (
          <li key={label} aria-current={i === step ? "step" : undefined}>
            {i + 1}. {label}
          </li>
        ))}
      </ol>

      {step === 0 && (
        <section>
          <h2>本地处理与授权</h2>
          <p>cyberWife 在本机处理你的照片与声音；不出网、不外发。</p>
          <button onClick={grantConsent} disabled={draft.consent_granted}>
            {draft.consent_granted ? "已授权（私人非商业用途）" : "勾选并继续"}
          </button>
          <button onClick={() => advance(1)} disabled={!draft.consent_granted}>
            下一步
          </button>
        </section>
      )}

      {step >= 1 && step <= 4 && (
        <section>
          <h2>第 {step + 1} 步：{STEPS[step]}</h2>
          <p>M1 阶段：UI 骨架；M2 起接入真实资产与人设字段。</p>
          <button onClick={() => advance(Math.max(0, step - 1))}>上一步</button>
          <button onClick={() => advance(Math.min(4, step + 1))}>下一步</button>
          {step === 4 && (
            <button onClick={() => alert("Onboarding complete (M1 stub)")}>完成</button>
          )}
        </section>
      )}
    </div>
  );
}
