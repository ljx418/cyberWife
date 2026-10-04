// SettingsDrawer — 设置抽屉（FR-11 / M2-04 脏检查 / M2-stretch 上传）
//
// M2-stretch：增加「人物」与「声音」的上传/录音入口（multipart / MediaRecorder）。

import { useEffect, useRef, useState } from "react";
import { ConversationClient, Profile } from "../../services/ConversationClient";

const TABS = ["人物", "声音与人设", "记忆", "隐私", "运行状态"] as const;
type Tab = (typeof TABS)[number];

export function SettingsDrawer({ defaultTab = "运行状态" as Tab }: { defaultTab?: Tab } = {}) {
  const [open, setOpen] = useState(true);  // M2-stretch 默认打开录音入口
  const [tab, setTab] = useState<Tab>(defaultTab);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [draft, setDraft] = useState<Profile | null>(null);
  const [dirty, setDirty] = useState(false);
  const [pendingClose, setPendingClose] = useState(false);
  const [uploadMsg, setUploadMsg] = useState<string | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  useEffect(() => {
    if (!open || tab !== "声音与人设") return;
    ConversationClient.getProfile().then((p) => {
      setProfile(p);
      setDraft(p);
      setDirty(false);
    }).catch(console.error);
  }, [open, tab]);

  useEffect(() => {
    if (open && dialogRef.current) dialogRef.current.focus();
  }, [open]);

  const requestClose = () => {
    if (dirty) setPendingClose(true); else doClose();
  };
  const doClose = () => {
    setOpen(false);
    setPendingClose(false);
    setDirty(false);
    setUploadMsg(null);
    setIsRecording(false);
  };
  const discardAndClose = () => { setDraft(profile); setDirty(false); doClose(); };

  // ── 文件上传（multipart）───────────────────────────────────────
  const onFilePick = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    setUploadMsg("上传中…");
    try {
      const fd = new FormData();
      fd.append("file", f);
      const r = await fetch(`${ConversationClient.gatewayBase()}/api/v1/assets/portrait/preview`, {
        method: "POST",
        body: fd,
      });
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        throw new Error(err.code || `HTTP ${r.status}`);
      }
      const meta = await r.json();
      setUploadMsg(`已接收：${meta.size_bytes} 字节，mime=${meta.mime}`);
    } catch (e: any) {
      setUploadMsg(`上传失败：${e.message || e}`);
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  // ── 录音（MediaRecorder）────────────────────────────────────────
  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { sampleRate: 16000, channelCount: 1 } });
      const mr = new MediaRecorder(stream, { mimeType: "audio/webm" });
      chunksRef.current = [];
      mr.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data); };
      mr.onstop = async () => {
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        const buf = await blob.arrayBuffer();
        const b64 = btoa(String.fromCharCode(...new Uint8Array(buf)));
        try {
          const r = await fetch(`${ConversationClient.gatewayBase()}/api/v1/assets/voice/record`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ filename: "user_clip.webm", data_b64: b64 }),
          });
          if (!r.ok) {
            const err = await r.json().catch(() => ({}));
            throw new Error(err.code || `HTTP ${r.status}`);
          }
          const meta = await r.json();
          setUploadMsg(`录音已接收：${meta.size_bytes} 字节`);
        } catch (e: any) {
          setUploadMsg(`录音上传失败：${e.message || e}`);
        }
        stream.getTracks().forEach((t) => t.stop());
      };
      mr.start();
      recorderRef.current = mr;
      setIsRecording(true);
      setUploadMsg("录音中…");
    } catch (e: any) {
      setUploadMsg(`无法访问麦克风：${e.message || e}`);
    }
  };
  const stopRecording = () => {
    if (recorderRef.current && recorderRef.current.state === "recording") {
      recorderRef.current.stop();
    }
    setIsRecording(false);
  };

  return (
    <div className="settings-drawer">
      <button onClick={() => setOpen((v) => !v)} aria-expanded={open}>设置</button>
      {open && (
        <aside role="dialog" aria-label="设置抽屉" ref={dialogRef} tabIndex={-1}>
          <nav>
            <ul>
              {TABS.map((t) => (
                <li key={t}>
                  <button onClick={() => setTab(t)} aria-current={tab === t ? "page" : undefined}>{t}</button>
                </li>
              ))}
            </ul>
          </nav>
          <section>
            <h2>{tab}</h2>
            {tab === "人物" && (
              <div>
                <p>上传人物照片（PNG/JPG，最大 50MB）。</p>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/png,image/jpeg"
                  onChange={onFilePick}
                  aria-label="选择人物照片"
                />
                {uploadMsg && <p role="status">{uploadMsg}</p>}
              </div>
            )}
            {tab === "声音与人设" && (
              <div>
                {draft ? (
                  <ProfileEditor
                    draft={draft}
                    dirty={dirty}
                    onChange={(next) => { setDraft(next); setDirty(true); }}
                    onSave={async () => {
                      try {
                        const saved = await ConversationClient.putProfile({
                          name: draft.name,
                          user_nickname: draft.user_nickname,
                          expected_version: draft.version,
                        });
                        setProfile(saved);
                        setDraft(saved);
                        setDirty(false);
                      } catch (e: any) {
                        alert(`保存失败：${e.message}`);
                      }
                    }}
                  />
                ) : (
                  <p style={{ color: "#d3a06f" }}>Profile 尚未保存；可先上传参考音频，再补填人设。</p>
                )}
                <hr />
                <p>录音 5–15 秒参考音频（WAV / WebM，最大 50MB）。</p>
                {!isRecording ? (
                  <button onClick={startRecording} style={{ padding: "8px 16px", background: "#8fc6c9", color: "#0a0d0e", border: "none", borderRadius: 4, cursor: "pointer" }}>
                    开始录音
                  </button>
                ) : (
                  <button onClick={stopRecording} style={{ padding: "8px 16px", background: "#d58d86", color: "#fff", border: "none", borderRadius: 4, cursor: "pointer" }}>
                    停止并上传
                  </button>
                )}
                {uploadMsg && <p role="status" style={{ color: "#8fc6c9", marginTop: 8 }}>{uploadMsg}</p>}
              </div>
            )}
            {!["人物", "声音与人设"].includes(tab) && (
              <p>M2 阶段：其他分类 UI 骨架；M2-M5 接入具体字段。</p>
            )}
          </section>
          <button onClick={requestClose}>关闭</button>
          {pendingClose && (
            <div role="alertdialog" aria-label="未保存的更改">
              <p>有未保存的更改，是否放弃？</p>
              <button onClick={discardAndClose}>放弃</button>
              <button onClick={() => setPendingClose(false)}>继续编辑</button>
            </div>
          )}
        </aside>
      )}
    </div>
  );
}


function ProfileEditor({
  draft, dirty, onChange, onSave,
}: {
  draft: Profile; dirty: boolean;
  onChange: (next: Profile) => void;
  onSave: () => void | Promise<void>;
}) {
  return (
    <form
      onSubmit={(e) => { e.preventDefault(); onSave(); }}
      aria-describedby={dirty ? "dirty-hint" : undefined}
    >
      <label>
        名称
        <input value={draft.name} onChange={(e) => onChange({ ...draft, name: e.target.value })} aria-required="true" />
      </label>
      <label>
        用户称呼
        <input value={draft.user_nickname} onChange={(e) => onChange({ ...draft, user_nickname: e.target.value })} aria-required="true" />
      </label>
      <label>
        性格关键词
        <textarea value={draft.persona} onChange={(e) => onChange({ ...draft, persona: e.target.value })} />
      </label>
      <label>
        关系背景
        <textarea value={draft.relationship_context} onChange={(e) => onChange({ ...draft, relationship_context: e.target.value })} />
      </label>
      <label>
        示例对话
        <textarea value={draft.example_dialogue} onChange={(e) => onChange({ ...draft, example_dialogue: e.target.value })} rows={4} />
      </label>
      {dirty && <p id="dirty-hint" style={{ color: "#d58d86" }}>有未保存的更改</p>}
      <button type="submit" disabled={!dirty}>保存（乐观并发，version 自增）</button>
    </form>
  );
}
