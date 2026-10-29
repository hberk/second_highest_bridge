// The homelab's pull deployer: run by bridge-pull.timer as `builder` in
// LXC 213, it installs the newest release that CI built from main
// (docs/MULTIPLAYER_PLAN.md, "Deploying from main"). The homelab reaches
// out; GitHub holds no key to it.
//
// A release is installed only if its attestation proves it was built by
// .github/workflows/pages.yml on refs/heads/main of the repository, from the
// commit the release names, on a GitHub-hosted runner. The check runs offline
// against the bundle CI attaches, so no GitHub login is needed. Then the same
// swap as deploy.sh, a restart, and /healthz; a release that fails is put
// back and never retried.
//
// Plain Node 24 and the gh CLI, no packages. Installed root-owned in
// /opt/bridge-pull so the account it runs as cannot rewrite its own checks.
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, appendFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const REPO = process.env.BRIDGE_REPO ?? 'hberk/second_highest_bridge';
const DIR = process.env.BRIDGE_DIR ?? '/opt/bridge';
const IDENTITY = `https://github.com/${REPO}/.github/workflows/pages.yml@refs/heads/main`;
const TAG = /^bridge-[0-9a-f]{7,40}$/;
const API = process.env.BRIDGE_API ?? 'https://api.github.com'; // a test points this at a fake
const headers = { 'user-agent': 'bridge-pull', accept: 'application/vnd.github+json' };

const log = (...a) => console.log(...a);
const run = (cmd, args, opts = {}) => execFileSync(cmd, args, { stdio: ['ignore', 'pipe', 'pipe'], ...opts }).toString();
const read = (f) => (existsSync(f) ? readFileSync(f, 'utf8').trim() : '');

async function get(url) {
  const r = await fetch(url, { headers, redirect: 'follow' });
  if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
  return r;
}

async function healthy() {
  for (let i = 0; i < 20; i++) {
    try {
      const r = await fetch('http://127.0.0.1:8787/healthz');
      if ((await r.json()).ok === true) return true;
    } catch { /* not up yet */ }
    await new Promise((res) => setTimeout(res, 1000));
  }
  return false;
}

const restart = () => run('sudo', ['/usr/bin/systemctl', 'restart', 'bridge.service']);

async function main() {
  const hold = read(join(DIR, '.hold'));
  if (hold) return log(`held: ${hold} (rm ${DIR}/.hold to resume deploying from main)`);

  const releases = await (await get(`${API}/repos/${REPO}/releases?per_page=20`)).json();
  const latest = releases
    .filter((r) => !r.draft && TAG.test(r.tag_name) && /^[0-9a-f]{40}$/.test(r.target_commitish))
    .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at))[0];
  if (!latest) return log('no bridge release yet');
  const sha = latest.target_commitish;
  if (read(join(DIR, 'VERSION')) === sha) return; // up to date: say nothing every five minutes
  if (read(join(DIR, '.failed')).split('\n').includes(sha)) return log(`skipping ${latest.tag_name}: it failed before`);

  const asset = (name) => {
    const a = latest.assets.find((x) => x.name === name);
    if (!a) throw new Error(`${latest.tag_name} has no ${name}`);
    return a;
  };
  const tarball = asset('bridge.tar.gz');
  const bundle = asset('bridge.sigstore.jsonl');

  const work = mkdtempSync(join(tmpdir(), 'bridge-pull-'));
  try {
    const tgz = join(work, 'bridge.tar.gz');
    const body = Buffer.from(await (await get(tarball.browser_download_url)).arrayBuffer());
    writeFileSync(tgz, body);
    writeFileSync(join(work, 'bundle.jsonl'), Buffer.from(await (await get(bundle.browser_download_url)).arrayBuffer()));
    const digest = createHash('sha256').update(body).digest('hex');
    if (tarball.digest && tarball.digest !== `sha256:${digest}`) throw new Error(`${latest.tag_name}: download doesn't match its digest`);

    // Throws (and so refuses the release) unless every condition holds.
    const ghHome = join(work, 'gh');
    mkdirSync(ghHome);
    run('gh', [
      'attestation', 'verify', tgz, '--bundle', join(work, 'bundle.jsonl'),
      '--repo', REPO, '--cert-identity', IDENTITY, '--source-digest', sha, '--deny-self-hosted-runners',
    ], { env: { PATH: process.env.PATH, HOME: ghHome, GH_CONFIG_DIR: ghHome } });

    const stage = join(work, 'stage');
    mkdirSync(stage);
    run('tar', ['-xzmf', tgz, '-C', stage]);
    if (read(join(stage, 'VERSION')) !== sha) throw new Error(`${latest.tag_name}: VERSION inside isn't ${sha}`);
    for (const f of ['server.js', 'public/index.html']) {
      if (!existsSync(join(stage, f))) throw new Error(`${latest.tag_name}: no ${f}`);
    }

    log(`installing ${latest.tag_name} (${sha})`);
    run('sh', ['-ec', `
      cd "$1"
      rm -rf .previous && mkdir .previous
      for f in server.js server.js.map public VERSION; do [ -e "$f" ] && mv "$f" .previous/; done
      mv "$2"/* .`, 'swap', DIR, stage]);
    restart();
    if (await healthy()) return log(`up: ${latest.tag_name}`);

    log(`!! ${latest.tag_name} did not come up; putting the previous version back`);
    appendFileSync(join(DIR, '.failed'), `${sha}\n`);
    run('sh', ['-ec', `
      cd "$1"
      rm -rf server.js server.js.map public VERSION
      mv .previous/* .`, 'rollback', DIR]);
    restart();
    log((await healthy()) ? 'previous version is back up' : '!! the previous version is not answering either');
    process.exitCode = 1;
  } finally {
    rmSync(work, { recursive: true, force: true });
  }
}

main().catch((e) => {
  log(`!! ${e.message}${e.stderr ? `\n${e.stderr}` : ''}`);
  process.exitCode = 1;
});
