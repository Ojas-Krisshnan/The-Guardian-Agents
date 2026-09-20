import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  base: './',
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/auth': 'http://127.0.0.1:8000',
      '/teacher': 'http://127.0.0.1:8000',
      '/student': 'http://127.0.0.1:8000',
      '/runs': 'http://127.0.0.1:8000',
      '/web': 'http://127.0.0.1:8000',
    },
  },
});
