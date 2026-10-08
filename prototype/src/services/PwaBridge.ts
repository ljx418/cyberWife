type InstallPromptEvent = Event & {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
};

type InstallListener = (available: boolean) => void;

let deferredPrompt: InstallPromptEvent | null = null;
const installListeners = new Set<InstallListener>();

if (typeof window !== 'undefined') {
  window.addEventListener('beforeinstallprompt', (event) => {
    event.preventDefault();
    deferredPrompt = event as InstallPromptEvent;
    installListeners.forEach((listener) => listener(true));
  });
  window.addEventListener('appinstalled', () => {
    deferredPrompt = null;
    installListeners.forEach((listener) => listener(false));
  });
}

export const PwaBridge = {
  subscribeInstallAvailability(listener: InstallListener): () => void {
    installListeners.add(listener);
    listener(deferredPrompt !== null);
    return () => installListeners.delete(listener);
  },

  async configure(enabled: boolean): Promise<'registered' | 'unregistered' | 'unsupported'> {
    if (!('serviceWorker' in navigator)) return 'unsupported';
    if (enabled) {
      await navigator.serviceWorker.register('/sw.js', { scope: '/' });
      return 'registered';
    }
    const registration = await navigator.serviceWorker.getRegistration('/');
    const scriptUrl = registration?.active?.scriptURL || registration?.waiting?.scriptURL || registration?.installing?.scriptURL;
    if (registration && scriptUrl && new URL(scriptUrl).pathname === '/sw.js') {
      await registration.unregister();
      return 'unregistered';
    }
    return 'unregistered';
  },

  async requestInstall(): Promise<'accepted' | 'dismissed' | 'already-installed' | 'unsupported'> {
    if (window.matchMedia('(display-mode: standalone)').matches) return 'already-installed';
    if (!deferredPrompt) return 'unsupported';
    const prompt = deferredPrompt;
    deferredPrompt = null;
    installListeners.forEach((listener) => listener(false));
    await prompt.prompt();
    const choice = await prompt.userChoice;
    return choice.outcome;
  },

  async toggleFullscreen(): Promise<'entered' | 'exited' | 'unsupported'> {
    if (document.fullscreenElement) {
      if (!document.exitFullscreen) return 'unsupported';
      await document.exitFullscreen();
      return 'exited';
    }
    if (!document.documentElement.requestFullscreen) return 'unsupported';
    await document.documentElement.requestFullscreen({ navigationUI: 'hide' });
    return 'entered';
  },
};
