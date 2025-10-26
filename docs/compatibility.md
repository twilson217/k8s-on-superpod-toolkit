# Kubernetes 1.33 Upgrade Compatibility Matrix

**Purpose:** Determine upgrade order for all applications based on K8s 1.31.9 and 1.33.x compatibility

**Legend:**
- ✅ = Compatible / Verified
- ❌ = Not Compatible / Not Supported
- ⚠️ = Unknown / Needs Verification
- 🔄 = Must Upgrade
- ⏸️ = Can Stay / Optional

---

## Upgrade Strategy Decision Logic

| Current on 1.33? | Latest on 1.31? | Action Required | Timing |
|------------------|-----------------|-----------------|--------|
| ✅ Yes | ✅ Yes | ⏸️ Optional - can upgrade before or after K8s | Flexible |
| ✅ Yes | ❌ No | ⏸️ Stay on current until after K8s | After K8s |
| ❌ No | ✅ Yes | 🔄 **MUST upgrade BEFORE K8s** | Before K8s |
| ❌ No | ❌ No | 🔄 **BLOCKED - need compatible version** | Critical |

---

## Core Infrastructure Components

### CNI & Network Layer

| Component | Current Ver | Latest Ver | Current→1.33 | Latest→1.31 | Action | Priority | Notes |
|-----------|-------------|------------|--------------|-------------|--------|----------|-------|
| **Calico CNI** | v3.30.3 | v3.30.3 | ✅ Yes | ✅ Yes | ⏸️ Stay as-is | Done ✅ | Upgraded via BCM (Oct 14) |
| **Network Operator (NVIDIA)** | v25.7.0 | v25.7.0 | ✅ Yes | ✅ Yes | ⏸️ Stay as-is | Done ✅ | Upgraded (Oct 14) |

### GPU Infrastructure

| Component | Current Ver | Latest Ver | Current→1.33 | Latest→1.31 | Action | Priority | Notes |
|-----------|-------------|------------|--------------|-------------|--------|----------|-------|
| **GPU Operator (NVIDIA)** | v25.3.4 | v25.3.4 | ✅ Yes (1.29-1.33) | ✅ Yes (1.29-1.33) | ⏸️ Stay as-is | Done ✅ | Upgraded (Oct 15) |

---

## Helm-Managed Applications

### Observability & Monitoring

| Application | Namespace | Current Ver | Latest Ver | Current→1.33 | Latest→1.31 | Action | Priority | Notes |
|-------------|-----------|-------------|------------|--------------|-------------|--------|----------|-------|
| **kube-prometheus-stack** | prometheus | 70.3.0 | ⚠️ Check latest | ⚠️ Likely yes | ⚠️ Likely yes | ⏸️ Likely OK / Optional upgrade | P2 | Operator v0.81.0 (2024). Says "K8s 1.19+". Recommend verify or upgrade to latest |
| **metrics-server** | kube-system | 3.12.2 (app: v0.7.2) | v0.8.x | ✅ Yes (1.27+) | ✅ Yes (1.31+) | ⏸️ Stay as-is | Done ✅ | v0.7.x supports K8s 1.27+, compatible with 1.31 & 1.33 |
| **kube-state-metrics** | kube-system | 5.31.0 (app: v2.15.0) | 6.3.0 (app: v2.17.0) | ⚠️ Works but not optimal | ✅ Yes | 🔄 **Upgrade to v2.17.0** | **P1 - HIGH** | **Current v2.15.0 uses client-go v1.32 (works with K8s 1.31 but not optimal for 1.33). Target v2.17.0 uses client-go v1.33 (proper match).** Upgrade before K8s 1.33 for optimal compatibility. Matrix: v2.15→K8s 1.32, v2.17→K8s 1.33. Healthcheck: `healthcheck_kube-state-metrics.py` https://github.com/kubernetes/kube-state-metrics |

### Run:AI Platform ✅ ALL COMPATIBLE

| Application | Namespace | Current Ver | Latest Ver | Current→1.33 | Latest→1.31 | Action | Priority | Notes |
|-------------|-----------|-------------|------------|--------------|-------------|--------|----------|-------|
| **runai-backend** | runai-backend | 2.22.47 | 2.22.47+ | ✅ Yes | ✅ Yes | ⏸️ Stay as-is | Done ✅ | Controls 29 workloads - compatible with 1.31 & 1.33 |
| **runai-cluster** | runai | 2.22.47 | 2.22.47+ | ✅ Yes | ✅ Yes | ⏸️ Stay as-is | Done ✅ | Controls 31 workloads - compatible with 1.31 & 1.33 |

**Run:AI Managed Workloads (60 total):**

<details>
<summary>runai-backend namespace (29 workloads) - All Helm-managed ✅</summary>

- keycloak
- runai-backend-assets-service
- runai-backend-audit-service
- runai-backend-authorization
- runai-backend-backend
- runai-backend-cli-exposer
- runai-backend-cluster-service
- runai-backend-datavolumes
- runai-backend-frontend
- runai-backend-grafana
- runai-backend-identity-manager
- runai-backend-k8s-objects-tracker
- runai-backend-metrics-service
- runai-backend-nats
- runai-backend-notifications-proxy
- runai-backend-notifications-service
- runai-backend-org-unit-helper
- runai-backend-org-unit-service
- runai-backend-policy-service
- runai-backend-postgresql
- runai-backend-redoc
- runai-backend-tenants-manager
- runai-backend-thanos-query
- runai-backend-thanos-receive
- runai-backend-traefik
- runai-backend-workloads
- runai-backend-workloads-helper
</details>

<details>
<summary>runai namespace (31 workloads) - All controlled by runai-cluster chart ✅</summary>

- accessrule-controller
- assets-sync
- binder
- cluster-api
- cluster-redis
- cluster-sync
- engine-admission
- engine-operator
- external-workload-integrator
- inference-workload-controller
- init-ca
- metrics-exporter
- nodepool-controller
- pod-group-assigner
- pod-group-controller
- pod-grouper
- prometheus-runai
- queue-controller
- researcher-service
- runai-admission-controller
- runai-agent
- runai-container-toolkit
- runai-job-controller
- runai-node-exporter
- runai-operator
- runai-project-controller
- runai-scheduler-default
- shared-objects-controller
- status-updater
- workload-controller
- workload-exporter
- workload-overseer
</details>

### Networking & Load Balancing

| Application | Namespace | Current Ver | Latest Ver | Current→1.33 | Latest→1.31 | Action | Priority | Notes |
|-------------|-----------|-------------|------------|--------------|-------------|--------|----------|-------|
| **metallb** | metallb-system | 0.15.2 | 0.15.2 | ✅ Yes | ✅ Yes | ⏸️ Stay as-is | Done ✅ | Latest version, compatible with 1.31 & 1.33 |

### Storage

| Application | Namespace | Current Ver | Latest Ver | Current→1.33 | Latest→1.31 | Action | Priority | Notes |
|-------------|-----------|-------------|------------|--------------|-------------|--------|----------|-------|
| **local-path-provisioner** | cm | 0.0.31 | N/A | N/A | N/A | 🔵 BCM-managed | Out of scope | Managed by apt/BCM, updated via BCM upgrades, not K8s upgrade |
| **vast-csi** | vast-csi | 2.6.3 | 2.6.3 | ✅ Yes (1.22-1.34) | ✅ Yes (1.22-1.34) | ⏸️ Stay as-is | Done ✅ | **Upgraded to v2.6.3** with snapshot-controller v7.0.1. Supports K8s 1.22-1.34, fully compatible. |

### Workload Management

| Application | Namespace | Current Ver | Latest Ver | Current→1.33 | Latest→1.31 | Action | Priority | Notes |
|-------------|-----------|-------------|------------|--------------|-------------|--------|----------|-------|
| **lws (LeaderWorkerSet)** | lws-system | v0.7.0 | **v0.6.2**<br>(Run:AI required) | ⚠️ Wrong version | ✅ Yes | 🔄 **Downgrade to v0.6.2** | **P1 - HIGH** | **Run:AI prerequisite** - Current v0.7.0 is newer, but **Run:AI requires v0.6.2 specifically**. v0.6.2 supports K8s 1.26+ (compatible with 1.31 & 1.33). Downgrade to match Run:AI requirement. |

### Dashboard & UI

| Application | Namespace | Current Ver | Latest Ver | Current→1.33 | Latest→1.31 | Action | Priority | Notes |
|-------------|-----------|-------------|------------|--------------|-------------|--------|----------|-------|
| **kubernetes-dashboard** | kubernetes-dashboard | 7.11.1 | v7.13.0 (latest) | ❌ No (only up to 1.32) | ✅ Yes | ⏸️ **Accept Breakage** | **P5 - Low** | Latest v7.13.0 only supports K8s up to 1.32. **NO version supports K8s 1.33 yet**. **DECISION:** Keep dashboard, accept it will break after K8s 1.33 upgrade. Not actively used (no access logs), so breakage is acceptable. Can upgrade when K8s 1.33 support is added. Check: https://github.com/kubernetes/dashboard |

### Access Control

| Application | Namespace | Current Ver | Latest Ver | Current→1.33 | Latest→1.31 | Action | Priority | Notes |
|-------------|-----------|-------------|------------|--------------|-------------|--------|----------|-------|
| **permissions-manager** | cm | 0.6.3 | N/A | N/A | N/A | 🔵 BCM-managed | Out of scope | Managed by apt/BCM (cm-kubernetes-permissions-manager) |

---

## Kubernetes-Managed Applications (Non-Helm)

### Ingress & Service Mesh

| Application | Namespace | Current Ver | Latest Ver | Current→1.33 | Latest→1.31 | Action | Priority | Notes |
|-------------|-----------|-------------|------------|--------------|-------------|--------|----------|-------|
| **ingress-nginx-controller** | ingress-nginx | v1.13.3 | v1.13.3 | ✅ Yes (1.29-1.33) | ✅ Yes (1.29-1.33) | ⏸️ Stay as-is | Done ✅ | Upgraded via BCM (Oct 15) |

### Knative Serving

| Application | Namespace | Current Ver | Latest Ver | Current→1.33 | Latest→1.31 | Action | Priority | Notes |
|-------------|-----------|-------------|------------|--------------|-------------|--------|----------|-------|
| **knative-serving** | knative-serving | 1.18.1 | 1.18.x | ✅ Yes | ✅ Yes | ⏸️ Stay as-is | Done ✅ | v1.18 is latest compatible with Run:AI, works with K8s 1.31 & 1.33 |
| **kourier (net-kourier)** | knative-serving | 1.18.0 | 1.18.x | ✅ Yes | ✅ Yes | ⏸️ Stay as-is | Done ✅ | Follows Knative 1.18 compatibility |
| **3scale-kourier-gateway** | kourier-system | envoy:v1.34 | envoy:v1.34 | ✅ Yes | ✅ Yes | ⏸️ Stay as-is | Done ✅ | Envoy v1.34 compatible, part of Knative 1.18 |

### ML/AI Operators

| Application | Namespace | Current Ver | Latest Ver | Current→1.33 | Latest→1.31 | Action | Priority | Notes |
|-------------|-----------|-------------|------------|--------------|-------------|--------|----------|-------|
| **training-operator (Kubeflow)** | kubeflow | v1-855e096<br>Image: `kubeflow/training-operator:v1-855e096` | **v1.9.2**<br>(Run:AI required) | ⚠️ Outdated | ✅ Yes | 🔄 **Upgrade to v1.9.2** | **P1 - CRITICAL** | **Run:AI prerequisite** - Current is commit-based version. **Run:AI requires v1.9.2 specifically**. Since Run:AI 2.22.47 supports K8s 1.33 and requires v1.9.2, the target version is compatible. Upgrade before or with K8s 1.33. Docs: https://github.com/kubeflow/training-operator |
| **mpi-operator** | mpi-operator | 0.6.0<br>Image: `mpioperator/mpi-operator:0.6.0` | v0.6.0<br>(latest) | ✅ Yes | ✅ Yes | ⏸️ Stay as-is | Done ✅ | **Run:AI prerequisite** - v0.6.0 is latest version and **confirmed compatible with K8s 1.33**. No upgrade needed. Repo: https://github.com/kubeflow/mpi-operator |

### Storage Controllers

| Application | Namespace | Current Ver | Latest Ver | Current→1.33 | Latest→1.31 | Action | Priority | Notes |
|-------------|-----------|-------------|------------|--------------|-------------|--------|----------|-------|
| **snapshot-controller** | kube-system | v7.0.1 (image v6.3.1) | v8.2.x (latest) | ✅ Yes | ✅ Yes | ⏸️ Stay as-is | Done ✅ | K8s CSI SIG project. **Upgraded to v7.0.1 as part of VAST CSI upgrade** - VAST CSI 2.6 documentation specifically requires external-snapshotter v7.0.1. v7.0.1 supports K8s 1.20-1.33. Note: Project version v7.0.1 uses image v6.3.1. Aligned with VAST, not latest. Repo: https://github.com/kubernetes-csi/external-snapshotter |
| **objectstorage-controller** | default | v0.1.1 (Oct 2022) | N/A | N/A | N/A | ⏸️ Not in use | P4 - Optional | COSI controller - very old version, no COSI resources in cluster, consider removal |

---

## Core Kubernetes Components

| Component | Current Ver | K8s 1.31 | K8s 1.33 | Notes |
|-----------|-------------|----------|----------|-------|
| **CoreDNS** | v1.11.3 | ✅ | ✅ | Managed by kubeadm |
| **kube-proxy** | v1.31.9 | ✅ | Auto-upgrade | Follows K8s version |
| **etcd** | v3.5.15 | ✅ Yes (requires 3.5.13+) | ✅ Yes (requires 3.5.13+) | 🔵 BCM-managed via apt - compatible, no upgrade needed |

---

## Verification Checklist

### Before Starting Any Upgrades:
- [ ] Check Calico 3.30.x latest stable version
- [ ] Verify GPU Operator 25.3.4 B200 GPU compatibility
- [ ] Check all Helm release latest versions
- [ ] Review each application's K8s compatibility matrix
- [ ] Test in staging environment if available

### Application-Specific Checks:
- [~] **kube-prometheus-stack**: v70.3.0 with operator v0.81.0 - likely compatible (says "K8s 1.19+"), recommend verify or check for newer chart version
- [x] **metrics-server**: v0.7.2 supports K8s 1.27+ - compatible with both 1.31 & 1.33 ✅
- [x] **ingress-nginx**: v1.12.1 → v1.13.3 required (current only supports up to 1.32)
- [x] **metallb**: v0.15.2 - latest version, compatible with both 1.31 & 1.33 ✅
- [x] **vast-csi**: v2.6.1 - v2.6.x supports K8s 1.22-1.34, compatible with both 1.31 & 1.33 ✅ (optional upgrade to 2.6.3)
- [x] **Knative Serving v1.18**: Latest compatible with Run:AI, works with K8s 1.31 & 1.33 ✅
- [x] **lws (LeaderWorkerSet)**: **Run:AI prerequisite** - Current v0.7.0 is newer, **must downgrade to v0.6.2** (Run:AI requirement) ⚠️
- [x] **training-operator**: **CRITICAL Run:AI prerequisite** - Current version outdated, **must upgrade to v1.9.2** (Run:AI requirement) ⚠️
- [x] **mpi-operator**: **CRITICAL Run:AI prerequisite** - v0.6.0 is latest and compatible with K8s 1.33 ✅
- [ ] **kube-state-metrics**: v2.15.0 → v2.17.0 - Should upgrade (v2.15 uses client-go v1.32, v2.17 uses client-go v1.33 for optimal K8s 1.33 support) 🔄
- [x] **snapshot-controller**: v5.0.1 → v7.0.1 - **Upgraded as part of VAST CSI upgrade** (v7.0.1 required by VAST CSI 2.6) ✅
- [x] **kubernetes-dashboard**: v7.13.0 (latest) NOT compatible with K8s 1.33 - **Accepted breakage** (not actively used, can fix later)

---

## Priority Levels

- **P0 - CRITICAL**: Must be done before K8s upgrade, blocks upgrade
- **P1 - HIGH**: Should be done before K8s upgrade for stability
- **P2 - MEDIUM**: Important but can be flexible on timing
- **P3 - LOW**: Can be upgraded after K8s if needed
- **P4 - OPTIONAL**: Nice to have, low risk

---

## Progress Summary

**Total Workloads Identified:** 77 applications/workloads
- ✅ **Run:AI (60 workloads):** All compatible via 2.22.47 - DONE
- ✅ **Network Operator:** Already upgraded to v25.7.0 - DONE
- ✅ **metrics-server:** v0.7.2 compatible (supports K8s 1.27+) - DONE
- 🔄 **kube-state-metrics:** v2.15.0 → v2.17.0 - Should upgrade before K8s 1.33 (optimal client-go match)
- ✅ **mpi-operator:** v0.6.0 latest and compatible with K8s 1.33 - DONE
- ✅ **metallb:** v0.15.2 compatible (latest version) - DONE
- ✅ **vast-csi:** v2.6.1 → v2.6.3 upgraded (v2.6.x supports K8s 1.22-1.34) - DONE (Oct 15)
- ✅ **snapshot-controller:** v5.0.1 → v7.0.1 upgraded (required by VAST CSI 2.6) - DONE (Oct 15)
- ✅ **Knative Serving (3 apps):** v1.18 compatible with K8s 1.31 & 1.33, latest compatible with Run:AI - DONE
- 🔵 **etcd:** v3.5.15 compatible (requires 3.5.13+) - BCM-managed, no upgrade needed
- 🔵 **local-path-provisioner:** Managed by BCM via apt - OUT OF SCOPE
- 🔵 **permissions-manager:** Managed by BCM via apt - OUT OF SCOPE
- ⏸️ **objectstorage-controller:** Not actively used, very old version - OPTIONAL (consider removal)
- 🔄 **Calico CNI:** Must upgrade to v3.30.x - REQUIRED BEFORE K8s upgrade
- 🔄 **GPU Operator:** Must upgrade to v25.3.4 - REQUIRED BEFORE K8s upgrade
- 🔄 **ingress-nginx:** Must upgrade to v1.13.3 - REQUIRED BEFORE K8s upgrade
- ✅ **snapshot-controller:** Upgraded to v7.0.1 - DONE (Oct 15, part of VAST CSI upgrade)
- 🔄 **training-operator:** Must upgrade to v1.9.2 - REQUIRED (Run:AI prerequisite, currently outdated)
- 🔄 **lws (LeaderWorkerSet):** Must downgrade to v0.6.2 - REQUIRED (Run:AI prerequisite, current v0.7.0 too new)
- ⏸️ **kubernetes-dashboard:** Will break on K8s 1.33 - **ACCEPTED** (not actively used, can fix post-upgrade)

**Verified/Scoped:** 77 of 77 (100%) ✅ COMPLETE

**BCM-managed (out of scope):** 3 components (etcd, local-path-provisioner, permissions-manager)
**Not actively used:** 1 app (objectstorage-controller)
**Completed Upgrades:** 5 apps (Calico CNI, GPU Operator, ingress-nginx, snapshot-controller, training-operator) ✅
**Deferred:** 1 app (lws downgrade - related to new feature implementation)
**Will break (accepted):** 1 app (kubernetes-dashboard) - Not actively used, breakage acceptable

---

## ✅ DECISION: kubernetes-dashboard - Accepted Breakage

**Issue:** kubernetes-dashboard v7.13.0 (latest) only supports Kubernetes up to v1.32. **No version currently supports K8s 1.33.**

**Usage Analysis:**
- ❌ No user access logs found
- ❌ Zero authentication requests
- ❌ Minimal resource usage (idle)
- ✅ Not actively used

**Decision:** **Keep dashboard, accept it will break after K8s 1.33 upgrade**
- Dashboard is not actively used (confirmed via logs)
- Breakage is acceptable
- Can upgrade dashboard when K8s 1.33 support is added
- No need to remove or wait for update

**Expected Behavior Post-Upgrade:**
- Dashboard pods may error/restart
- Dashboard UI will be non-functional
- No impact on critical services

**Post-Upgrade Action (Optional):**
- Monitor https://github.com/kubernetes/dashboard/releases for K8s 1.33 support
- Upgrade dashboard when compatible version is released

---

## Upgrade Order Summary (Based on Compatibility)

### Phase 1: Pre-K8s Upgrades (MUST DO FIRST)
1. ✅ Network Operator v25.7.0 (already done)
2. ✅ Run:AI 2.22.47 (already compatible - stay as-is)
3. ✅ mpi-operator v0.6.0 (latest version, compatible with K8s 1.33 - stay as-is)
4. 🔄 Calico CNI v3.29.2 → v3.30.x (P0 - CRITICAL, current doesn't support 1.33)
5. 🔄 GPU Operator v24.9.1 → v25.3.4 (P1 - HIGH, current only supports up to 1.31)
6. ✅ ingress-nginx-controller v1.12.1 → v1.13.3 (P1 - HIGH, current only supports up to 1.32) - DONE (Oct 15)
7. ✅ training-operator v1-855e096 → v1.9.2 (P1 - HIGH, Run:AI requires v1.9.2 specifically) - DONE (Oct 15)
8. 🔄 lws (LeaderWorkerSet) v0.7.0 → v0.6.2 (P1 - HIGH, Run:AI requires v0.6.2 - DOWNGRADE) - DEFERRED
9. ✅ snapshot-controller v5.0.1 → v7.0.1 (P2 - MEDIUM, upgraded with VAST CSI per vendor requirements) - DONE (Oct 15)

### Phase 2: Kubernetes Upgrade
- Kubernetes v1.31.9 → v1.33.x

### Phase 3: Post-K8s Upgrades (IF NEEDED)
- [Apps where latest version doesn't support K8s 1.31]
- [Apps where upgrade can wait]

### Phase 4: Optional Upgrades
- [Apps that are compatible in current version]
- [Non-critical updates]

---

## Next Steps

1. **Research Phase**: Go through each "⚠️ TBD" entry and fill in:
   - Latest stable version
   - Current version K8s 1.33 compatibility
   - Latest version K8s 1.31 compatibility
   - Required action and priority

2. **Categorize**: Sort applications into upgrade phases based on compatibility

3. **Plan**: Create detailed upgrade procedures for each phase

4. **Execute**: Follow the phased approach with validation after each step

---

## Notes & References

### Verified Compatibility ✅
- **Run:AI 2.22.47:** Confirmed compatible with K8s 1.31 & 1.33 (60 workloads)
- **Network Operator v25.7.0:** Supports K8s 1.33 (already upgraded)
- **metrics-server v0.7.2:** Supports K8s 1.27+ (compatible with 1.31 & 1.33)
- **metallb v0.15.2:** Latest version, compatible with K8s 1.31 & 1.33
- **vast-csi v2.6.1:** v2.6.x supports K8s 1.22-1.34 (compatible with 1.31 & 1.33)
- **etcd v3.5.15:** K8s 1.31+ requires 3.5.13+ (BCM-managed, no upgrade needed)
- **Knative Serving v1.18 (3 apps):** Latest version compatible with Run:AI, works with K8s 1.31 & 1.33
- **lws v0.7.0:** Latest version, supports K8s 1.26+ (compatible with 1.31 & 1.33)

### ⚠️ Run:AI Prerequisites Status

- **mpi-operator v0.6.0:** ✅ **COMPATIBLE**
  - Image: `mpioperator/mpi-operator:0.6.0`
  - **v0.6.0 is the latest version**
  - **Confirmed compatible with K8s 1.33**
  - No upgrade needed
  - Repo: https://github.com/kubeflow/mpi-operator

- **training-operator v1-855e096:** 🔄 **MUST UPGRADE**
  - Image: `kubeflow/training-operator:v1-855e096`
  - Current: Commit-based version (non-standard release)
  - Target: **v1.9.2** (Run:AI specifically requires this version)
  - Since Run:AI 2.22.47 supports K8s 1.33 and requires v1.9.2, the target version is compatible
  - **ACTION:** Upgrade to v1.9.2 before or with K8s 1.33
  - Docs: https://github.com/kubeflow/training-operator

### Completed Pre-K8s Upgrades ✅
- ✅ **Calico CNI:** v3.29.2 → v3.30.3 (Oct 14, 2025)
- ✅ **GPU Operator:** v24.9.1 → v25.3.4 (Oct 15, 2025)
- ✅ **ingress-nginx:** v1.12.1 → v1.13.3 (Oct 15, 2025)
- ✅ **training-operator:** v1-855e096 → v1.9.2 (Oct 15, 2025)
- ✅ **snapshot-controller:** v5.0.1 → v7.0.1 (Oct 15, 2025 - part of VAST CSI upgrade)
- ✅ **VAST CSI:** v2.6.1 → v2.6.3 (Oct 15, 2025 - upgraded with snapshot-controller)

### Deferred (Related to New Feature) 🔄
- **lws (LeaderWorkerSet):** v0.7.0 → v0.6.2 (Run:AI requires v0.6.2 - DOWNGRADE, deferred per user request)

### Run:AI Workloads Covered ✅
- **runai-backend namespace:** 29 workloads (all Helm-managed)
- **runai namespace:** 31 workloads (all deployed by runai-cluster chart)
- **Total:** 60 workloads can stay as-is through upgrade

### Run:AI Prerequisites (NOT bundled with Run:AI)
- **training-operator (Kubeflow):** Required for Run:AI training jobs
  - Current: v1-855e096 (commit-based, outdated)
  - Target: **v1.9.2** (Run:AI requirement)
  - Status: 🔄 **MUST UPGRADE**
- **lws (LeaderWorkerSet):** Required for Run:AI gang scheduling
  - Current: v0.7.0 (too new)
  - Target: **v0.6.2** (Run:AI requirement)
  - Status: 🔄 **MUST DOWNGRADE**
- **mpi-operator v0.6.0:** Required for Run:AI MPI workloads
  - Status: ✅ **Compatible** (latest version, confirmed K8s 1.33 support)
- **Knative Serving v1.18:** Required for Run:AI serverless features
  - Status: ✅ **Compatible** (latest version compatible with Run:AI)
- **Note:** These are separate installations, NOT included in Run:AI Helm charts

### BCM-Managed Components 🔵
- **etcd v3.5.15:** ✅ Compatible (K8s 1.31+ requires 3.5.13+, you have 3.5.15)
  - Managed via apt/BCM (cm-etcd package)
  - No upgrade needed for K8s 1.31 → 1.33
  - Would only need to upgrade if updating BCM itself
- **local-path-provisioner v0.0.31:** Out of scope for K8s upgrade
  - Managed via apt/BCM
  - Upgraded through BCM update cycle
- **permissions-manager v0.6.3:** Out of scope for K8s upgrade
  - Managed via apt/BCM (cm-kubernetes-permissions-manager package)
  - In `cm` namespace alongside local-path-provisioner
  - Upgraded through BCM update cycle

---

## Key Insights

### VAST CSI & Snapshot-Controller Dependency
The snapshot-controller version must be aligned with VAST CSI driver requirements:
- **VAST CSI 2.6.x requires external-snapshotter v7.0.1 specifically**
- This is documented in: [VAST CSI 2.6 Administrator Guide](https://support.vastdata.com/s/document-item?bundleId=vast-csi-driver-2.6-administrator-s-guide)
- The snapshot-controller image version (v6.3.1) does not match the project version (v7.0.1) - this is expected
- Always check vendor documentation for CSI driver compatibility requirements
- Latest is not always best - vendor-specific requirements take precedence

### BCM Certificate Management (Critical Finding)
In BCM-managed environments, ingress certificate configuration requires special handling:
- Certificates must be configured via `cm-kubernetes-setup` → "Configure Ingress"
- This creates `ingress-server-default-tls` secret in `ingress-nginx` namespace
- Manual `kubectl create secret tls` approach will not work properly
- **Always reconfigure certificates after ingress-nginx upgrades in BCM environments**

---

**Last Updated:** 2025-10-15

