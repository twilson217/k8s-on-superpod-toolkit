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

## Upcoming Upgrades

See `.logs/todo-list.md` for the complete Kubernetes 1.33 upgrade plan.

### Next Steps
1. GPU Operator (v24.9.1 → v25.3.4)
2. Other component upgrades (ingress-nginx, snapshot-controller, training-operator, lws)
3. Kubernetes (v1.31.9 → v1.33.x)

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

