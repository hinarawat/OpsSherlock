# Runbook: Postgres Connection Pool Exhaustion

**Symptoms:** `FATAL: sorry, too many clients already`, `remaining connection slots are reserved`, app timeouts acquiring connections.

**Root cause:** App opens more connections than Postgres max_connections, usually from connection leaks (unclosed sessions), missing pooler, or replica failover doubling load.

**Fix:**
1. Identify hogs: `SELECT client_addr, state, count(*) FROM pg_stat_activity GROUP BY 1,2 ORDER BY 3 DESC;`
2. Kill idle-in-transaction sessions older than 10 min.
3. Deploy/verify PgBouncer in transaction mode between app and DB.
4. Fix app-side leaks: ensure connections returned to pool in finally blocks; set pool max_size sanely (replicas x pool_size < max_connections).

**Verification:** pg_stat_activity count stays under 70% of max_connections during peak.
