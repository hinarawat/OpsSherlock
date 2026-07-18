# Runbook: Disk Full / No Space Left on Device

**Symptoms:** `No space left on device`, writes failing, services crashing, `df -h` shows 100% on a volume.

**Root cause:** Log growth without rotation, large temp/core files, docker image/layer bloat, or runaway data growth.

**Fix:**
1. Find the culprit: `du -xh --max-depth=2 /var | sort -rh | head`.
2. Truncate/rotate huge logs: `truncate -s 0 <file>`; fix logrotate config.
3. Docker hosts: `docker system prune -af --volumes` (check first!).
4. Expand volume if growth is legitimate; add disk usage alert at 80%.

**Verification:** `df -h` below 80%; failing service writes succeed again.
