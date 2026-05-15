/// <reference types="vitest" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/v2/__tests__/setup.ts'],
    include: ['src/v2/__tests__/**/*.test.{ts,tsx}'],
    css: false,
  },
});
