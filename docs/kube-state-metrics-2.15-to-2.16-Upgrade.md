# Kube-State-Metrics 2.15 to 2.16 Upgrade Guide

**Date:** October 25, 2025  
**Upgrade Path:** v2.15.0 (Chart 5.31.0) → v2.16.0 (Chart 6.1.5)  
**Kubernetes Version:** 1.31 (preparing for 1.32)  
**Cluster:** BCM-managed Superpod

---

## Purpose

Upgrade kube-state-metrics to v2.16.0 (client-go v1.32) in preparation for Kubernetes 1.32 upgrade. This is an interim step before the final K8s 1.33 upgrade, which will require kube-state-metrics v2.17.0.

## Compatibility Matrix

| kube-state-metrics Version | Chart Version | Kubernetes client-go | Best for K8s Version |
|----------------------------|---------------|---------------------|---------------------|
| v2.15.0 (previous)         | 5.31.0        | v1.32               | K8s 1.31-1.32      |
| **v2.16.0 (current)**      | **6.1.5**     | **v1.32**           | **K8s 1.32**       |
| v2.17.0 (next)             | 6.3.0         | v1.33               | K8s 1.33           |

**Note:** We are stopping at v2.16.0 for now as we wait for BCM to support Kubernetes 1.33. When BCM support is available, we will upgrade from v2.16.0 → v2.17.0 before upgrading Kubernetes to 1.33.

---

## Pre-Upgrade Steps

### 1. Run Pre-Upgrade Health Check

```bash
cd /root/runai-files/k8s-on-superpod-toolkit
./healthcheck_kube-state-metrics.py | tee pre-upgrade-ksm-2.16.log
```

**Expected Result:** All 7 tests should pass (or 6/7 if ServiceMonitor test fails - that's OK).

### 2. Backup Current Helm Values

```bash
mkdir -p ~/runai-files/upgrade-to-1.33/ksm/backup
cd ~/runai-files/upgrade-to-1.33/ksm/backup
helm get values kube-state-metrics -n kube-system > ksm-current-values.yaml
```

**Our Current Values:**
```yaml
USER-SUPPLIED VALUES:
tolerations:
- effect: NoSchedule
  key: node-role.kubernetes.io/master
  operator: Exists
- effect: NoSchedule
  key: node-role.kubernetes.io/control-plane
  operator: Exists
```

### 3. Review Chart Changes

Check differences between chart versions:
```bash
diff <(helm show values prometheus-community/kube-state-metrics --version 5.31.0) \
     <(helm show values prometheus-community/kube-state-metrics --version 6.1.5)
```

**Key Changes in Chart 6.x:**
- ✅ Removed deprecated `podSecurityPolicy` (PSPs removed in K8s 1.25+)
- ✅ Removed `kubeTargetVersionOverride` (was for PSP support)
- ✅ Added `prometheus.scrapeconfig` section (disabled by default)
- ✅ Added kubeRBACProxy enhancements
- ✅ Changed `env: {}` to `env: []` (formatting)
- ✅ Added optional `dnsPolicy` and `dnsConfig` settings

**Impact:** No breaking changes for our configuration.

---

## Upgrade Process

### 4. Prepare Updated Values File

**IMPORTANT:** We cannot use `--reuse-values` because chart 6.x added new configuration sections (`prometheus.scrapeconfig`) that don't exist in the old release. Using `--reuse-values` causes a nil pointer error.

**Solution:** Use `-f values.yaml` to merge our customizations with the new chart's defaults.

Create the updated values file:
```bash
cd ~/runai-files/upgrade-to-1.33/ksm/backup
cat > ksm-updated-values.yaml <<'EOF'
tolerations:
- effect: NoSchedule
  key: node-role.kubernetes.io/master
  operator: Exists
- effect: NoSchedule
  key: node-role.kubernetes.io/control-plane
  operator: Exists

affinity:
  nodeAffinity:
    preferredDuringSchedulingIgnoredDuringExecution:
    - preference:
        matchExpressions:
        - key: node-role.kubernetes.io/runai-system
          operator: Exists
      weight: 1
EOF
```

**Note:** We added `affinity` to prefer scheduling on RunAI control plane nodes.

### 5. Execute Helm Upgrade

```bash
helm upgrade kube-state-metrics prometheus-community/kube-state-metrics \
  --namespace kube-system \
  --version 6.1.5 \
  -f ksm-updated-values.yaml
```

**Expected Output:**
```
Release "kube-state-metrics" has been upgraded. Happy Helming!
NAME: kube-state-metrics
LAST DEPLOYED: Fri Oct 25 20:XX:XX 2025
NAMESPACE: kube-system
STATUS: deployed
REVISION: 2
...
```

### 6. Monitor Rollout

```bash
kubectl rollout status deployment/kube-state-metrics -n kube-system
```

**Expected Output:**
```
deployment "kube-state-metrics" successfully rolled out
```

### 7. Verify Pod Status

```bash
kubectl get pods -n kube-system -l app.kubernetes.io/name=kube-state-metrics
```

**Expected Output:**
```
NAME                                  READY   STATUS    RESTARTS   AGE
kube-state-metrics-6558d5fbc7-9b8jp   1/1     Running   0          5m
```

### 8. Verify Image Version

```bash
kubectl get deployment kube-state-metrics -n kube-system \
  -o jsonpath='{.spec.template.spec.containers[0].image}'
```

**Expected Output:**
```
registry.k8s.io/kube-state-metrics/kube-state-metrics:v2.16.0
```

---

## Post-Upgrade Verification

### 9. Wait for Full Initialization

**IMPORTANT:** After the rollout completes, wait an additional 3-5 minutes before running health checks.

**Why?** The pod needs time to:
1. Establish connections to the Kubernetes API
2. Build the initial metrics cache
3. Fully initialize the metrics endpoint

If you run the health check too soon, Test 3 (Metrics Endpoint Accessibility) may fail with:
```
Test 3: Metrics Endpoint Accessibility
Status: ✗ FAIL
Details: Cannot access metrics endpoint via port-forward
```

**Solution:** Wait 3-5 minutes after rollout, then run the health check again.

### 10. Run Post-Upgrade Health Check

```bash
cd /root/runai-files/k8s-on-superpod-toolkit
./healthcheck_kube-state-metrics.py | tee post-upgrade-ksm-2.16.log
```

**Expected Result:** All 7 tests should pass:
```
================================================================================
Test Summary
================================================================================

Tests Passed: 7/7
Tests Failed: 0/7

✓ All tests PASSED!
Kube-state-metrics is healthy and functioning properly.
```

### 11. Compare Pre/Post Upgrade Results

```bash
diff pre-upgrade-ksm-2.16.log post-upgrade-ksm-2.16.log
```

**Expected Differences:**
- Version change: v2.15.0 → v2.16.0
- Possibly different pod name
- Timestamp differences

---

## Successful Upgrade Output

### Health Check Test Results

```
Test 1: Kube-State-Metrics Pod Status
Status: ✓ PASS
Details: Found 1 pod(s): 1 running, 1 ready
  • kube-state-metrics-6558d5fbc7-9b8jp: Running, Ready: True, Restarts: 0

Test 2: Service Availability
Status: ✓ PASS
Details: Found 1 service(s):
  • kube-state-metrics: ClusterIP
    - ClusterIP: 10.240.240.105
    - Ports: http=8080→8080

Test 3: Metrics Endpoint Accessibility
Status: ✓ PASS
Details: Metrics endpoint responding successfully
Sample output:
  # HELP kube_configmap_annotations Kubernetes annotations converted to Prometheus labels.
  # TYPE kube_configmap_annotations gauge
  [...]

Test 4: Core Metrics Availability
Status: ✓ PASS
Details: Found 7/7 core metrics:
  ✓ kube_pod_info
  ✓ kube_pod_status_phase
  ✓ kube_node_info
  ✓ kube_node_status_condition
  ✓ kube_deployment_status_replicas
  ✓ kube_daemonset_status_number_ready
  ✓ kube_namespace_status_phase

Test 5: Metric Freshness Validation
Status: ✓ PASS
Details: Metrics vs. Actual:
  • Nodes: 8 (metrics) vs 8 (actual)
  • Pods: 312 (metrics) vs 314 (actual)

  Metrics are fresh and accurate!

Test 6: Resource Metrics Coverage
Status: ✓ PASS
Details: Monitoring 28 resource type(s):
  certificatesigningrequests, configmaps, cronjobs, daemonsets, deployments, [...]

Test 7: Configuration Validation
Status: ✓ PASS
Details:   • Image: registry.k8s.io/kube-state-metrics/kube-state-metrics:v2.16.0
  • Version: v2.16.0
  • Replicas: 1/1 available
  • Resource Requests:
    - CPU: not set
    - Memory: not set
  • Resource Limits:
    - CPU: not set
    - Memory: not set
```

---

## Troubleshooting

### Issue: `--reuse-values` Error

**Error:**
```
Error: UPGRADE FAILED: template: kube-state-metrics/templates/scrapeconfig.yaml:1:14: 
executing "kube-state-metrics/templates/scrapeconfig.yaml" at 
<.Values.prometheus.scrapeconfig.enabled>: nil pointer evaluating interface {}.enabled
```

**Cause:** Chart 6.x added new configuration sections that don't exist in the stored values from chart 5.x. Using `--reuse-values` doesn't merge with chart defaults.

**Solution:** Use `-f values.yaml` instead of `--reuse-values` to merge custom values with new chart defaults.

### Issue: Test 3 Fails Immediately After Upgrade

**Error:**
```
Test 3: Metrics Endpoint Accessibility
Status: ✗ FAIL
Details: Cannot access metrics endpoint via port-forward
```

**Cause:** Pod just started and metrics endpoint not fully initialized.

**Solution:** Wait 3-5 minutes and run health check again. The pod needs time to build its metrics cache.

### Issue: Port 18080 Already in Use

**Error:** Port-forward fails because port 18080 is in use.

**Solution:**
```bash
# Check for existing port-forwards
ps aux | grep "port-forward.*kube-state"

# Kill any old port-forward processes
pkill -f "port-forward.*kube-state"

# Check if port is in use
ss -tuln | grep 18080
```

---

## Rollback Procedure

If issues occur, rollback is simple:

```bash
# Rollback to previous version
helm rollback kube-state-metrics -n kube-system

# Verify rollback
kubectl rollout status deployment/kube-state-metrics -n kube-system

# Run health check
./healthcheck_kube-state-metrics.py
```

---

## Next Steps

### Immediate Actions (Completed)
- ✅ Upgraded kube-state-metrics to v2.16.0 for K8s 1.32
- ✅ Added RunAI control plane node affinity
- ✅ Verified all health checks pass

### Future Actions (When BCM Supports K8s 1.33)

1. **Before K8s 1.33 Upgrade:**
   ```bash
   # Upgrade kube-state-metrics to v2.17.0
   helm upgrade kube-state-metrics prometheus-community/kube-state-metrics \
     --namespace kube-system \
     --version 6.3.0 \
     -f ksm-updated-values.yaml
   ```

2. **Proceed with K8s 1.33 Upgrade**

3. **Verify after K8s 1.33:**
   ```bash
   ./healthcheck_kube-state-metrics.py
   ```

---

## Key Learnings

1. **Chart Version Jumps:** When upgrading across major chart versions (5.x → 6.x), always use `-f values.yaml` instead of `--reuse-values` to avoid nil pointer errors from new configuration sections.

2. **Metrics Initialization:** After deployment rollout completes, allow 3-5 minutes for the metrics endpoint to fully initialize before running validation tests.

3. **Affinity Configuration:** For BCM/RunAI environments, prefer scheduling kube-state-metrics on RunAI control plane nodes using nodeAffinity with `node-role.kubernetes.io/runai-system`.

4. **Health Check Script:** The `healthcheck_kube-state-metrics.py` script provides comprehensive validation and catches issues immediately. Always run before and after upgrades.

5. **Staged Upgrades:** When planning multi-version Kubernetes upgrades (1.31 → 1.32 → 1.33), upgrade kube-state-metrics in stages matching each K8s version for optimal client-go compatibility.

---

## References

- [kube-state-metrics GitHub](https://github.com/kubernetes/kube-state-metrics)
- [kube-state-metrics Compatibility Matrix](https://github.com/kubernetes/kube-state-metrics#compatibility-matrix)
- [Prometheus Community Helm Charts](https://github.com/prometheus-community/helm-charts/tree/main/charts/kube-state-metrics)
- Compatibility Documentation: `docs/compatibility.md`
- Health Check Script: `healthcheck_kube-state-metrics.py`
- Main Documentation: `README.md`

---

**Upgrade Status:** ✅ **COMPLETED SUCCESSFULLY**  
**Upgraded By:** Travis Wilson  
**Verified:** October 25, 2025

