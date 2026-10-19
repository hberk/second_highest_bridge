import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';
import { fileURLToPath } from 'node:url';

// The solved deal library is shared with the Python app, so it is imported
// from the repository root rather than copied. (The stylesheet used to be
// too; table.css is now a ported copy.)
const root = fileURLToPath(new URL('..', import.meta.url));

export default defineConfig({
  // Relative asset paths: GitHub Pages serves the site from a sub-path
  // (/second_highest_bridge/), and the same build works at any other address.
  base: './',
  plugins: [svelte()],
  resolve: { alias: { $root: root } },
  server: { fs: { allow: [root] } },
  test: { include: ['src/**/*.test.ts'], testTimeout: 60000 },
});
