// Component-mode plugin bundle only — Vite lib mode building
// src/plugin.jsx -> dist/remote-screen.js, the bundle aw-app.json's
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
      fileName: () => 'remote-screen.js',
    },
    rollupOptions: { external: ['react', 'react-dom'] },
  },
});
