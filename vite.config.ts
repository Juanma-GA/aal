import path from 'node:path';
import { fileURLToPath } from 'node:url';
import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

const ROOT = path.dirname(fileURLToPath(import.meta.url));

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': path.join(ROOT, 'src') },
  },
  server: {
    proxy: {
      // Forwards to the FastAPI backend (backend/app/main.py), which must be
      // running separately (uvicorn app.main:app, port 8000): Vite only
      // proxies the request, it does not start that process.
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});
