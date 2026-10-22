// Build research/solver-rs/wasm for the browser and copy the .wasm beside
// src/lib/dd/solver.ts. Needs Rust with the wasm32-unknown-unknown target
// (rustup target add wasm32-unknown-unknown); without it this fails, and so
// do dev, test and build: the History replayer has no fallback solver.
import { execFileSync } from 'node:child_process';
import { copyFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const crate = fileURLToPath(new URL('../../research/solver-rs/wasm/', import.meta.url));
const target = 'wasm32-unknown-unknown';
try {
  execFileSync('cargo', ['build', '--release', '--target', target, '--manifest-path', `${crate}Cargo.toml`],
    { stdio: 'inherit' });
} catch {
  console.error(`\nCould not build the double dummy solver. Install Rust (https://rustup.rs), then:\n` +
    `  rustup target add ${target}\n`);
  process.exit(1);
}
copyFileSync(`${crate}target/${target}/release/solver_wasm.wasm`,
  fileURLToPath(new URL('../src/lib/dd/solver.wasm', import.meta.url)));
