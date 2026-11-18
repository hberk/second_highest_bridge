// Where tables are kept between restarts: one SQLite file (node:sqlite, in
// WAL mode). A table is its meta (players, seats, host...) as JSON, its
// boards' deals, and the actions made on each board, appended one row at a
// time. Loading a table replays nothing here: the core derives a board from
// its deal and actions.
//
// It is also the game log (MULTIPLAYER_PLAN.md, "Game logs"): every action
// carries when it was made and, for a robot's, how long it thought; `log`
// holds what happened around the play (joins, seats, drops, refusals,
// reports, errors). A table that expires loses its seats and tokens, never
// its boards or its log.
//
// The SQL goes through `Sql` (sql.ts): node:sqlite on the homelab, a Durable
// Object's storage on Cloudflare. This file imports neither.
import type { Row, Sql } from './sql';
import type { Action, Board, TableState } from '../../frontend/src/lib/table/core';
import type { HistoryRecord } from '../../frontend/src/lib/saves';

type Meta = Omit<TableState, 'id' | 'board'>;

export class Store {
  /** `indexes`: the log's two indexes, for reading one table's log or a
   *  time window out of a file of many tables. A Durable Object holds one
   *  table and is never queried that way, and every index costs a row
   *  written per log line, so it goes without. */
  constructor(private db: Sql, { indexes = true }: { indexes?: boolean } = {}) {
    this.db.exec(`
      create table if not exists tables (
        id text primary key, created_at integer not null, last_active integer not null, meta text not null
      ) without rowid;
      create table if not exists boards (
        table_id text not null, board_num integer not null, board text not null, record text,
        primary key (table_id, board_num)
      ) without rowid;
      create table if not exists events (
        table_id text not null, board_num integer not null, seq integer not null, action text not null,
        ts integer, ms real,
        primary key (table_id, board_num, seq)
      ) without rowid;
      create table if not exists log (
        ts integer not null, table_id text not null, board_num integer, player_id text, kind text not null,
        detail text
      );
    `);
    if (indexes) {
      this.db.exec(`
        create index if not exists log_by_table on log (table_id, ts);
        create index if not exists log_by_time on log (ts);
      `);
    }
    // Databases from before the log: the two columns, empty for old actions.
    const cols = this.db.all('pragma table_info(events)').map((c) => c.name);
    if (!cols.includes('ts')) this.db.exec('alter table events add column ts integer');
    if (!cols.includes('ms')) this.db.exec('alter table events add column ms real');
  }

  private get(sql: string, ...args: (string | number | null)[]): Row | undefined {
    return this.db.all(sql, ...args)[0];
  }

  close(): void {
    this.db.close();
  }

  exists(id: string): boolean {
    return !!this.get('select 1 from tables where id = ?', id);
  }

  /** Every write for one change, in one transaction. The new actions were
   *  made at `now`; `robotMs` is the thinking time of the last, a robot's. */
  save(s: TableState, now: number, newBoard: boolean, actionsFrom: number, record: HistoryRecord | null,
       robotMs: number | null = null): void {
    const { id, board, ...meta } = s;
    this.db.transaction(() => {
      this.db.run(`insert into tables (id, created_at, last_active, meta) values (?, ?, ?, ?)
        on conflict (id) do update set last_active = excluded.last_active, meta = excluded.meta`,
        id, s.createdAt, now, JSON.stringify(meta satisfies Meta));
      if (!board) return;
      if (newBoard) {
        const { actions: _, ...deal } = board;
        this.db.run('insert or replace into boards (table_id, board_num, board) values (?, ?, ?)',
          id, board.num, JSON.stringify(deal));
      }
      const last = board.actions.length - 1;
      for (let i = actionsFrom; i <= last; i++) {
        const a = board.actions[i];
        this.db.run('insert into events (table_id, board_num, seq, action, ts, ms) values (?, ?, ?, ?, ?, ?)',
          id, board.num, i, JSON.stringify(a), now, i === last && !a.human ? robotMs : null);
      }
      if (record) {
        this.db.run('update boards set record = ? where table_id = ? and board_num = ?',
          JSON.stringify(record), id, board.num);
      }
    });
  }

  /** One line of a table's log. `detail` is stored as JSON. */
  log(tableId: string, ts: number, kind: string, detail: Record<string, unknown> | null = null,
      boardNum: number | null = null, playerId: string | null = null): void {
    this.db.run('insert into log (ts, table_id, board_num, player_id, kind, detail) values (?, ?, ?, ?, ?, ?)',
      ts, tableId, boardNum, playerId, kind, detail ? JSON.stringify(detail) : null);
  }

  load(id: string): TableState | null {
    const row = this.get('select meta from tables where id = ?', id) as { meta: string } | undefined;
    if (!row) return null;
    const meta = JSON.parse(row.meta) as Meta;
    let board: Board | null = null;
    const b = this.get('select board from boards where table_id = ? and board_num = ?', id, meta.boardNum) as
      { board: string } | undefined;
    if (b) {
      const actions = (this.db.all('select action from events where table_id = ? and board_num = ? order by seq',
        id, meta.boardNum) as { action: string }[]).map((r) => JSON.parse(r.action) as Action);
      board = { ...(JSON.parse(b.board) as Omit<Board, 'actions'>), actions };
    }
    return { id, board, ...meta };
  }

  /** Tables nobody has touched since `before` close; `keep` (tables with
   *  someone connected now) never do. A closed table's row (its seats and
   *  token hashes) goes; its boards, actions and log stay, with a last log
   *  line naming who sat where. */
  expire(before: number, keep: Set<string>, now: number): string[] {
    const rows = (this.db.all('select id, meta from tables where last_active < ?', before) as { id: string; meta: string }[])
      .filter((r) => !keep.has(r.id));
    for (const r of rows) {
      const meta = JSON.parse(r.meta) as Meta;
      this.db.transaction(() => {
        this.log(r.id, now, 'closed', {
          players: meta.players.map((p) => ({ id: p.id, name: p.name, seat: p.seat })), boards: meta.boardNum,
        });
        this.db.run('delete from tables where id = ?', r.id);
      });
    }
    return rows.map((r) => r.id);
  }

  /** When the table was last changed, or null once it has closed. */
  lastActive(id: string): number | null {
    const row = this.get('select last_active from tables where id = ?', id);
    return row ? Number(row.last_active) : null;
  }
}
