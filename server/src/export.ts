// The game log, read back out (MULTIPLAYER_PLAN.md, "Game logs"). Run on the
// container beside the live server; the database is opened read-only, so it
// never blocks or changes a table.
//
//   node server.js export [--db <path>] [--since 7d|36h|2026-10-28] [--table <id>] [--lin]
//
// JSON by default: every table with activity in the window, each board with
// its deal, its actions (when, and a robot's thinking time) and its LIN, the
// table's log (joins, seats, drops, refusals, reports, errors), and summary
// stats. `--lin` prints the finished boards alone, one LIN line each, for the
// History screen's import.
import { DatabaseSync } from 'node:sqlite';
import type { Seat } from '../../frontend/src/lib/engine/card';
import type { Action, Board } from '../../frontend/src/lib/table/core';
import type { HistoryRecord } from '../../frontend/src/lib/saves';
import { toLin } from '../../frontend/src/lib/lin';

export interface ExportOptions { since: number; table: string | null; lin: boolean; db?: string }

const iso = (ms: number | null) => (ms === null ? null : new Date(ms).toISOString());

/** "7d", "36h", "90m", or a date; the default is the last week. */
export function parseSince(text: string | undefined, now: number): number {
  if (!text) return now - 7 * 864e5;
  const m = /^(\d+)([dhm])$/.exec(text);
  if (m) return now - Number(m[1]) * { d: 864e5, h: 36e5, m: 6e4 }[m[2] as 'd' | 'h' | 'm'];
  const t = Date.parse(text);
  if (Number.isNaN(t)) throw new Error(`--since ${text}: not 7d, 36h, 90m or a date`);
  return t;
}

export function parseArgs(argv: string[], now: number): ExportOptions {
  const opt = (name: string) => {
    const i = argv.indexOf(name);
    return i >= 0 ? argv[i + 1] : undefined;
  };
  return { since: parseSince(opt('--since'), now), table: opt('--table') ?? null, lin: argv.includes('--lin'), db: opt('--db') };
}

interface LogRow { ts: number; table_id: string; board_num: number | null; player_id: string | null; kind: string; detail: string | null }
interface EventRow { board_num: number; seq: number; action: string; ts: number | null; ms: number | null }

const q = (xs: number[], p: number) => {
  if (!xs.length) return null;
  const s = [...xs].sort((a, b) => a - b);
  return s[Math.min(s.length - 1, Math.floor(p * s.length))];
};
const spread = (xs: number[]) => ({ n: xs.length, median: q(xs, 0.5), p95: q(xs, 0.95), max: xs.length ? Math.max(...xs) : null });

export function exportLogs(dbPath: string, o: ExportOptions): { text: string } {
  const db = new DatabaseSync(dbPath, { readOnly: true });
  try {
    const ids = o.table ? [o.table] : (db.prepare(`
      select table_id from log where ts >= ? union select table_id from events where ts >= ?`)
      .all(o.since, o.since) as { table_id: string }[]).map((r) => r.table_id);

    const robotMs: number[] = [];
    const humanMs: number[] = [];
    const counts: Record<string, number> = {};
    const refused: Record<string, number> = {};
    const people = new Set<string>();
    const linLines: string[] = [];
    let boardsFinished = 0;

    const tables = ids.map((id) => {
      const log = (db.prepare('select * from log where table_id = ? order by ts, rowid').all(id) as unknown as LogRow[])
        .map((r) => ({ ts: iso(r.ts), board: r.board_num, player: r.player_id, kind: r.kind, detail: r.detail ? JSON.parse(r.detail) : null }));
      for (const l of log) {
        counts[l.kind] = (counts[l.kind] ?? 0) + 1;
        if (l.kind === 'joined' && l.player) people.add(l.player);
        if (l.kind === 'refused') refused[l.detail.code] = (refused[l.detail.code] ?? 0) + 1;
      }
      const names = new Map<number, Partial<Record<Seat, string>>>();
      for (const l of log) {
        if (l.kind === 'dealt' && l.board !== null) {
          names.set(l.board, Object.fromEntries((l.detail.people as { name: string; seat: Seat }[]).map((p) => [p.seat, p.name])));
        }
      }
      const events = db.prepare('select board_num, seq, action, ts, ms from events where table_id = ? order by board_num, seq')
        .all(id) as unknown as EventRow[];
      const boardRows = db.prepare('select board_num, board, record from boards where table_id = ? order by board_num')
        .all(id) as { board_num: number; board: string; record: string | null }[];
      const boards = boardRows.map((row) => {
        const deal = JSON.parse(row.board) as Omit<Board, 'actions'>;
        const record = row.record ? (JSON.parse(row.record) as HistoryRecord) : null;
        const mine = events.filter((e) => e.board_num === row.board_num);
        const actions = mine.map((e, i) => {
          const a = JSON.parse(e.action) as Action;
          const prev = mine[i - 1];
          // A person's time to act: from the action before theirs.
          if (a.human && prev?.ts && e.ts) humanMs.push(e.ts - prev.ts);
          if (!a.human && e.ms !== null) robotMs.push(e.ms);
          return { seq: e.seq, ts: iso(e.ts), ms: e.ms, ...a };
        });
        if (record) {
          boardsFinished++;
          const lin = toLin({ ...record, board_num: row.board_num }, names.get(row.board_num));
          linLines.push(lin);
          return { num: row.board_num, dealer: deal.dealer, vulnerability: deal.vulnerability, hands: deal.hands,
            started: actions[0]?.ts ?? null, ended: actions.at(-1)?.ts ?? null,
            contract: record.contract, result: record.result, tricks: record.tricks_taken, lin, actions };
        }
        return { num: row.board_num, dealer: deal.dealer, vulnerability: deal.vulnerability, hands: deal.hands,
          started: actions[0]?.ts ?? null, ended: null, unfinished: true, actions };
      });
      const open = db.prepare('select created_at, last_active, meta from tables where id = ?').get(id) as
        { created_at: number; last_active: number; meta: string } | undefined;
      const players = open
        ? (JSON.parse(open.meta).players as { id: string; name: string; seat: Seat | null }[]).map(({ id: pid, name, seat }) => ({ id: pid, name, seat }))
        : log.findLast((l) => l.kind === 'closed')?.detail.players ?? [];
      return {
        id, open: !!open, created: log.find((l) => l.kind === 'created')?.ts ?? iso(open?.created_at ?? null),
        lastActive: iso(open?.last_active ?? null), players, boards, log,
      };
    });

    if (o.lin) return { text: linLines.join('\n') + (linLines.length ? '\n' : '') };
    const stats = {
      tables: tables.length, boardsFinished, people: people.size,
      robotMs: spread(robotMs), humanSeconds: spread(humanMs.map((x) => Math.round(x / 100) / 10)),
      reports: counts.report ?? 0, clientErrors: counts.client_error ?? 0, robotErrors: counts.robot_error ?? 0,
      refused, kinds: counts,
    };
    return { text: JSON.stringify({ exported: iso(Date.now()), since: iso(o.since), stats, tables }, null, 1) + '\n' };
  } finally {
    db.close();
  }
}
