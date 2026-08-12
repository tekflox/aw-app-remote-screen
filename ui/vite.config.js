// Component-mode plugin bundle only — Vite lib mode building
// src/plugin.jsx -> dist/rdp-vnc.js, the bundle aw-app.json's
// contributes.frontend.bundle points at. Same shape as aw-app-whiteboard's.
import { defineConfig } from 'vite';

export default defineConfig({
  esbuild: {
    jsxFactory: 'host.h',
    jsxFragment: 'host.React.Fragment',
  },
  build: {
    outDir: 'dist',
    lib: {
      entry: 'src/plugin.jsx',
      formats: ['es'],
      fileName: () => 'rdp-vnc.js',
    },
    rollupOptions: { external: ['react', 'react-dom'] },
  },
});
