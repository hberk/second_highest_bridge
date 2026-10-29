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
import { DatabaseSync } from 'node:sqlite';
import type { Action, Board, TableState } from '../../frontend/src/lib/table/core';
import type { HistoryRecord } from '../../frontend/src/lib/saves';

type Meta = Omit<TableState, 'id' | 'board'>;

export class Store {
  private db: DatabaseSync;

  constructor(path: string) {
    this.db = new DatabaseSync(path);
    this.db.exec(`
      pragma journal_mode = wal;
      pragma synchronous = normal;
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
      create index if not exists log_by_table on log (table_id, ts);
      create index if not exists log_by_time on log (ts);
    `);
    // Databases from before the log: the two columns, empty for old actions.
    const cols = (this.db.prepare('pragma table_info(events)').all() as { name: string }[]).map((c) => c.name);
    if (!cols.includes('ts')) this.db.exec('alter table events add column ts integer');
    if (!cols.includes('ms')) this.db.exec('alter table events add column ms real');
  }

  close(): void {
    this.db.close();
  }

  exists(id: string): boolean {
    return !!this.db.prepare('select 1 from tables where id = ?').get(id);
  }

  /** Every write for one change, in one transaction. The new actions were
   *  made at `now`; `robotMs` is the thinking time of the last, a robot's. */
  save(s: TableState, now: number, newBoard: boolean, actionsFrom: number, record: HistoryRecord | null,
       robotMs: number | null = null): void {
    const { id, board, ...meta } = s;
    this.db.exec('begin');
    try {
      this.db.prepare(`insert into tables (id, created_at, last_active, meta) values (?, ?, ?, ?)
        on conflict (id) do update set last_active = excluded.last_active, meta = excluded.meta`)
        .run(id, s.createdAt, now, JSON.stringify(meta satisfies Meta));
      if (board) {
        if (newBoard) {
          const { actions: _, ...deal } = board;
          this.db.prepare('insert or replace into boards (table_id, board_num, board) values (?, ?, ?)')
            .run(id, board.num, JSON.stringify(deal));
        }
        const add = this.db.prepare('insert into events (table_id, board_num, seq, action, ts, ms) values (?, ?, ?, ?, ?, ?)');
        const last = board.actions.length - 1;
        for (let i = actionsFrom; i <= last; i++) {
          const a = board.actions[i];
          add.run(id, board.num, i, JSON.stringify(a), now, i === last && !a.human ? robotMs : null);
        }
        if (record) {
          this.db.prepare('update boards set record = ? where table_id = ? and board_num = ?')
            .run(JSON.stringify(record), id, board.num);
        }
      }
      this.db.exec('commit');
    } catch (e) {
      this.db.exec('rollback');
      throw e;
    }
  }

  /** One line of a table's log. `detail` is stored as JSON. */
  log(tableId: string, ts: number, kind: string, detail: Record<string, unknown> | null = null,
      boardNum: number | null = null, playerId: string | null = null): void {
    this.db.prepare('insert into log (ts, table_id, board_num, player_id, kind, detail) values (?, ?, ?, ?, ?, ?)')
      .run(ts, tableId, boardNum, playerId, kind, detail ? JSON.stringify(detail) : null);
  }

  load(id: string): TableState | null {
    const row = this.db.prepare('select meta from tables where id = ?').get(id) as { meta: string } | undefined;
    if (!row) return null;
    const meta = JSON.parse(row.meta) as Meta;
    let board: Board | null = null;
    const b = this.db.prepare('select board from boards where table_id = ? and board_num = ?')
      .get(id, meta.boardNum) as { board: string } | undefined;
    if (b) {
      const actions = (this.db.prepare('select action from events where table_id = ? and board_num = ? order by seq')
        .all(id, meta.boardNum) as { action: string }[]).map((r) => JSON.parse(r.action) as Action);
      board = { ...(JSON.parse(b.board) as Omit<Board, 'actions'>), actions };
    }
    return { id, board, ...meta };
  }

  /** Tables nobody has touched since `before` close; `keep` (tables with
   *  someone connected now) never do. A closed table's row (its seats and
   *  token hashes) goes; its boards, actions and log stay, with a last log
   *  line naming who sat where. */
  expire(before: number, keep: Set<string>, now: number): string[] {
    const rows = (this.db.prepare('select id, meta from tables where last_active < ?').all(before) as { id: string; meta: string }[])
      .filter((r) => !keep.has(r.id));
    for (const r of rows) {
      const meta = JSON.parse(r.meta) as Meta;
      this.db.exec('begin');
      try {
        this.log(r.id, now, 'closed', {
          players: meta.players.map((p) => ({ id: p.id, name: p.name, seat: p.seat })), boards: meta.boardNum,
        });
        this.db.prepare('delete from tables where id = ?').run(r.id);
        this.db.exec('commit');
      } catch (e) {
        this.db.exec('rollback');
        throw e;
      }
    }
    return rows.map((r) => r.id);
  }
}
