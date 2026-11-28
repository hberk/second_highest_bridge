import { defineConfig, loadEnv, type Plugin } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';
import { fileURLToPath } from 'node:url';

// The solved deal library is shared with the Python app, so it is imported
// from the repository root rather than copied. (The stylesheet used to be
// too; table.css is now a ported copy.)
const root = fileURLToPath(new URL('..', import.meta.url));

/** The page may open a socket to the table server (the Worker at
 *  bridge.second-highest.workers.dev), and only to it. */
function tablePage(socketOrigin: string): Plugin {
  return {
    name: 'table-page',
    transformIndexHtml(html) {
      const out = html.replace("connect-src 'self';", `connect-src 'self' ${socketOrigin};`);
      if (!out.includes(socketOrigin)) {
        throw new Error('table-page: index.html no longer matches what the build rewrites');
      }
      return out;
    },
  };
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_');
  return {
    // Relative asset paths: the same build works at any address or sub-path.
    base: './',
    plugins: [svelte(), tablePage(env.VITE_TABLE_SOCKET_ORIGIN || 'wss://bridge.second-highest.workers.dev')],
    // The double dummy solver: a plain asset (fetched by the worker, inlined
    // for dd.test.ts), never Vite's own WebAssembly import.
    assetsInclude: ['**/*.wasm'],
    resolve: { alias: { $root: root } },
    build: { outDir: 'dist' },
    server: {
      fs: { allow: [root] },
      // `npm run dev`: the tables go to a table server on this machine
      // (`npm run dev` in server/).
      proxy: { '/tables': { target: 'http://localhost:8787', ws: true } },
    },
    test: { include: ['src/**/*.test.ts'], testTimeout: 60000 },
  };
});
