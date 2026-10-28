// Bundles the server, the frontend's engine and table core included, into
// one dist/server.js with no npm dependencies left to install: the homelab
// container only needs Node 24. `node build.mjs bench` builds the robot
// benchmark instead.
import { build } from 'esbuild';
import { readFileSync } from 'node:fs';

const bench = process.argv[2] === 'bench';
await build({
  entryPoints: [bench ? 'src/bench.ts' : 'src/main.ts'],
  outfile: bench ? 'dist/bench.js' : 'dist/server.js',
  bundle: true,
  platform: 'node',
  format: 'esm',
  target: 'node24',
  sourcemap: true,
  legalComments: 'none',
  // This tsconfig for every file, frontend/ included: frontend/tsconfig.json
  // extends a package only frontend/node_modules has, so the bundle would
  // differ between here and CI, where only server/ is installed.
  tsconfig: 'tsconfig.json',
  // ws has optional native helpers it does without.
  external: ['bufferutil', 'utf-8-validate'],
  banner: { js: "import { createRequire } from 'node:module'; const require = createRequire(import.meta.url);" },
});

// The server must never carry the challenge library (engine/challenge.ts
// imports it through a Vite alias): the core imports only types from there.
if (!bench) {
  const out = readFileSync('dist/server.js', 'utf8');
  if (out.includes('solved_deals') || out.includes('$root')) {
    console.error('dist/server.js pulls in the challenge deal library; the server must not import challenge.ts');
    process.exit(1);
  }
}
console.log(`built ${bench ? 'dist/bench.js' : 'dist/server.js'}`);
