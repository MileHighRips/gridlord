import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// `base` is configurable for GitHub Pages project sites (e.g. '/gridlord/').
export default defineConfig({
  base: process.env.VITE_BASE ?? '/',
  plugins: [react()],
  server: { port: 5173 },
});
