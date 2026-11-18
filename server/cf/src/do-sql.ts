// The Store's SQL (../../src/sql.ts) on a Durable Object's own SQLite. Every
// statement here runs synchronously; `transactionSync` makes a change all or
// none, as node:sqlite's begin/commit does on the homelab.
//
// It also counts the rows written, which is the Free plan's binding limit
// (100,000 a day, MULTIPLAYER_PLAN.md "The Free plan's budget").
import type { Row, Sql, SqlValue } from '../../src/sql';

export interface CountingSql extends Sql {
  readonly rowsWritten: number;
}

export function doSql(storage: DurableObjectStorage): CountingSql {
  let written = 0;
  const exec = (q: string, args: SqlValue[]) => {
    const cursor = storage.sql.exec(q, ...args);
    const rows = cursor.toArray() as Row[];
    written += cursor.rowsWritten;
    return rows;
  };
  return {
    get rowsWritten() { return written; },
    run: (q, ...a) => { exec(q, a); },
    all: (q, ...a) => exec(q, a),
    exec: (script) => { exec(script, []); },
    transaction: (fn) => storage.transactionSync(fn),
    close: () => {},
  };
}
