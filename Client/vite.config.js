import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite';

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Pin the Client dev port so the Auth0 redirect_uri (window.location.origin)
    // always matches a registered callback URL. 5173 is used by the static site,
    // so the Client owns 5174. strictPort makes Vite fail loudly if it's taken
    // instead of silently drifting to another port (which Auth0 would reject).
    port: 5174,
    strictPort: true,
  },
})
