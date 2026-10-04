// cyberWife V1 AppShell — 路由 + 主题 + HostBridge（M1 阶段）

import { useEffect, useState } from "react";
import { HostBridge } from "../platform/HostBridge";

export type ThemeMode = "dark" | "quiet" | "cinematic" | "system";

const THEME_KEY = "cyberWife.ui.theme";

export function AppShell({ children }: { children: React.ReactNode }) {
  const [theme, setTheme] = useState<ThemeMode>(() => {
    const saved = localStorage.getItem(THEME_KEY) as ThemeMode | null;
    return saved || "cinematic";
  });

  useEffect(() => {
    localStorage.setItem(THEME_KEY, theme);
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  useEffect(() => {
    // 启动时探测 HostBridge；M1 阶段仅打印模式
    HostBridge.getWindowMode().then((mode) => {
      console.info("[AppShell] host mode =", mode);
    });
  }, []);

  return (
    <div className="app-shell" data-theme={theme}>
      <div className="theme-pills">
        {(["cinematic", "dark", "quiet"] as ThemeMode[]).map((t) => (
          <button key={t} onClick={() => setTheme(t)} aria-pressed={theme === t}>
            {t}
          </button>
        ))}
      </div>
      <main>{children}</main>
    </div>
  );
}
