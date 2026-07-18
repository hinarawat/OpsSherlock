# Runbook: OpenStack Nova Instance Launch Failure

**Symptoms:** `nova-compute` logs show `Instance failed to spawn`, `NoValidHost: No valid host was found`, build errors, or instances stuck in BUILD/ERROR state.

**Root cause:** Scheduler cannot place the instance — typically insufficient compute resources (RAM/CPU/disk on hypervisors), image/flavor mismatch, neutron port binding failure, or a down nova-compute service.

**Fix:**
1. Check service health: `openstack compute service list` — restart any down nova-compute (`systemctl restart nova-compute`).
2. Check hypervisor capacity: `openstack hypervisor stats show` — if RAM/vCPU exhausted, free capacity or add nodes; review overcommit ratios in nova.conf.
3. Inspect the failed instance: `openstack server show <id>` → fault message; cross-check nova-scheduler.log for NoValidHost reason.
4. If network-related: check neutron agent status and port binding errors in neutron-server.log.
5. Retry launch after fixing; consider smaller flavor to confirm capacity hypothesis.

**Verification:** New instance reaches ACTIVE state; `openstack compute service list` all up; scheduler logs clean.
