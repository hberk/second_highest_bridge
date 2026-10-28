// Starts the table server from the environment (bridge.service sets it):
//   PORT             8787
//   BRIDGE_DB        /var/lib/bridge/bridge.db
//   PUBLIC_DIR       the beta build, /opt/bridge/public
//   ALLOWED_ORIGINS  https://bridge.ettamei.com (comma-separated)
//   TRUSTED_PROXY    Caddy's address, 192.168.169.211
import { startServer } from './server';

const env = process.env;
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
