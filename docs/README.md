# Upgrade Documentation

This directory contains detailed upgrade documentation for Kubernetes infrastructure components.

## Completed Upgrades

### Network Operator
- **File:** `NetworkOperator-24.7.0-to-25.7.0-Upgrade.md`
- **Date:** October 14, 2025
- **Upgrade:** v24.7.0 → v25.7.0
- **Status:** ✅ Complete

### Calico CNI
- **File:** `Calico-3.29-to-3.30-Upgrade.md`
- **Date:** October 14, 2025
- **Upgrade:** v3.29.2 → v3.30.3
- **Method:** BCM clone-and-toggle strategy
- **Status:** ✅ Complete

### GPU Operator
- **File:** `GpuOperator-24.9-to-25.3-Upgrade.md`
- **Date:** October 15, 2025
- **Upgrade:** v24.9.1 → v25.3.4
- **Status:** ✅ Complete

### ingress-nginx
- **File:** `IngressNginx-1.12-to-1.13-Upgrade.md`
- **Date:** October 15, 2025
- **Upgrade:** v1.12.1 → v1.13.3
- **Method:** BCM clone-and-toggle strategy
- **Status:** ✅ Complete
- **Notes:** Fixed ClusterIP/NodePort issue and added nodeAffinity

### Training Operator
- **File:** `TrainingOperator-1.8-to-1.9-Upgrade.md` *(to be created)*
- **Date:** October 15, 2025
- **Upgrade:** v1-855e096 → v1.9.2
- **Status:** ✅ Complete
- **Notes:** Run:AI prerequisite, required server-side apply with force-conflicts

### VAST CSI Driver
- **File:** `VastCSI-2.6.1-to-2.6.3-Upgrade.md`
- **Date:** October 15, 2025
- **Upgrades:** 
  - snapshot-controller: v5.0.1 → v7.0.1 (image v6.3.1)
  - VAST CSI: v2.6.1 → v2.6.3
- **Status:** ✅ Complete
- **Notes:** Included snapshot-controller upgrade per VAST CSI 2.6 requirements

### Kubernetes Control Plane
- **File:** `Kubernetes-1.31-to-1.32-Upgrade.md`
- **Date:** October 20, 2025
- **Upgrade:** v1.31.9 → v1.32.9
- **Status:** ✅ Complete
- **Critical Issues:**
  - kube-apiserver manifest fixes required (etcd-servers, feature gates)
  - Tigera Operator conflict with BCM Calico management
  - LoadBalancer services disappeared during upgrade
  - TLS certificate reconfiguration required via `cm-kubernetes-setup`
- **Notes:** 
  - **BCM Support Limitation:** Do NOT upgrade beyond 1.32 until BCM releases tooling with 1.33 support
  - Verified with BCM support that `cm-kubernetes-setup` supports up to v1.32.x only

## BCM-Specific Documentation

### Kubernetes Control Plane Upgrades in BCM Environments
- **File:** `BCM-Kubernetes-Upgrade-Requirements.md`
- **Purpose:** Critical BCM-specific requirements for Kubernetes control plane upgrades
- **Key Topics:**
  - Updating BCM Kubernetes version metadata (REQUIRED post-upgrade step)
  - Software image management for compute nodes
  - Supported version checking
  - Ingress certificate reconfiguration
  - BCM vs. standard Kubernetes upgrade differences
- **Status:** Reference documentation extracted from BCM Containerization Manual

## Upcoming Upgrades

### Next Steps
1. Other component upgrades (lws downgrade - deferred)
2. ~~Kubernetes Control Plane upgrade to v1.33~~ - **NOT SUPPORTED**
   - **BCM Limitation:** `cm-kubernetes-setup` only supports up to Kubernetes 1.32.x
   - Confirmed with BCM support - do not attempt 1.33 upgrade
   - Staying on v1.32.9 until BCM releases updated tooling

## Documentation Standards

Each upgrade document includes:
- Executive summary
- Pre-upgrade state
- Complete procedure with commands
- Validation steps
- Post-upgrade state
- Rollback procedure
- Lessons learned
- Timeline and artifacts

