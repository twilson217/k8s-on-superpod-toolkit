# GPU Operator Upgrade: v24.9.1 → v25.3.4

**Date:** October 15, 2025  
**Environment:** SuperPod with BCM-managed Kubernetes  
**Reason:** Required for Kubernetes 1.33 compatibility

---

## Pre-Upgrade Status

- **Current Version:** v24.9.1
- **Target Version:** v25.3.4
- **K8s Compatibility:** v24.9.1 supports up to K8s 1.31, v25.3.4 supports K8s 1.29-1.33

---

## Pre-Upgrade Testing

Ran comprehensive health check:

```bash
cd /home/travisw/dev/k8s-on-superpod-toolkit
python3 healthchecks/healthcheck_gpu-operator.py before
```

**Result:** ✅ All 8 tests passed

---

## Upgrade Procedure

### 1. Update Helm Repository

```bash
helm repo update nvidia
```

### 2. Perform Upgrade

```bash
helm upgrade gpu-operator nvidia/gpu-operator \
  --namespace gpu-operator \
  --version v25.3.4 \
  --reuse-values
```

**Note:** Did not use `--disable-openapi-validation` flag. CRD schema changes were backward-compatible, and upgrade completed successfully without it.

### 3. Monitor Rollout

```bash
kubectl get pods -n gpu-operator -w
```

All pods rolled out successfully.

---

## Post-Upgrade Validation

### 1. Health Check

```bash
python3 healthchecks/healthcheck_gpu-operator.py after
```

**Result:** ✅ All 8 tests passed

### 2. Verify ClusterPolicy

```bash
kubectl logs -n gpu-operator -l app=gpu-operator --tail=100 | grep -i "warn\|error\|unknown"
```

**Result:** ✅ No warnings or errors found

### 3. Check Events

```bash
kubectl get events -n gpu-operator --sort-by='.lastTimestamp' | tail -30
```

**Result:** ✅ Some transient `FailedCreatePodSandBox` errors during pod restarts (normal during upgrades), all pods eventually succeeded

---

## Outcome

✅ **Upgrade Successful**

- All GPU Operator pods running
- GPU discovery working
- CUDA workloads executing successfully
- DCGM metrics collection operational
- No persistent issues or errors
- No troubleshooting required

---

## Components Tested

1. Environment Information
2. Pod Status (Running/Completed)
3. GPU Node Discovery
4. NVIDIA Device Plugin
5. GPU Feature Discovery
6. DCGM Metrics Exporter
7. Operator Validator
8. CUDA Workload Execution

---

## Notes

- **Driver Management:** Drivers remain managed by DGX OS (not GPU Operator) in SuperPod environment
- **Run:AI Compatibility:** No impact to Run:AI workloads
- **Network Operator:** No changes required (already v25.7.0)

---

**Status:** ✅ Complete - Ready for Kubernetes 1.33 upgrade

