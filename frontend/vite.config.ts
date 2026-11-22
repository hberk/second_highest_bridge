import { defineConfig, loadEnv, type Plugin } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';
import { fileURLToPath } from 'node:url';

// The solved deal library is shared with the Python app, so it is imported
// from the repository root rather than copied. (The stylesheet used to be
// too; table.css is now a ported copy.)
const root = fileURLToPath(new URL('..', import.meta.url));

/** The beta build (`--mode beta`, the deployed site, served by the Worker at
 *  bridge.second-highest.workers.dev) may open a socket to that server, and
 *  only to it; it doesn't count page views. The plain build is untouched. */
function betaPage(socketOrigin: string): Plugin {
  return {
    name: 'beta-page',
    transformIndexHtml(html) {
      const out = html
        .replace(" https://static.cloudflareinsights.com;", ';')
        .replace("connect-src 'self' https://cloudflareinsights.com;", `connect-src 'self' ${socketOrigin};`)
        .replace(/\s*<!-- Cloudflare Web Analytics:[\s\S]*?<\/script>/, '');
      if (/https:\/\/[a-z.]*cloudflareinsights\.com/.test(out) || !out.includes(socketOrigin)) {
        throw new Error('beta-page: index.html no longer matches what the beta build rewrites');
      }
      return out;
    },
  };
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_');
  const beta = env.VITE_TABLES === '1';
  return {
    // Relative asset paths: the same build works at any address or sub-path.
    base: './',
    plugins: [svelte(), ...(beta ? [betaPage(env.VITE_TABLE_SOCKET_ORIGIN || 'wss://bridge.second-highest.workers.dev')] : [])],
    // The double dummy solver: a plain asset (fetched by the worker, inlined
    // for dd.test.ts), never Vite's own WebAssembly import.
    assetsInclude: ['**/*.wasm'],
    resolve: { alias: { $root: root } },
    build: { outDir: beta ? 'dist-beta' : 'dist' },
    server: {
      fs: { allow: [root] },
      // `npm run dev:beta`: the tables go to a table server on this machine
      // (`npm run dev` in server/).
      proxy: beta ? { '/tables': { target: 'http://localhost:8787', ws: true } } : undefined,
    },
    test: { include: ['src/**/*.test.ts'], testTimeout: 60000 },
  };
});
