# Runbook: TLS Certificate Expired

**Symptoms:** `certificate has expired`, `SSL_ERROR_EXPIRED_CERT_ALERT`, clients failing TLS handshake, browsers showing security errors.

**Root cause:** Certificate passed its notAfter date — auto-renewal (certbot/cert-manager) failed silently or cert was manually issued and forgotten.

**Fix:**
1. Confirm: `openssl s_client -connect host:443 | openssl x509 -noout -dates`.
2. Renew now: `certbot renew --force-renewal` (or `kubectl delete certificate <name>` to force cert-manager reissue).
3. Reload the frontend: `nginx -s reload` / restart ingress.
4. Fix root cause of failed auto-renewal (DNS challenge creds, rate limits); add expiry monitoring alert at 14 days.

**Verification:** openssl shows new notAfter date; clients connect cleanly.
