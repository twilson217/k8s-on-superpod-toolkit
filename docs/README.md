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

## Upcoming Upgrades

See `.logs/todo-list.md` for the complete Kubernetes 1.33 upgrade plan.

### Next Steps
1. Other component upgrades (snapshot-controller, training-operator, lws)
2. Kubernetes (v1.31.9 → v1.33.x)

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

