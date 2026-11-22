// The Store's SQL (../../src/sql.ts) on a Durable Object's own SQLite. Every
// statement here runs synchronously; `transactionSync` makes a change all or
// none, as node:sqlite's begin/commit does in the Node server.
//
// It also counts the rows written, which is the Free plan's binding limit
// (100,000 a day, MULTIPLAYER_PLAN.md "The Free plan's budget").
import type { Row, Sql, SqlValue } from '../../src/sql';

export class DoSql implements Sql {
  rowsWritten = 0;
  /** Development only: every write from now on throws this, as a spent
   *  daily allowance does (resting.ts). */
  failWrites: string | null = null;

  constructor(private storage: DurableObjectStorage) {}

  private go(q: string, args: SqlValue[]): Row[] {
    if (this.failWrites && !/^\s*(select|pragma)/i.test(q)) throw new Error(this.failWrites);
    const cursor = this.storage.sql.exec(q, ...args);
    const rows = cursor.toArray() as Row[];
    this.rowsWritten += cursor.rowsWritten;
    return rows;
  }

  run(q: string, ...a: SqlValue[]): void { this.go(q, a); }
  all(q: string, ...a: SqlValue[]): Row[] { return this.go(q, a); }
  exec(script: string): void { this.go(script, []); }
  transaction<T>(fn: () => T): T { return this.storage.transactionSync(fn); }
  close(): void {}
}
