import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';

/**
 * Native shell setup.
 *
 * Only runs inside the Android app; in a browser these imports resolve but the
 * calls no-op, so the web build is unaffected.
 */
async function setupNative() {
  if (!window.Capacitor?.isNativePlatform?.()) return;

  // Scopes the native-only CSS in index.css. Set before anything awaits, so
  // the first paint already has it.
  document.body.classList.add('native-app');

  try {
    const { StatusBar, Style } = await import('@capacitor/status-bar');
    // The app is dark, so the status bar needs light icons. The default is
    // dark-on-dark, which renders the clock and battery effectively invisible.
    await StatusBar.setStyle({ style: Style.Dark });
    await StatusBar.setBackgroundColor({ color: 'var(--bg)' });
    // Do NOT overlay: with overlay on, the first row of the dashboard sits
    // under the clock. The CSS safe-area insets then have nothing to do, and
    // reserving the space in native is more reliable than guessing it in CSS.
    await StatusBar.setOverlaysWebView({ overlay: false });
  } catch {
    /* plugin missing in a web build - nothing to configure */
  }

  try {
    const { SplashScreen } = await import('@capacitor/splash-screen');
    // Hide once React has actually rendered, rather than on a fixed timer, so
    // a slow first paint never shows a blank screen between the two.
    await SplashScreen.hide();
  } catch {
    /* no splash plugin */
  }
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

setupNative();
