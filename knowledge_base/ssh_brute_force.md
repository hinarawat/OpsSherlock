# Runbook: SSH Brute-Force / Authentication Failure Attack

**Symptoms:** Bursts of `Failed password`, `Invalid user`, `authentication failure`, or `POSSIBLE BREAK-IN ATTEMPT` in sshd logs, often from a small set of IPs cycling through usernames (webmaster, test, admin, root).

**Root cause:** Automated credential-stuffing/brute-force attack against the SSH daemon, typically from botnets scanning the internet. Reverse-DNS mismatch warnings indicate spoofed or disposable attacker hosts.

**Fix:**
1. Identify attacking IPs: `grep "Failed password" /var/log/auth.log | awk '{print $(NF-3)}' | sort | uniq -c | sort -rn | head`.
2. Block them now: `fail2ban-client set sshd banip <ip>` or add firewall deny rules (`ufw deny from <ip>`).
3. Verify no successful login from attacker IPs: `grep "Accepted" /var/log/auth.log | grep <ip>`. If found, treat as compromise — rotate keys, audit authorized_keys, escalate to security.
4. Harden: disable password auth (`PasswordAuthentication no`), disable root login, deploy fail2ban, move SSH off port 22 / behind VPN.

**Verification:** Auth failure rate drops to baseline; fail2ban shows bans; no `Accepted` events from suspicious IPs.
