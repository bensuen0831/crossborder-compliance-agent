import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173, strictPort: true,
    proxy: Object.fromEntries(['/api', '/health', '/m0-demo'].map((path) => [path, {
      target: process.env.M0_API_TARGET ?? 'http://127.0.0.1:8010',
      changeOrigin: false,
    }])),
  },
  test: {
    environment: 'jsdom', setupFiles: ['./src/test/setup.ts'],
    // Enterprise component assertions retain a bounded deadline on shared CI CPUs.
    testTimeout: 15_000,
    include: ['src/**/*.test.{ts,tsx}'], css: true,
  },
  build: {
    rollupOptions: { output: { manualChunks: {
      enterprise: ['antd', '@ant-design/icons'],
      contracts: ['ajv/dist/2020', 'ajv-formats'],
    } } },
  },
});
