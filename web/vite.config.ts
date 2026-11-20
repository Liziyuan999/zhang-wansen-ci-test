import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 后端路径为 /api 前缀（FastAPI 已在路由中写入 /api），开发代理直接转发到 localhost:8000
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    // 固定 5174：避免端口被占用后 Vite 自动递增导致 README/start.bat 与实际运行不一致
    port: 5174,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        // 手动拆包：将高频第三方依赖从业务主包中分离，缩小首屏主包体积
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined
          // element-plus 全家桶单独成包（含图标，体积最大）
          if (id.includes('element-plus') || id.includes('@element-plus')) return 'element-plus'
          // Vue 核心运行时单独成包，保证跨页面共享缓存
          if (id.includes('vue') || id.includes('@vue')) return 'vue-vendor'
          // 状态管理与网络层单独成包
          if (id.includes('pinia') || id.includes('axios')) return 'store-vendor'
          // 其余第三方依赖统一放进 vendor
          return 'vendor'
        },
      },
    },
  },
})
