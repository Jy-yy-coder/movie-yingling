import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// 影灵 CINE · 电影宇宙前端
// dev 时把 /api 与海报静态路径代理到 FastAPI（cine.main，默认 8010）
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8010',
      '/posters': 'http://127.0.0.1:8010',
      '/posters_thumb': 'http://127.0.0.1:8010',
    },
  },
  build: {
    outDir: 'dist',
    chunkSizeWarningLimit: 1500,
  },
})
