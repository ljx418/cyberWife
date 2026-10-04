// HostBridge — 桌面壳抽象接口（FR-19；prototype-spec §11）
//
// V1 浏览器实现：getWindowMode 永远返回 'browser'；其余方法为安全空操作。

export type WindowMode = "browser" | "compact" | "pet";

export interface HostBridgeApi {
  getWindowMode(): Promise<WindowMode>;
  setWindowMode(mode: WindowMode): Promise<HostActionResult>;
  setAlwaysOnTop(enabled: boolean): Promise<HostActionResult>;
  setTransparent(enabled: boolean): Promise<HostActionResult>;
  quit(): Promise<HostActionResult>;
}

export interface HostActionResult { supported: false; reason: "browser_unsupported" }
const unsupported = async (): Promise<HostActionResult> => ({ supported: false, reason: "browser_unsupported" })

const NOOP: HostBridgeApi = {
  async getWindowMode() { return "browser"; },
  setWindowMode: unsupported,
  setAlwaysOnTop: unsupported,
  setTransparent: unsupported,
  quit: unsupported,
};

export const HostBridge: HostBridgeApi = NOOP;
