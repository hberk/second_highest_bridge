import { defineConfig } from 'vitest/config';

// The tests start the Worker in workerd (wrangler's local runtime) and talk
// to it over real sockets, as the Node server's tests do (../test).
export default defineConfig({
  // As in ../vitest.config.ts: frontend/tsconfig.json extends a package only
  // frontend/node_modules has; the transform needs no tsconfig.
  oxc: { tsconfig: false },
  test: { include: ['test/**/*.test.ts'], testTimeout: 120_000, hookTimeout: 120_000, fileParallelism: false },
});
