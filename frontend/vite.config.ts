import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

// Phase 6 : l'application est servie par Flask sous /app/ (build dans frontend/dist).
// En développement (npm run dev), Vite redirige les appels vers Flask (port 5000).
const flask = { target: 'http://127.0.0.1:5000', changeOrigin: true, secure: false };

export default defineConfig({
  base: '/app/',
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    chunkSizeWarningLimit: 1200,
  },
  server: {
    port: 5173,
    proxy: {
      '/api': flask,
      '/ask_ia': flask,
      '/telecharger': flask,
      '/vendor': flask,
      '/view_report': flask,
    },
  },
});
