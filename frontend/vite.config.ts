import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// GitHub Pages project sites must serve assets from the repo subpath.
export default defineConfig({
  base: process.env.VITE_BASE ?? '/gridlord/',
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 4173,
    strictPort: true,
  },
  preview: {
    host: '0.0.0.0',
    port: 4173,
    strictPort: true,
  },
});
