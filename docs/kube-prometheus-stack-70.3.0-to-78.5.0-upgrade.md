# kube-prometheus-stack Upgrade: 70.3.0 → 78.5.0

**Date:** October 29, 2025  
**Target Kubernetes Version:** 1.32.x (preparing for 1.33.x)

## Purpose

Upgrade the `kube-prometheus-stack` Helm chart from version 70.3.0 (app v0.81.0) to 78.5.0 (app v0.86.1) to maintain compatibility with Kubernetes 1.31, 1.32, and prepare for 1.33.

## Compatibility

### Version Information
- **Current:** Chart 70.3.0, App v0.81.0 (Prometheus Operator)
- **Target:** Chart 78.5.0, App v0.86.1 (Prometheus Operator)
- **Kubernetes Compatibility:** Both versions are compatible with K8s 1.31, 1.32, and 1.33
- **Priority:** P2 (Optional upgrade, primarily for latest features and bug fixes)

### Documentation References
- **Helm Chart:** https://github.com/prometheus-community/helm-charts/tree/main/charts/kube-prometheus-stack
- **Releases:** https://artifacthub.io/packages/helm/prometheus-community/kube-prometheus-stack
- **Prometheus Operator:** https://github.com/prometheus-operator/prometheus-operator

## Components Included

The kube-prometheus-stack includes:
1. **Prometheus Operator** - Manages Prometheus and Alertmanager instances
2. **Prometheus** - Metrics collection and storage
3. **Alertmanager** - Alert management and routing
4. **Grafana** - Visualization and dashboards
5. **kube-state-metrics** - Kubernetes object metrics
6. **prometheus-node-exporter** - Node-level metrics (DaemonSet)

## Pre-Upgrade Health Check

### 1. Create Health Check Script

A comprehensive health check script was created at `healthchecks/healthcheck_kube-prometheus-stack.py` to validate:
- Prometheus Operator deployment status
- Prometheus StatefulSet readiness
- Alertmanager StatefulSet readiness
- Grafana deployment status
- Node Exporter DaemonSet coverage
- ServiceMonitors configuration
- PrometheusRules configuration
- Prometheus targets health (with intelligent control plane failure detection)
- Prometheus query functionality
- CRD installation

### 2. Run Pre-Upgrade Health Check

```bash
cd /home/travisw/dev/k8s-on-superpod-toolkit
python3 healthchecks/healthcheck_kube-prometheus-stack.py
```

**Expected Result:** All tests should pass. Note that some Prometheus targets for control plane components (kube-controller-manager, kube-scheduler, kube-proxy) are expected to fail on non-control-plane nodes.

### 3. Document Current State

```bash
# Get current chart version
helm list -n prometheus | grep kube-prometheus-stack

# Get all pods
kubectl get pods -n prometheus -o wide

# Get current resource versions
kubectl get statefulsets,deployments,daemonsets -n prometheus
```

## Upgrade Process

### Step 1: Backup Current Configuration

```bash
cd ~/runai-files/upgrade-to-1.33/kube-prometheus-stack

# Export current values
helm get values kube-prometheus-stack -n prometheus > kps-70.3.0-current-values.yaml

# Backup current release info
helm get all kube-prometheus-stack -n prometheus > kps-70.3.0-release-backup.yaml
```

### Step 2: Compare Chart Versions

```bash
# Update Helm repo
helm repo update prometheus-community

# Pull both chart versions for comparison
helm pull prometheus-community/kube-prometheus-stack --version 70.3.0 --untar
helm pull prometheus-community/kube-prometheus-stack --version 78.5.0 --untar

# Extract default values
cp kube-prometheus-stack-70.3.0/values.yaml kps-70.3.0-defaults.yaml
cp kube-prometheus-stack-78.5.0/values.yaml kps-78.5.0-defaults.yaml

# Compare defaults (review major changes)
diff -u kps-70.3.0-defaults.yaml kps-78.5.0-defaults.yaml > kps-chart-diff.txt
```

### Step 3: Create Updated Values File

Create `kps-current-values.yaml` with your custom configuration plus required affinity rules:

```yaml
# Your existing custom configuration
grafana:
  additionalDataSources: []
  grafana.ini:
    server:
      root_url: '%(protocol)s://%(domain)s:%(http_port)s/grafana/'
      serve_from_sub_path: true
  # Add affinity for Grafana
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
    key: node-role.kubernetes.io/control-plane
    operator: Exists

prometheus:
  prometheusSpec:
    # Your existing scrape configs
    additionalScrapeConfigs:
    - job_name: gpu-metrics
      kubernetes_sd_configs:
      - namespaces:
          names:
          - gpu-operator
        role: endpoints
      metrics_path: /metrics
      relabel_configs:
      - action: drop
        regex: .*-node-feature-discovery-master
        source_labels:
        - __meta_kubernetes_endpoints_name
      - action: replace
        source_labels:
        - __meta_kubernetes_pod_node_name
        target_label: kubernetes_node
      scheme: http
      scrape_interval: 1s
    
    # Add affinity for Prometheus
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
      key: node-role.kubernetes.io/control-plane
      operator: Exists

# Add affinity for Alertmanager
alertmanager:
  alertmanagerSpec:
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
      key: node-role.kubernetes.io/control-plane
      operator: Exists

# Add affinity for Prometheus Operator
prometheusOperator:
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
    key: node-role.kubernetes.io/control-plane
    operator: Exists

# Add affinity for kube-state-metrics (subchart)
kube-state-metrics:
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
    key: node-role.kubernetes.io/control-plane
    operator: Exists
```

### Step 4: Perform Helm Upgrade

```bash
# Upgrade with values file
helm upgrade kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  --namespace prometheus \
  --version 78.5.0 \
  -f kps-current-values.yaml
```

**Expected Output:**
```
Release "kube-prometheus-stack" has been upgraded. Happy Helming!
NAME: kube-prometheus-stack
LAST DEPLOYED: <timestamp>
NAMESPACE: prometheus
STATUS: deployed
REVISION: <n>
```

### Step 5: Force StatefulSet Pod Recreation

**IMPORTANT:** StatefulSets do not automatically recreate pods when affinity rules change. Manual deletion is required:

```bash
# Delete Alertmanager pod
kubectl delete pod alertmanager-kube-prometheus-stack-alertmanager-0 -n prometheus

# Delete Prometheus pod
kubectl delete pod prometheus-kube-prometheus-stack-prometheus-0 -n prometheus

# Verify pods are recreated on correct nodes
kubectl get pods -n prometheus -o wide
```

### Step 6: Monitor Rollout

```bash
# Watch all deployments
kubectl rollout status deployment/kube-prometheus-stack-grafana -n prometheus
kubectl rollout status deployment/kube-prometheus-stack-operator -n prometheus
kubectl rollout status deployment/kube-prometheus-stack-kube-state-metrics -n prometheus

# Watch StatefulSets (after manual deletion)
kubectl rollout status statefulset/prometheus-kube-prometheus-stack-prometheus -n prometheus
kubectl rollout status statefulset/alertmanager-kube-prometheus-stack-alertmanager -n prometheus

# Verify all pods are running
kubectl get pods -n prometheus -o wide
```

**Expected Result:** All pods should be running on RunAI system nodes (not DGX worker nodes).

## Post-Upgrade Validation

### 1. Run Health Check

```bash
cd /home/travisw/dev/k8s-on-superpod-toolkit
python3 healthchecks/healthcheck_kube-prometheus-stack.py
```

**Expected Result:** All tests should pass.

### 2. Verify Pod Placement

```bash
# Check all pods are on correct nodes
kubectl get pods -n prometheus -o wide

# Run DGX pod placement health check
python3 healthchecks/healthcheck_dgx-pods.py
```

**Expected Result:** 
- All non-DaemonSet pods should be on RunAI system nodes (runai-01, runai-02, etc.)
- Node Exporter DaemonSet pods should be on all nodes
- No violations in DGX pod placement health check

### 3. Compare Configuration

```bash
# Export new values
helm get values kube-prometheus-stack -n prometheus > kps-78.5.0-deployed-values.yaml

# Compare with pre-upgrade values
diff -u kps-70.3.0-current-values.yaml kps-78.5.0-deployed-values.yaml
```

### 4. Verify Component Functionality

```bash
# Check Prometheus is scraping targets
kubectl port-forward -n prometheus svc/kube-prometheus-stack-prometheus 9090:9090
# Open browser to http://localhost:9090/targets

# Check Grafana is accessible
kubectl port-forward -n prometheus svc/kube-prometheus-stack-grafana 3000:80
# Open browser to http://localhost:3000

# Check Alertmanager is running
kubectl port-forward -n prometheus svc/kube-prometheus-stack-alertmanager 9093:9093
# Open browser to http://localhost:9093
```

## Critical Issues Encountered

### Issue 1: `--reuse-values` Not Safe

**Problem:** Using `helm upgrade --reuse-values` is not safe for this upgrade because:
- New chart versions may introduce new top-level configuration sections
- The stored release values don't include new defaults
- This can cause nil pointer errors or missing configurations

**Solution:** Always use `-f values.yaml` approach:
1. Export current values: `helm get values <release> > current-values.yaml`
2. Review and update as needed
3. Upgrade with explicit values file: `helm upgrade <release> <chart> -f current-values.yaml`

### Issue 2: StatefulSet Pods Not Automatically Updated

**Problem:** When affinity or other pod template changes are made via Helm, StatefulSet pods are not automatically recreated. They continue running with old specifications until manually deleted.

**Solution:** After Helm upgrade, manually delete StatefulSet pods:
```bash
kubectl delete pod <statefulset-pod-name> -n <namespace>
```

The StatefulSet controller will automatically recreate the pod with the new configuration.

### Issue 3: Incorrect Namespace and Labels in Health Check

**Problem:** Initial health check script used incorrect namespace (`monitoring` instead of `prometheus`) and incorrect label selectors for various components.

**Solution:** Updated health check to use:
- Correct namespace: `prometheus`
- Correct labels:
  - Prometheus Operator: `app.kubernetes.io/name=kube-prometheus-stack-prometheus-operator`
  - Prometheus: `app=kube-prometheus-stack-prometheus`
  - Alertmanager: `app=kube-prometheus-stack-alertmanager`
  - Node Exporter: `app.kubernetes.io/name=prometheus-node-exporter`

### Issue 4: False Positives in Prometheus Targets Health Check

**Problem:** Prometheus targets health check was failing due to expected control plane component failures (kube-controller-manager, kube-scheduler, kube-proxy) on non-control-plane nodes.

**Solution:** Enhanced the health check to:
1. Query nodes and classify them as control-plane vs worker nodes
2. Calculate expected failures: `(control_plane_nodes × 2) + (total_nodes × 1)`
3. Distinguish between expected control plane failures and unexpected failures
4. Only fail the test if unexpected target failures are found
5. Display detailed error messages for unexpected down targets

## Troubleshooting

### Pods Stuck in Pending State

**Symptoms:** Pods remain in `Pending` state after upgrade

**Diagnosis:**
```bash
kubectl describe pod <pod-name> -n prometheus
```

**Common Causes:**
1. Insufficient resources on RunAI system nodes
2. Affinity/toleration rules preventing scheduling
3. PersistentVolume issues

**Resolution:**
1. Check node resources: `kubectl describe node <node-name>`
2. Review pod events: `kubectl get events -n prometheus --sort-by='.lastTimestamp'`
3. Temporarily remove affinity rules if needed for troubleshooting

### CRD Conflicts or Upgrade Failures

**Symptoms:** Helm upgrade fails with CRD-related errors

**Diagnosis:**
```bash
kubectl get crds | grep monitoring.coreos.com
```

**Resolution:**
1. CRDs are typically not automatically upgraded by Helm
2. May need to manually apply CRDs from the new chart version
3. See: https://github.com/prometheus-operator/prometheus-operator#quickstart

### Prometheus Not Scraping Targets

**Symptoms:** Targets show as "down" in Prometheus UI

**Diagnosis:**
```bash
# Check ServiceMonitors
kubectl get servicemonitors -n prometheus

# Check Prometheus logs
kubectl logs prometheus-kube-prometheus-stack-prometheus-0 -n prometheus -c prometheus
```

**Resolution:**
1. Verify ServiceMonitors have correct label selectors
2. Verify target pods are running and have correct labels
3. Check network policies aren't blocking scraping
4. Verify custom scrape configs in values.yaml

### Grafana Dashboards Missing or Broken

**Symptoms:** Grafana dashboards are empty or show "No data"

**Diagnosis:**
```bash
# Check Grafana datasource configuration
kubectl get configmap -n prometheus | grep grafana

# Check Grafana logs
kubectl logs deployment/kube-prometheus-stack-grafana -n prometheus -c grafana
```

**Resolution:**
1. Verify Prometheus datasource is configured correctly
2. Check dashboard ConfigMaps are present: `kubectl get configmaps -n prometheus -l grafana_dashboard=1`
3. Restart Grafana pod if needed: `kubectl rollout restart deployment/kube-prometheus-stack-grafana -n prometheus`

## Key Learnings

### 1. Always Use Explicit Values Files

Never rely on `--reuse-values` for multi-version upgrades. Always:
1. Export current values
2. Compare with new chart defaults
3. Merge your customizations with new defaults
4. Upgrade with explicit values file

### 2. StatefulSet Updates Require Manual Intervention

StatefulSets do not automatically roll pods when pod template changes. Always plan for:
1. Manual pod deletion after Helm upgrade
2. Brief service interruption during pod recreation
3. Persistent volume considerations

### 3. Comprehensive Health Checks Are Essential

A robust health check script should:
1. Test all components (Operator, Prometheus, Alertmanager, Grafana, Exporters)
2. Validate configuration (ServiceMonitors, PrometheusRules, CRDs)
3. Check data collection (targets, queries)
4. Account for expected failures (control plane components)
5. Provide detailed error messages for troubleshooting

### 4. Pod Placement Matters in Multi-Tenant Environments

In RunAI environments:
1. Keep monitoring stack on dedicated system nodes
2. Use affinity rules to prevent placement on GPU worker nodes
3. Use tolerations to allow placement on tainted control plane nodes
4. Validate placement with dedicated health checks

### 5. Documentation Reference Accuracy Is Critical

When documenting compatibility:
1. Verify you're referencing the correct project (kube-prometheus-stack vs kube-prometheus)
2. Use Helm chart documentation, not standalone project docs
3. Cross-reference ArtifactHub for accurate version information
4. Include direct links to specific versions

## Related Documentation

- [Compatibility Matrix](compatibility.md) - Full application compatibility tracking
- [Health Check Scripts](../README.md#monitoring-stack-health-check-scripts) - All health check documentation
- [kube-state-metrics Upgrade](kube-state-metrics-2.15-to-2.16-Upgrade.md) - Related component upgrade
- [metrics-server Upgrade](metrics-server-3.12.2-to-3.13.0-upgrade.md) - Related component upgrade

## Rollback Procedure

If issues are encountered and rollback is necessary:

```bash
# Rollback to previous release
helm rollback kube-prometheus-stack -n prometheus

# Verify rollback
helm list -n prometheus
kubectl get pods -n prometheus

# Delete StatefulSet pods to apply old configuration
kubectl delete pod alertmanager-kube-prometheus-stack-alertmanager-0 -n prometheus
kubectl delete pod prometheus-kube-prometheus-stack-prometheus-0 -n prometheus

# Run health check
python3 healthchecks/healthcheck_kube-prometheus-stack.py
```

## Summary

✅ **Upgrade Completed Successfully**
- Chart upgraded from 70.3.0 → 78.5.0
- App version upgraded from v0.81.0 → v0.86.1
- All components running on correct nodes (RunAI system nodes)
- Health checks passing
- All monitoring functionality validated

**Key Requirements for Future Upgrades:**
1. Always use explicit values files (never `--reuse-values`)
2. Always add affinity rules for all non-DaemonSet pods
3. Always manually delete StatefulSet pods after upgrade
4. Always run comprehensive health checks before and after
5. Always validate pod placement on correct node types

