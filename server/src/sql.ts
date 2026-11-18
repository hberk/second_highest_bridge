// The few SQL calls the Store makes, so the same Store runs on two databases:
// node:sqlite on the homelab (one file for every table), and a Durable
// Object's own SQLite on Cloudflare (one database per table, cf/). Neither
// adapter knows the schema; the Store does.
import { DatabaseSync, type SQLInputValue } from 'node:sqlite';

export type SqlValue = string | number | null;
export type Row = Record<string, SqlValue>;

export interface Sql {
  /** A statement that returns nothing. */
  run(sql: string, ...args: SqlValue[]): void;
  /** Every row a query returns. */
  all(sql: string, ...args: SqlValue[]): Row[];
  /** Several statements, no arguments (the schema). */
  exec(script: string): void;
  /** `fn`'s writes, all or none. */
  transaction<T>(fn: () => T): T;
  close(): void;
}

/** node:sqlite in WAL mode: the homelab's one file. */
export function nodeSql(path: string): Sql {
  const db = new DatabaseSync(path);
  db.exec('pragma journal_mode = wal; pragma synchronous = normal;');
  const args = (a: SqlValue[]) => a as SQLInputValue[];
  return {
    run: (sql, ...a) => { db.prepare(sql).run(...args(a)); },
    all: (sql, ...a) => db.prepare(sql).all(...args(a)) as Row[],
    exec: (script) => db.exec(script),
    transaction: (fn) => {
      db.exec('begin');
      try {
        const out = fn();
        db.exec('commit');
        return out;
      } catch (e) {
        db.exec('rollback');
        throw e;
      }
    },
    close: () => db.close(),
  };
}
