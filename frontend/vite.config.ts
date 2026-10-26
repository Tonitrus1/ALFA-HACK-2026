import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
const target = process.env.BACKEND_ORIGIN ?? 'http://127.0.0.1:18080';
export default defineConfig({ plugins: [react()], server: { host: '127.0.0.1', port: 5173, strictPort: true,
 proxy: Object.fromEntries(['/api', '/demo/api', '/assets/feed'].map(p => [p, {target, changeOrigin: false}])) },
 build: {chunkSizeWarningLimit: 1100} });
