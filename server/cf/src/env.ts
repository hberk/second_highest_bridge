import type { Limiter } from './limiter';
import type { TableObject } from './table-object';

export interface Env {
  TABLES: DurableObjectNamespace<TableObject>;
  LIMITER: DurableObjectNamespace<Limiter>;
  ASSETS: Fetcher;
  /** Visitor counts (visits.ts); absent in the tests and `wrangler dev`. */
  VISITS?: AnalyticsEngineDataset;
  /** Shared finished boards (boards.ts); absent only if unbound. */
  BOARDS?: D1Database;
  /** Shared-board requests one address may send in an hour (60 by default). */
  BOARDS_PER_HOUR?: string;
  /** Origins allowed to open a table, comma-separated. */
  ALLOWED_ORIGINS: string;
  /** The robots' pace in ms (600 by default); the tests shorten it. */
  ROBOT_DELAY_MS?: string;
  /** Close a table's sockets after this long with no action (25 min by default). */
  IDLE_CLOSE_MS?: string;
  /** Tables one address may create in an hour (10 by default). */
  CREATES_PER_HOUR?: string;
  /** "1" in development only: the measurements endpoint. */
  BRIDGE_DEV?: string;
}
