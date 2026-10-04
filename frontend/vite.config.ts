import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';
import { fileURLToPath } from 'node:url';

// The solved deal library and the stylesheet are shared with the Python app,
// so they are imported from the repository root rather than copied.
const root = fileURLToPath(new URL('..', import.meta.url));

export default defineConfig({
  plugins: [svelte()],
  resolve: { alias: { $root: root } },
  server: { fs: { allow: [root] } },
  test: { include: ['src/**/*.test.ts'], testTimeout: 60000 },
});
