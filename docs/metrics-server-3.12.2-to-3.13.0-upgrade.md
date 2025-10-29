# Metrics-Server 3.12.2 to 3.13.0 Upgrade Guide

**Date:** October 25, 2025  
**Upgrade Path:** v0.7.2 (Chart 3.12.2) → v0.8.0 (Chart 3.13.0)  
**Kubernetes Version:** 1.31  
**Cluster:** BCM-managed Superpod  
**Priority:** P3 - Optional (Both versions compatible with K8s 1.31, 1.32, 1.33)

---

## Purpose

Optional upgrade of metrics-server from v0.7.2 to v0.8.0 to gain enhanced features. Both versions are fully compatible with Kubernetes 1.31, 1.32, and 1.33, so this upgrade is not required for the K8s upgrade path.

## Compatibility Matrix

| metrics-server Version | Chart Version | Kubernetes Support | Best for K8s Version |
|------------------------|---------------|-------------------|---------------------|
| v0.7.2 (previous)      | 3.12.2        | K8s 1.27+         | K8s 1.27-1.33      |
| **v0.8.0 (current)**   | **3.13.0**    | **K8s 1.29+**     | **K8s 1.29-1.33+** |

**Note:** This upgrade is optional. v0.7.2 works perfectly with K8s 1.31, 1.32, and 1.33. v0.8.0 adds enhanced features but no critical fixes.

---

## Pre-Upgrade Steps

### 1. Run Pre-Upgrade Health Check

```bash
cd /root/runai-files/k8s-on-superpod-toolkit
./healthcheck_metrics-server.py | tee pre-upgrade-metrics-server-0.8.log
```

**Expected Result:** All 7 tests should pass (or 6/7 if node/pod metrics are temporarily unavailable).

### 2. Backup Current Helm Values

```bash
mkdir -p ~/runai-files/upgrade-to-1.33/metrics-server
cd ~/runai-files/upgrade-to-1.33/metrics-server
helm get values metrics-server -n kube-system > metrics-server-current-values.yaml
```

**Our Current Values:**
```yaml
USER-SUPPLIED VALUES:
containerPort: 4443
defaultArgs:
- --cert-dir=/tmp
- --kubelet-preferred-address-types=Hostname,InternalIP,ExternalIP
- --kubelet-use-node-status-port
- --metric-resolution=15s
replicas: 2
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
diff <(helm show values metrics-server/metrics-server --version 3.12.2) \
     <(helm show values metrics-server/metrics-server --version 3.13.0)
```

**Key Changes in Chart 3.13.0:**
- ✅ Added `unhealthyPodEvictionPolicy` (new optional field)
- ✅ Added `tls:` configuration section (new optional TLS management features)
  - Support for metrics-server generated certs (default)
  - Support for Helm-generated certs
  - Support for cert-manager
  - Support for existing secrets
- ✅ Updated addon-resizer image tag (1.8.21 → 1.8.23)
- ✅ Minor formatting changes (indentation)

**Impact:** New optional features with defaults. No breaking changes for existing configurations.

---

## Upgrade Process

### 4. Prepare Updated Values File

**CRITICAL:** We cannot use `--reuse-values` because chart 3.13.0 added new configuration sections (`tls:`) that don't exist in the old release. The template tries to access `.Values.tls.type` causing a nil pointer error.

**Error when using `--reuse-values`:**
```
Error: UPGRADE FAILED: template: metrics-server/templates/deployment.yaml:74:27: 
executing "metrics-server/templates/deployment.yaml" at <.Values.tls.type>: 
nil pointer evaluating interface {}.type
```

**Solution:** Use `-f values.yaml` to merge our customizations with the new chart's defaults.

Create the updated values file:
```bash
cd ~/runai-files/upgrade-to-1.33/metrics-server
cat > metrics-server-values.yaml <<'EOF'
containerPort: 4443
defaultArgs:
- --cert-dir=/tmp
- --kubelet-preferred-address-types=Hostname,InternalIP,ExternalIP
- --kubelet-use-node-status-port
- --metric-resolution=15s
replicas: 2

affinity:
  nodeAffinity:
    preferredDuringSchedulingIgnoredDuringExecution:
    - preference:
        matchExpressions:
        - key: node-role.kubernetes.io/runai-system
          operator: Exists
      weight: 1

tolerations:
- effect: NoSchedule
  key: node-role.kubernetes.io/master
  operator: Exists
- effect: NoSchedule
  key: node-role.kubernetes.io/control-plane
  operator: Exists
EOF
```

**Note:** We added `affinity` to prefer scheduling on RunAI control plane nodes (which are also K8s control plane nodes in this environment).

### 5. Execute Helm Upgrade

```bash
helm upgrade metrics-server metrics-server/metrics-server \
  --namespace kube-system \
  --version 3.13.0 \
  -f metrics-server-values.yaml
```

**Expected Output:**
```
Release "metrics-server" has been upgraded. Happy Helming!
NAME: metrics-server
LAST DEPLOYED: Fri Oct 25 XX:XX:XX 2025
NAMESPACE: kube-system
STATUS: deployed
REVISION: 2
...
```

### 6. Monitor Rollout

```bash
kubectl rollout status deployment/metrics-server -n kube-system
```

**Expected Output:**
```
Waiting for deployment "metrics-server" rollout to finish: 1 of 2 updated replicas are available...
deployment "metrics-server" successfully rolled out
```

### 7. Verify Pod Status

```bash
kubectl get pods -n kube-system -l app.kubernetes.io/name=metrics-server
```

**Expected Output:**
```
NAME                              READY   STATUS    RESTARTS   AGE
metrics-server-xxxxxxxxxx-xxxxx   1/1     Running   0          2m
metrics-server-xxxxxxxxxx-xxxxx   1/1     Running   0          2m
```

### 8. Verify Image Version

```bash
kubectl get deployment metrics-server -n kube-system \
  -o jsonpath='{.spec.template.spec.containers[0].image}'
```

**Expected Output:**
```
registry.k8s.io/metrics-server/metrics-server:v0.8.0
```

---

## Post-Upgrade Verification

### 9. Wait for Full Initialization

**IMPORTANT:** After the rollout completes, wait 2-3 minutes before running health checks.

**Why?** metrics-server needs time to:
1. Establish connections to all kubelets
2. Collect initial metrics from nodes and pods
3. Register and stabilize the Metrics API

### 10. Run Post-Upgrade Health Check

```bash
cd /root/runai-files/k8s-on-superpod-toolkit
./healthcheck_metrics-server.py | tee post-upgrade-metrics-server-0.8.log
```

**Expected Result:** All 7 tests should pass:
```
================================================================================
Test Summary
================================================================================

Tests Passed: 7/7
Tests Failed: 0/7

✓ All tests PASSED!
Metrics-server is healthy and functioning properly.
```

### 11. Verify kubectl top Commands

```bash
# Test node metrics
kubectl top nodes

# Test pod metrics (sample)
kubectl top pods -n kube-system
```

**Expected:** Should return resource usage for nodes and pods.

### 12. Compare Pre/Post Upgrade Results

```bash
diff pre-upgrade-metrics-server-0.8.log post-upgrade-metrics-server-0.8.log
```

**Expected Differences:**
- Version change: v0.7.2 → v0.8.0
- Possibly different pod names
- Timestamp differences
- Updated image reference in Test 7

---

## Successful Upgrade Output

### Health Check Test Results

```
================================================================================
Metrics-Server Health Check
================================================================================

Timestamp: 2025-10-25 XX:XX:XX
Namespace: kube-system
Component: metrics-server

Test 1: Metrics-Server Pod Status
Status: ✓ PASS
Details: Found 2 pod(s): 2 running, 2 ready
  • metrics-server-xxxxxxxxxx-xxxxx: Running, Ready: True, Restarts: 0
  • metrics-server-xxxxxxxxxx-xxxxx: Running, Ready: True, Restarts: 0

Test 2: Service Availability
Status: ✓ PASS
Details: Service: metrics-server
  • Type: ClusterIP
  • ClusterIP: 10.240.17.207
  • Ports: https=443→https

Test 3: API Service Registration
Status: ✓ PASS
Details: API Service: v1beta1.metrics.k8s.io
  • Service: kube-system/metrics-server
  • Conditions:
    - Available: True (Passed)

Test 4: Metrics API Availability
Status: ✓ PASS
Details: Metrics API responding successfully
  • API Version: metrics.k8s.io/v1beta1
  • Resources available: nodes, pods

Test 5: Node Metrics Collection
Status: ✓ PASS
Details: Node metrics collected: 5/5 nodes
Sample metrics:
  [node metrics displayed]

Test 6: Pod Metrics Collection
Status: ✓ PASS
Details: Pod metrics collected: XXX/XXX pods (XX.X%)
Sample metrics:
  [pod metrics displayed]

Test 7: Configuration Validation
Status: ✓ PASS
Details:   • Image: registry.k8s.io/metrics-server/metrics-server:v0.8.0
  • Version: v0.8.0
  • Replicas: 2/2 available
  • Key Configuration Args:
    - --cert-dir=/tmp
    - --kubelet-preferred-address-types=Hostname,InternalIP,ExternalIP
    - --metric-resolution=15s
```

---

## Troubleshooting

### Issue: `--reuse-values` Error

**Error:**
```
Error: UPGRADE FAILED: template: metrics-server/templates/deployment.yaml:74:27: 
executing "metrics-server/templates/deployment.yaml" at <.Values.tls.type>: 
nil pointer evaluating interface {}.type
```

**Cause:** Chart 3.13.0 added new `tls:` configuration section that doesn't exist in stored values from chart 3.12.2. Using `--reuse-values` doesn't merge with chart defaults.

**Solution:** Use `-f values.yaml` instead of `--reuse-values` to merge custom values with new chart defaults.

### Issue: Test 1 Fails - No Pods Found

**Error:**
```
Test 1: Metrics-Server Pod Status
Status: ✗ FAIL
Details: No metrics-server pods found
```

**Cause:** Script looking for wrong label selector.

**Solution:** Already fixed in latest version of `healthcheck_metrics-server.py`. Pull latest from GitHub:
```bash
cd /root/runai-files/k8s-on-superpod-toolkit
git pull
```

### Issue: Test 5 or Test 6 Fails - Low Metrics Coverage

**Error:**
```
Test 6: Pod Metrics Collection
Status: ✗ FAIL
Details: Pod metrics collected: XXX/XXX pods (XX.X%)
  WARNING: Low metrics coverage!
```

**Cause:** 
- Nodes rebooting or pods pending
- metrics-server just started and hasn't collected all metrics yet

**Solution:** 
- Wait 3-5 minutes and run health check again
- Check if any nodes are unavailable: `kubectl get nodes`
- Check for pending pods: `kubectl get pods -A | grep Pending`

### Issue: kubectl top Commands Fail

**Error:**
```bash
$ kubectl top nodes
Error from server (ServiceUnavailable): the server is currently unable to handle the request
```

**Cause:** Metrics API not fully initialized or APIService not available.

**Solution:**
1. Check APIService status:
   ```bash
   kubectl get apiservice v1beta1.metrics.k8s.io
   ```

2. Check metrics-server logs:
   ```bash
   kubectl logs -n kube-system -l app.kubernetes.io/name=metrics-server --tail=50
   ```

3. Wait a few more minutes for initialization

---

## Rollback Procedure

If issues occur, rollback is simple:

```bash
# Rollback to previous version
helm rollback metrics-server -n kube-system

# Verify rollback
kubectl rollout status deployment/metrics-server -n kube-system

# Wait for stabilization
sleep 120

# Run health check
cd /root/runai-files/k8s-on-superpod-toolkit
./healthcheck_metrics-server.py
```

---

## What's New in v0.8.0

### Enhanced TLS Certificate Management

Chart 3.13.0 / App v0.8.0 introduces flexible TLS certificate management:

1. **metrics-server Generated** (default) - Self-signed certs managed by metrics-server
2. **Helm Generated** - Self-signed certs managed by Helm
3. **cert-manager Integration** - Automated certificate management via cert-manager.io
4. **Existing Secret** - Reuse existing TLS certificates

**Default behavior:** Uses metrics-server generated certificates (same as v0.7.2), so no changes required for upgrade.

### Other Enhancements

- Improved unhealthy pod eviction policy support
- Updated addon-resizer sidecar (if enabled)
- Enhanced Kubernetes 1.29+ support
- Performance and stability improvements

---

## Next Steps

### Immediate Actions (Completed)
- ✅ Upgraded metrics-server to v0.8.0
- ✅ Added RunAI control plane node affinity
- ✅ Verified all health checks pass
- ✅ Verified kubectl top commands work

### Future Considerations

**No further action required.** metrics-server v0.8.0 is compatible with:
- ✅ Kubernetes 1.31 (current)
- ✅ Kubernetes 1.32 (next upgrade)
- ✅ Kubernetes 1.33 (future upgrade)

This upgrade positions the cluster well for future Kubernetes upgrades.

---

## Key Learnings

1. **Chart Version Upgrades:** When upgrading across chart versions, always use `-f values.yaml` instead of `--reuse-values` to avoid nil pointer errors from new configuration sections.

2. **Health Check Timing:** After deployment rollout completes, allow 2-3 minutes for metrics-server to establish kubelet connections and collect initial metrics before running validation tests.

3. **Affinity Configuration:** For BCM/RunAI environments, prefer scheduling metrics-server on RunAI control plane nodes using nodeAffinity with `node-role.kubernetes.io/runai-system`.

4. **Label Selectors:** Modern Helm charts use `app.kubernetes.io/name` labels instead of older `k8s-app` labels. Health check scripts must support both.

5. **Optional Upgrades:** Not all component upgrades are required. metrics-server v0.7.2 works perfectly fine with K8s 1.31-1.33. v0.8.0 upgrade was done to take advantage of enhanced features, not for compatibility reasons.

6. **Universal Pattern:** This is the **second** component (after kube-state-metrics) where `--reuse-values` failed due to new template sections. The pattern is clear: **Always use `-f values.yaml` for Helm chart version upgrades**.

---

## References

- [metrics-server GitHub](https://github.com/kubernetes-sigs/metrics-server)
- [metrics-server Helm Chart](https://github.com/kubernetes-sigs/metrics-server/tree/master/charts/metrics-server)
- [metrics-server Releases](https://github.com/kubernetes-sigs/metrics-server/releases)
- Compatibility Documentation: `docs/compatibility.md`
- Health Check Script: `healthcheck_metrics-server.py`
- Main Documentation: `README.md`
- Related: `docs/kube-state-metrics-2.15-to-2.16-Upgrade.md`

---

**Upgrade Status:** ✅ **COMPLETED SUCCESSFULLY**  
**Upgraded By:** Travis Wilson  
**Verified:** October 25, 2025  
**Priority:** P3 - Optional (Enhanced features, not required for K8s upgrades)

