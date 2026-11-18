import './styles.css'

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import App from './app.tsx'
import { preloadInitialLanguage } from './i18n'
import { watchTheme } from './theme'

// Follow the OS light/dark appearance. theme.ts paints the first frame on
// import (synchronously, from the media query); this subscribes to live OS
// theme changes via the authoritative Tauri window theme.
void watchTheme()

// Catalogues are per-language chunks. Waiting the few milliseconds for the
// initial one means the window never flashes English on a Japanese machine.
await preloadInitialLanguage()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>
)
