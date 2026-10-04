import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import { AppShell } from './app/AppShell'
import { SettingsDrawer as LegacySettingsDrawer } from './features/settings/SettingsDrawer'
import './styles.css'

function LegacyDevelopmentEntry() {
  return (
    <AppShell>
      <div style={{ padding: 24, maxWidth: 720 }} data-testid="legacy-development-entry">
        <h2>cyberWife 开发上传入口</h2>
        <p>此入口仅用于开发兼容性检查；产品根路由固定进入沉浸式主舞台。</p>
        <LegacySettingsDrawer defaultTab="声音与人设" />
      </div>
    </AppShell>
  )
}

const legacy = import.meta.env.DEV && new URLSearchParams(window.location.search).get('legacy') === '1'
createRoot(document.getElementById('root')!).render(
  <StrictMode>{legacy ? <LegacyDevelopmentEntry /> : <App />}</StrictMode>,
)
