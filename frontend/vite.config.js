import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// El servidor de desarrollo hace de proxy hacia Django para que el navegador
// vea una sola procedencia: así la cookie de sesión y el token CSRF funcionan
// igual que en producción detrás de Nginx.
export default defineConfig({
  plugins: [vue()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: false },
      '/admin': { target: 'http://127.0.0.1:8000', changeOrigin: false },
      '/static': { target: 'http://127.0.0.1:8000', changeOrigin: false }
    }
  },
  build: { outDir: 'dist', emptyOutDir: true }
})
