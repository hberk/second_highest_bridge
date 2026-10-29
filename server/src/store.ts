// Where tables are kept between restarts: one SQLite file (node:sqlite, in
// WAL mode). A table is its meta (players, seats, host...) as JSON, its
// boards' deals, and the actions made on each board, appended one row at a
// time. Loading a table replays nothing here: the core derives a board from
// its deal and actions.
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
        primary key (table_id, board_num, seq)
      ) without rowid;
    `);
  }

  close(): void {
    this.db.close();
  }

  exists(id: string): boolean {
    return !!this.db.prepare('select 1 from tables where id = ?').get(id);
  }

  /** Every write for one change, in one transaction. */
  save(s: TableState, now: number, newBoard: boolean, actionsFrom: number, record: HistoryRecord | null): void {
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
        const add = this.db.prepare('insert into events (table_id, board_num, seq, action) values (?, ?, ?, ?)');
        for (let i = actionsFrom; i < board.actions.length; i++) {
          add.run(id, board.num, i, JSON.stringify(board.actions[i]));
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

  /** Tables nobody has touched since `before`, deleted; `keep` (tables with
   *  someone connected now) never are. */
  expire(before: number, keep: Set<string>): string[] {
    const ids = (this.db.prepare('select id from tables where last_active < ?').all(before) as { id: string }[])
      .map((r) => r.id).filter((id) => !keep.has(id));
    for (const id of ids) {
      this.db.prepare('delete from events where table_id = ?').run(id);
      this.db.prepare('delete from boards where table_id = ?').run(id);
      this.db.prepare('delete from tables where id = ?').run(id);
    }
    return ids;
  }
}
