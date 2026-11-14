/// <reference types="vitest/config" />
import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

// DOPPELGRUND_BASE: sub-path for GitHub Pages (e.g. "/DoppelGrund/"); defaults to "/".
const base = process.env.DOPPELGRUND_BASE ?? '/';

export default defineConfig({
  base,
  plugins: [vue()],
  worker: { format: 'es' },
  build: { target: 'es2022', chunkSizeWarningLimit: 2500 },
  test: {
    environment: 'node',
    include: ['tests/**/*.test.ts'],
  },
});
