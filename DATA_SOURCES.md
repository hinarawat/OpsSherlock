# 📚 Data Sources — OpsSherlock

Where every log file and knowledge-base (RAG) runbook came from.

## Sample Logs (`sample_logs/`)

| File | Origin | Source link |
|---|---|---|
| `ssh_brute_force.log` | ✅ **Real** — actual SSH attack traffic captured on a lab server (Loghub research dataset) | [logpai/loghub → OpenSSH](https://github.com/logpai/loghub/tree/master/OpenSSH) |
| `linux_system.log` | ✅ **Real** — real Linux syslog (Loghub research dataset) | [logpai/loghub → Linux](https://github.com/logpai/loghub/tree/master/Linux) |
| `openstack_nova.log` | ⚙️ Crafted — error lines written in the exact nova log format from Loghub's real OpenStack sample (the public sample contained no error lines) | [logpai/loghub → OpenStack](https://github.com/logpai/loghub/tree/master/OpenStack) (format reference) |
| `k8s_oom_killed.log` | ⚙️ Crafted — modeled on real kubelet/OOMKilled log format | Kubernetes docs (format reference) |
| `nginx_502.log` | ⚙️ Crafted — real nginx error-log format; the real elastic dataset had no 5xx errors | [elastic/examples → nginx_logs](https://github.com/elastic/examples/tree/master/Common%20Data%20Formats/nginx_logs) (evaluated, not used) |
| `postgres_pool.log` | ⚙️ Crafted — real Postgres/SQLAlchemy error message formats | Postgres docs (format reference) |
| `disk_full.log` | ⚙️ Crafted — standard syslog/systemd format | — |
| `aws_rds_storage.log` | ⚙️ Crafted — uses real AWS RDS event codes (RDS-EVENT-0007, RDS-EVENT-0089) | AWS RDS event documentation (format reference) |
| `tls_expired.log` | ⚙️ Crafted — standard haproxy/JVM TLS error formats | — |

## Knowledge Base / RAG corpus (`knowledge_base/`)

| File | Origin | Source link |
|---|---|---|
| `k8s_oom_killed.md` | ✅ **Real** SRE playbook (copied verbatim) | [Scoutflo → KubeContainerOOMKilled-pod.md](https://github.com/Scoutflo/Scoutflo-SRE-Playbooks/blob/main/K8s%20Playbooks/03-Pods/KubeContainerOOMKilled-pod.md) |
| `k8s_crashloopbackoff.md` | ✅ **Real** SRE playbook | [Scoutflo → CrashLoopBackOff-pod.md](https://github.com/Scoutflo/Scoutflo-SRE-Playbooks/blob/main/K8s%20Playbooks/03-Pods/CrashLoopBackOff-pod.md) |
| `k8s_imagepullbackoff.md` | ✅ **Real** SRE playbook | [Scoutflo → ImagePullBackOff-registry.md](https://github.com/Scoutflo/Scoutflo-SRE-Playbooks/blob/main/K8s%20Playbooks/03-Pods/ImagePullBackOff-registry.md) |
| `aws_rds_storage_full.md` | ✅ **Real** SRE playbook | [Scoutflo → Storage-Full-Error-RDS.md](https://github.com/Scoutflo/Scoutflo-SRE-Playbooks/blob/main/AWS%20Playbooks/02-Database/Storage-Full-Error-RDS.md) |
| `aws_ec2_high_cpu.md` | ✅ **Real** SRE playbook | [Scoutflo → High-CPU-Utilization-EC2.md](https://github.com/Scoutflo/Scoutflo-SRE-Playbooks/blob/main/AWS%20Playbooks/01-Compute/High-CPU-Utilization-EC2.md) |
| `aws_dynamodb_throttling.md` | ✅ **Real** SRE playbook | [Scoutflo → Throttling-Errors-DynamoDB.md](https://github.com/Scoutflo/Scoutflo-SRE-Playbooks/blob/main/AWS%20Playbooks/02-Database/Throttling-Errors-DynamoDB.md) |
| `ssh_brute_force.md` | ✍️ Authored for this project, style based on public incident-response templates | [sectemplates](https://github.com/securitytemplates/sectemplates) (style reference) |
| `nginx_502_upstream.md` | ✍️ Authored, standard nginx troubleshooting practice | nginx docs (reference) |
| `postgres_connection_pool.md` | ✍️ Authored, standard Postgres/PgBouncer practice | Postgres wiki (reference) |
| `disk_full.md` | ✍️ Authored, standard Linux ops practice | — |
| `openstack_instance_failure.md` | ✍️ Authored, based on OpenStack operations guide | OpenStack docs (reference) |
| `tls_cert_expired.md` | ✍️ Authored, standard certbot/cert-manager practice | — |

**Dataset credits:** [Loghub](https://github.com/logpai/loghub) (ISSRE '23 — 19 real-world log datasets) · [Scoutflo SRE Playbooks](https://github.com/Scoutflo/Scoutflo-SRE-Playbooks) (414 open-source incident playbooks).
