# Runbook: Nginx 502 Bad Gateway (upstream failure)

**Symptoms:** 502 errors, logs show `connect() failed (111: Connection refused) while connecting to upstream` or `upstream timed out`.

**Root cause:** Upstream app server is down, overloaded, or not listening on the expected port/socket. Can also be upstream keepalive/timeout mismatch.

**Fix:**
1. Check upstream health: `curl -I http://upstream:port/health`; restart the app service if down.
2. Verify nginx upstream config points at the right host/port.
3. If timeouts: raise `proxy_read_timeout`, and ensure upstream keepalive_timeout > nginx keepalive_timeout.
4. Check upstream worker saturation (queue full) — scale replicas.

**Verification:** 502 rate drops to 0 in access logs; `curl` through nginx returns 200.
