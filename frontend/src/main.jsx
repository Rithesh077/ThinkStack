import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

// The type system, self-hosted. This app's whole claim is that it works with no
// network, and the previous Google Fonts <link> quietly broke that: offline, the
// entire identity fell back to Georgia and the system sans. Vite fingerprints
// these woff2 into dist/assets, so scripts/build.sh's bundled-UI integrity check
// covers them for free.
//
// The wght axis, not opsz. The design varies weight (300/400/500/600); nothing
// in it sets font-variation-settings for optical size, and at UI sizes auto
// optical sizing is imperceptible. One file per subset instead of two.
import '@fontsource-variable/newsreader'
import '@fontsource-variable/newsreader/wght-italic.css'
import '@fontsource-variable/ibm-plex-sans'
import '@fontsource/ibm-plex-mono/400.css'
import '@fontsource/ibm-plex-mono/500.css'

import './index.css'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
