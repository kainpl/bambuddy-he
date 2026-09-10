import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Independent design preview: the production entry and API proxy are not loaded.
export default defineConfig({
  plugins: [react()],
  server: { host: '127.0.0.1', port: 5186, strictPort: true },
  build: {
    outDir: '../temp/monitor-mockup',
    emptyOutDir: true,
    rollupOptions: { input: 'monitor-mockup.html' },
  },
});
