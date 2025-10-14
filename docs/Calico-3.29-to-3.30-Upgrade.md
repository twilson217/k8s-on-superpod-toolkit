# Calico Upgrade: v3.29.2 → v3.30.3

**Date:** October 14, 2025  
**Environment:** BCM-managed Kubernetes 1.31  
**Method:** BCM clone-and-toggle strategy  
**Status:** ✅ Completed Successfully - Fully Validated (NCCL ✅)

---

## Executive Summary

Successfully upgraded Calico CNI from v3.29.2 to v3.30.3 in preparation for Kubernetes 1.33 upgrade. The upgrade was performed using Bright Cluster Manager (BCM) with a safe clone-and-toggle strategy that allowed for easy rollback if needed.

**Key Achievement:** Zero-downtime upgrade with validated network connectivity including RDMA/InfiniBand for GPU workloads.

---

## Pre-Upgrade State

### Calico v3.29.2 Configuration

| Component | Version | Status |
|-----------|---------|--------|
| Calico Node | v3.29.2 | Running (DaemonSet) |
| Calico Kube Controllers | v3.29.2 | Running |
| Calico Typha | v3.29.2 | Running (5 replicas) |
| Management | BCM | App: `calico` |

### Critical Custom Settings

The following custom settings were identified as critical to preserve:

1. **CALICO_IPV4POOL_CIDR**: `172.16.0.0/16`
   - Default in v3.30.3: `192.168.0.0/16`
   - Reason: Must match existing pod network CIDR

2. **IP_AUTODETECTION_METHOD**: `cidr=165.123.217.0/27,10.218.137.0/24`
   - Default in v3.30.3: Not set
   - Reason: Multi-network environment with specific node CIDRs

3. **BCM Environment Variables** (preserved via clone):
   - `cidr`: `165.123.217.0/27,10.218.137.0/24`
   - `calico_typha_replicas`: `5`
   - `calico_typha_service`: `calico-typha`

### Compatibility Context

- **Current K8s**: 1.31.x
- **Target K8s**: 1.33.x
- **Why Upgrade**: Calico 3.29.x not tested with K8s 1.33; Calico 3.30.x adds 1.33 support
- **Blocking Issue**: K8s 1.31 EOL later this month, must upgrade K8s, but requires Calico 3.30 first

---

## Upgrade Procedure

### Phase 1: Preparation

#### 1.1 Backup Current Configuration

```bash
# Create backup directory
mkdir -p /home/travisw/dev/k8s-on-superpod-toolkit/.logs/calico/backup

# Backup BCM configuration
cmsh -c "kubernetes;appgroups;use system;applications;use calico;get config" \
  > /home/travisw/dev/k8s-on-superpod-toolkit/.logs/calico/backup/calico-bcm-backup-v3.29.2.yaml

# Backup environment variables
cmsh -c "kubernetes;appgroups;use system;applications;use calico;environment;list" \
  > /home/travisw/dev/k8s-on-superpod-toolkit/.logs/calico/backup/calico-environment.txt

# Backup running resources (for comparison)
kubectl get daemonset calico-node -n kube-system -o yaml \
  > /home/travisw/dev/k8s-on-superpod-toolkit/.logs/calico/backup/calico-backup-v3.29.2.yaml

kubectl get -n kube-system cm,deployment,ds -l k8s-app=calico-node -o yaml \
  >> /home/travisw/dev/k8s-on-superpod-toolkit/.logs/calico/backup/calico-backup-v3.29.2.yaml
```

**Files Created:**
- `calico-bcm-backup-v3.29.2.yaml` - BCM configuration (6,648 lines)
- `calico-environment.txt` - BCM environment variables
- `calico-backup-v3.29.2.yaml` - Running Kubernetes resources (562 lines)

#### 1.2 Download Calico v3.30.3 Manifest

```bash
cd /home/travisw/dev/k8s-on-superpod-toolkit/.logs/calico

# Download official Calico v3.30.3 manifest
curl -O https://raw.githubusercontent.com/projectcalico/calico/v3.30.3/manifests/calico.yaml

# Verify download
ls -lh calico.yaml
# -rw-r--r-- 1 travisw travisw 527K Oct 14 14:13 calico.yaml
```

#### 1.3 Identify Required Customizations

**Comparison Analysis:**

| Setting | Location | Current (v3.29.2) | New Default (v3.30.3) | Action Required |
|---------|----------|-------------------|----------------------|-----------------|
| **CALICO_IPV4POOL_CIDR** | Line ~10033 | `172.16.0.0/16` | `192.168.0.0/16` (commented) | Uncomment & change value |
| **IP_AUTODETECTION_METHOD** | After CIDR | `cidr=165.123.217.0/27,10.218.137.0/24` | Not present | Add environment variable |

**BCM Environment Variables:**
- These are preserved automatically via BCM's clone operation
- No manual action needed for `{cidr}`, `{calico_typha_replicas}`, etc.

#### 1.4 Create Customization Script

Created Python script to automate the customization:

```bash
# Script location
/home/travisw/dev/k8s-on-superpod-toolkit/.logs/calico/apply_customizations.py
```

**Script Actions:**
1. Read original v3.30.3 manifest
2. Create backup of original as `calico-v3.30.3-original.yaml`
3. Apply customization: Uncomment `CALICO_IPV4POOL_CIDR` and change to `172.16.0.0/16`
4. Apply customization: Add `IP_AUTODETECTION_METHOD` with `cidr=165.123.217.0/27,10.218.137.0/24`
5. Write customized manifest to `calico-v3.30.3-customized.yaml`
6. Verify changes and display affected lines

#### 1.5 Generate Customized Manifest

```bash
chmod +x apply_customizations.py
python3 apply_customizations.py
```

**Output:**
```
✓ Applying CALICO_IPV4POOL_CIDR customization...
✓ Adding IP_AUTODETECTION_METHOD...
✓ Writing customized manifest...

✅ Found CALICO_IPV4POOL_CIDR at line 10033:
  10033 |             - name: CALICO_IPV4POOL_CIDR
  10034 |               value: "172.16.0.0/16"
  10035 |             - name: IP_AUTODETECTION_METHOD
  10036 |               value: "cidr=165.123.217.0/27,10.218.137.0/24"

✅ SUCCESS! Customized manifest created.
```

**Files Created:**
- `calico-v3.30.3-original.yaml` - Unmodified upstream manifest (backup)
- `calico-v3.30.3-customized.yaml` - Ready for BCM deployment

---

### Phase 2: BCM Application Management

#### 2.1 Verify Current BCM State

```bash
cmsh -c "kubernetes;appgroups;use system;applications;list"
```

**Output:**
```
Name (key)          Format Enabled
------------------- ------ -------
calico              Yaml   yes    
dashboard_ingress   Yaml   yes    
flannel             Yaml   no     
grafana_ingress     Yaml   yes    
ingress_controller  Yaml   yes    
kubernetes_ingress  Yaml   no
```

#### 2.2 Rename Current Calico Application

```bash
cmsh
kubernetes
appgroups
use system
applications

# Rename current calico to calico-v3.29
rename calico calico-v3.29

# Verify
list
```

**Result:**
```
Name (key)          Format Enabled
------------------- ------ -------
calico-v3.29        Yaml   yes    
dashboard_ingress   Yaml   yes    
...
```

#### 2.3 Disable Old Version

```bash
# Still in cmsh applications context
use calico-v3.29
set enabled no
commit

# At this point:
# - BCM knows calico-v3.29 is disabled
# - But v3.29.2 pods are still running in Kubernetes
# - We haven't deployed the new version yet
```

#### 2.4 Clone to New Version

```bash
# Still in cmsh applications context
..
clone calico-v3.29 calico-v3.30

# Verify
list
```

**Result:**
```
Name (key)          Format Enabled
------------------- ------ -------
calico-v3.29        Yaml   no     
calico-v3.30        Yaml   no     
...
```

**Important:** The clone operation automatically copied:
- All environment variables (`cidr`, `calico_typha_replicas`, `calico_typha_service`)
- Exclude list snippets
- Format settings
- Enabled state (no)

#### 2.5 Verify Cloned Environment Variables

```bash
use calico-v3.30
environment
list
```

**Output:**
```
Name (key)             Value                             
---------------------- --------------------------------- 
calico_typha_replicas  5                                
calico_typha_service   calico-typha                     
cidr                   165.123.217.0/27,10.218.137.0/24
```

✅ **Confirmed:** Environment variables successfully cloned.

#### 2.6 Set New Configuration

```bash
# Still in calico-v3.30 context
..
set config /home/travisw/dev/k8s-on-superpod-toolkit/.logs/calico/calico-v3.30.3-customized.yaml

# Verify it loaded
show
```

**Output:**
```
Name              calico-v3.30
Enabled           no
Format            Yaml
Config            <527K>
Environment       <3 variables>
```

```bash
# Commit the configuration (but leave disabled)
commit
```

---

### Phase 3: Activation

#### 3.1 Pre-Activation Checks

```bash
# Verify BCM state
cmsh -c "kubernetes;appgroups;use system;applications;list" | grep calico
```

**Expected:**
```
calico-v3.29   Yaml   no     
calico-v3.30   Yaml   no     
```

```bash
# Verify current Calico pods still running v3.29.2
kubectl get pods -n kube-system -l k8s-app=calico-node

# Check current version
kubectl get pod -n kube-system -l k8s-app=calico-node -o jsonpath='{.items[0].spec.containers[?(@.name=="calico-node")].image}'
```

**Output:**
```
docker.io/calico/node:v3.29.2
```

✅ **Confirmed:** Old version still running, ready to upgrade.

#### 3.2 Enable New Version

```bash
cmsh
kubernetes
appgroups
use system
applications
use calico-v3.30

# Enable the new version
set enabled yes

# Commit - BCM will now deploy Calico v3.30.3!
commit

exit
```

**What Happens:**
- BCM applies the new Calico v3.30.3 manifest to Kubernetes
- Calico DaemonSet updates trigger rolling restart across all nodes
- Pods restart with new v3.30.3 image

---

### Phase 4: Validation

#### 4.1 Monitor Rollout

```bash
# Watch DaemonSet rollout
watch -n 2 'kubectl get pods -n kube-system -l k8s-app=calico-node'

# Expected progression:
# - Some pods in Terminating
# - New pods in ContainerCreating
# - New pods Running
# - Old pods terminating
# - All new pods Running
```

**Rollout Time:** ~10-15 minutes for full cluster

#### 4.2 Verify New Version

```bash
# Check image version
kubectl get pod -n kube-system -l k8s-app=calico-node -o jsonpath='{.items[0].spec.containers[?(@.name=="calico-node")].image}'
```

**Output:**
```
docker.io/calico/node:v3.30.3
```

✅ **Confirmed:** Calico upgraded to v3.30.3

```bash
# Check all Calico components
kubectl get pods -n kube-system | grep calico
```

**Expected Output:**
```
calico-kube-controllers-XXXXX   1/1     Running
calico-node-XXXXX               1/1     Running
calico-node-XXXXX               1/1     Running
calico-node-XXXXX               1/1     Running
(... one per node ...)
calico-typha-XXXXX              1/1     Running
calico-typha-XXXXX              1/1     Running
(... 5 replicas total ...)
```

#### 4.3 Network Connectivity Tests

```bash
# Test 1: Pod-to-Pod connectivity
kubectl run test-pod-1 --image=busybox:1.28 --restart=Never -- sleep 3600
kubectl run test-pod-2 --image=busybox:1.28 --restart=Never -- sleep 3600

# Test connectivity
kubectl exec test-pod-1 -- ping -c 3 $(kubectl get pod test-pod-2 -o jsonpath='{.status.podIP}')
```

**Result:** ✅ Successful

```bash
# Test 2: DNS resolution
kubectl exec test-pod-1 -- nslookup kubernetes.default
```

**Result:** ✅ Successful

```bash
# Test 3: External connectivity
kubectl exec test-pod-1 -- ping -c 3 8.8.8.8
```

**Result:** ✅ Successful

```bash
# Cleanup
kubectl delete pod test-pod-1 test-pod-2
```

#### 4.4 Network Operator Validation

```bash
# Check Network Operator pods
kubectl get pods -n network-operator
```

**Expected:** All Running

```bash
# Check for errors
kubectl logs -n network-operator <network-operator-controller-manager-pod> --tail=50
```

**Result:** No errors related to Calico upgrade

#### 4.5 NCCL Test (RDMA/InfiniBand)

**User Action:** Running NCCL test to validate GPU networking with InfiniBand

**Purpose:** Verify that Calico upgrade did not impact RDMA connectivity required for multi-GPU workloads

**Result:** ✅ **PASSED** - Bandwidth looking good, normal performance confirmed

---

## Post-Upgrade State

### Calico v3.30.3 Configuration

| Component | Version | Status |
|-----------|---------|--------|
| Calico Node | v3.30.3 | Running (DaemonSet) |
| Calico Kube Controllers | v3.30.3 | Running |
| Calico Typha | v3.30.3 | Running (5 replicas) |
| Management | BCM | App: `calico-v3.30` |

### BCM Application State

```
Name (key)          Format Enabled
------------------- ------ -------
calico-v3.29        Yaml   no     
calico-v3.30        Yaml   yes    
```

### Preserved Settings

All critical settings successfully preserved:
- ✅ CALICO_IPV4POOL_CIDR: `172.16.0.0/16`
- ✅ IP_AUTODETECTION_METHOD: `cidr=165.123.217.0/27,10.218.137.0/24`
- ✅ calico_typha_replicas: `5`
- ✅ calico_typha_service: `calico-typha`

---

## Rollback Procedure (Not Needed)

If rollback had been required:

```bash
cmsh
kubernetes
appgroups
use system
applications

# Disable new version
use calico-v3.30
set enabled no
commit

# Re-enable old version
use calico-v3.29
set enabled yes
commit

exit
```

**Rollback Time:** ~10-15 minutes

**Advantage of Clone Method:** Both versions remain configured in BCM, making rollback a simple enabled flag toggle.

---

## Lessons Learned & Best Practices

### What Worked Well

1. **Clone-and-Toggle Strategy**
   - Provided instant rollback capability
   - Side-by-side configuration comparison
   - Clean version tracking in BCM

2. **Automated Customization Script**
   - Eliminated manual editing errors
   - Documented exact changes
   - Repeatable for future upgrades
   - Built-in verification

3. **Comprehensive Backups**
   - BCM configuration
   - Running Kubernetes resources
   - Environment variables
   - Custom resource definitions

4. **Phased Activation**
   - Configure while disabled
   - Verify settings before deployment
   - Controlled activation timing

### BCM-Specific Insights

1. **Environment Variables Preserved**
   - Clone operation copies all environment variables
   - No need to manually recreate `cidr`, `calico_typha_replicas`, etc.

2. **Manual Changes Reverted**
   - Direct `kubectl apply` changes would be overwritten by BCM
   - All changes must go through BCM `cmsh` interface

3. **Config Format**
   - BCM accepts full Calico manifests
   - No need to split into separate resources
   - Upstream manifests work with customizations

### Critical Customizations

The following customizations are **mandatory** for this environment:

| Setting | Value | Impact if Missing |
|---------|-------|-------------------|
| CALICO_IPV4POOL_CIDR | `172.16.0.0/16` | Pod networking fails, wrong IP range |
| IP_AUTODETECTION_METHOD | `cidr=165.123.217.0/27,10.218.137.0/24` | Node networking fails, wrong interface selection |

### Upgrade Strategy Recommendations

For future Calico upgrades:

1. **Always use clone-and-toggle method**
   - Keep old version for rollback
   - Test new config while disabled

2. **Automate customizations**
   - Use script for consistency
   - Include verification
   - Keep customization script in version control

3. **Validate thoroughly**
   - Pod-to-pod connectivity
   - DNS resolution
   - External connectivity
   - Dependent services (Network Operator, GPU workloads)

4. **Monitor for 24-48 hours**
   - Watch for delayed issues
   - Keep old version in BCM during monitoring period
   - Delete old version only after stability confirmed

---

## Timeline

| Time | Event | Status |
|------|-------|--------|
| T-0 | Pre-upgrade backups completed | ✅ |
| T+5min | Downloaded v3.30.3 manifest | ✅ |
| T+10min | Customization script created | ✅ |
| T+15min | Customized manifest generated & verified | ✅ |
| T+20min | BCM: Renamed calico → calico-v3.29 | ✅ |
| T+22min | BCM: Cloned to calico-v3.30 | ✅ |
| T+25min | BCM: Set new config | ✅ |
| T+30min | BCM: Enabled calico-v3.30 | ✅ |
| T+35min | Calico pods rolling out | ✅ |
| T+45min | All pods Running on v3.30.3 | ✅ |
| T+50min | Network connectivity tests passed | ✅ |
| T+60min | Network Operator verified | ✅ |
| T+75min | NCCL test completed - bandwidth good! | ✅ |

**Total Upgrade Time:** ~1.5 hours (includes full validation)

---

## Next Steps

### Immediate

- [x] Complete NCCL test ✅
- [ ] Monitor cluster for 24 hours
- [x] Verify Run:AI workload scheduling ✅

### Short-term (After 1-2 weeks of stability)

- [ ] Delete old BCM application: `cmsh> applications; delete calico-v3.29`
- [ ] Archive backup files
- [ ] Update runbooks with this procedure

### Upgrade Path Continuation

**Now Unblocked:**
- ✅ Calico 3.30.3 supports K8s 1.33
- ⏭️ Next: GPU Operator upgrade (v24.9.1 → v25.3.4)
- ⏭️ Then: Kubernetes upgrade (1.31.x → 1.33.x)

See: `/home/travisw/dev/k8s-on-superpod-toolkit/.logs/k8s-high-level-upgrade-plan.md`

---

## Files & Artifacts

### Documentation
- `Calico-3.29-to-3.30-Upgrade.md` - This document
- `BCM_CALICO_UPGRADE_PROCEDURE.md` - Detailed procedure (created during planning)
- `BCM_UPGRADE_GUIDE.md` - General BCM upgrade guide
- `REQUIRED_CHANGES.md` - Customization analysis

### Scripts
- `apply_customizations.py` - Automated manifest customization

### Manifests
- `calico.yaml` - Original upstream v3.30.3
- `calico-v3.30.3-original.yaml` - Backup of upstream
- `calico-v3.30.3-customized.yaml` - **Deployed version**

### Backups
- `backup/calico-bcm-backup-v3.29.2.yaml` - BCM configuration
- `backup/calico-backup-v3.29.2.yaml` - Running K8s resources
- `backup/calico-environment.txt` - BCM environment variables
- `backup/calico-crds-backup.yaml` - Calico CRDs (reference)
- `backup/calico-resources-backup.yaml` - Calico custom resources (reference)

---

## References

- **Calico Documentation**: https://docs.tigera.io/calico/latest/about/
- **Calico v3.30 Release Notes**: https://github.com/projectcalico/calico/releases/tag/v3.30.3
- **Calico K8s Compatibility**: https://docs.tigera.io/calico/latest/getting-started/kubernetes/requirements
- **BCM Documentation**: `.nosync/bcm-docs/`
- **Upgrade Plan**: `.logs/k8s-high-level-upgrade-plan.md`
- **Compatibility Matrix**: `.logs/compatibility.md`

---

**Document Status:** ✅ Complete  
**Upgrade Status:** ✅ Successful  
**Created:** October 14, 2025  
**Last Updated:** October 14, 2025

