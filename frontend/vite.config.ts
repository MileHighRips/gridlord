import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => ({
  // Local dev should load from the site root; GitHub Pages production builds use the repo subpath.
  base: process.env.VITE_BASE ?? (mode === 'production' ? '/gridlord/' : '/'),
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
}));
