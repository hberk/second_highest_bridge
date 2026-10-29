import { defineConfig } from 'vitest/config';

export default defineConfig({
  // The tests import the engine from frontend/, whose tsconfig extends a
  // package only frontend/node_modules has. The server's own tsconfig covers
  // type-checking (`npm run check`); the transform needs no tsconfig.
  oxc: { tsconfig: false },
  test: { include: ['test/**/*.test.ts'], testTimeout: 60000, pool: 'forks' },
});
