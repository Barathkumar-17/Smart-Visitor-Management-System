import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The client always calls same-origin /api/... so CORS never comes up.
// The prefix is stripped here: /api/auth/login -> http://127.0.0.1:8000/auth/login
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
});
