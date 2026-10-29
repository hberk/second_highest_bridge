// Starts the table server from the environment (bridge.service sets it):
//   PORT             8787
//   BRIDGE_DB        /var/lib/bridge/bridge.db
//   PUBLIC_DIR       the beta build, /opt/bridge/public
//   ALLOWED_ORIGINS  https://bridge.ettamei.com (comma-separated)
//   TRUSTED_PROXY    Caddy's address, 192.168.169.211
//   BRIDGE_DEV=1     on a development machine only: allows the two above unset
import { log, startServer } from './server';

const env = process.env;
const dev = env.BRIDGE_DEV === '1';
// Without TRUSTED_PROXY every player behind Caddy has Caddy's address, and
// the per-address limits become one limit for the whole internet. Without
// PUBLIC_DIR there is no site. Both fail silently, so refuse to start.
for (const name of ['TRUSTED_PROXY', 'PUBLIC_DIR']) {
  if (!env[name] && !dev) {
    console.error(`${name} is not set (set BRIDGE_DEV=1 to run without it on a development machine)`);
    process.exit(2);
  }
}

// A last resort: every handler catches its own errors, so one reaching here
// is a bug. Log it and keep the other tables running.
process.on('uncaughtException', (e) => log('uncaught', e));
process.on('unhandledRejection', (e) => log('unhandled rejection', e));

const server = await startServer({
  port: Number(env.PORT ?? 8787),
  host: env.HOST ?? '0.0.0.0',
  dbPath: env.BRIDGE_DB ?? './bridge.db',
  publicDir: env.PUBLIC_DIR,
  allowedOrigins: (env.ALLOWED_ORIGINS ?? 'https://bridge.ettamei.com').split(',').map((s) => s.trim()).filter(Boolean),
  trustedProxy: env.TRUSTED_PROXY,
});
console.log(`bridge table server on :${server.port}`);

let stopping = false;
for (const signal of ['SIGTERM', 'SIGINT'] as const) {
  process.on(signal, () => {
    if (stopping) return;
    stopping = true;
    // Sockets close with 1012 (restarting): clients reconnect and resume.
    server.close().then(() => process.exit(0));
    setTimeout(() => process.exit(0), 5000).unref();
  });
}
