# Usage Guide for Overview and Snapshot Scripts

This guide explains how to use the `overview.py` and `snapshot.py` scripts for Kubernetes environment documentation.

## Overview Script (`overview.py`)

The overview script collects version information for Kubernetes components, Helm charts, and applications.

### Commands

#### Pre-Upgrade
Collect version information before an upgrade:
```bash
./overview.py --pre
```

**Output files:**
- `.logs/pre-upgrade-overview.md` - Human-readable markdown report
- `.logs/pre-upgrade-overview.json` - Machine-readable data for diff

#### Post-Upgrade
Collect version information after an upgrade:
```bash
./overview.py --post
```

**Output files:**
- `.logs/post-upgrade-overview.md` - Human-readable markdown report
- `.logs/post-upgrade-overview.json` - Machine-readable data for diff

#### Generate Diff
Compare pre and post upgrade states:
```bash
./overview.py --diff
```

**Output file:**
- `.logs/diff-overview.md` - Side-by-side comparison showing what changed

**Requirements:** Both `--pre` and `--post` must be run first.

---

## Snapshot Script (`snapshot.py`)

The snapshot script creates a comprehensive snapshot of the entire Kubernetes environment.

### Commands

#### Pre-Upgrade
Capture complete environment state before an upgrade:
```bash
./snapshot.py --pre
```

**Output file:**
- `.logs/pre-upgrade-snapshot.md` - Comprehensive environment snapshot

#### Post-Upgrade
Capture complete environment state after an upgrade:
```bash
./snapshot.py --post
```

**Output file:**
- `.logs/post-upgrade-snapshot.md` - Comprehensive environment snapshot

#### Generate Diff
Compare pre and post upgrade snapshots:
```bash
./snapshot.py --diff
```

**Output file:**
- `.logs/diff-snapshot.md` - Unified diff showing all changes

**Requirements:** Both `--pre` and `--post` must be run first.

---

## Typical Workflow

### Before Upgrade

1. Run both scripts in pre-upgrade mode:
```bash
./overview.py --pre
./snapshot.py --pre
```

2. Review the generated reports:
   - `.logs/pre-upgrade-overview.md` - Quick version summary
   - `.logs/pre-upgrade-snapshot.md` - Complete environment state

### After Upgrade

1. Run both scripts in post-upgrade mode:
```bash
./overview.py --post
./snapshot.py --post
```

2. Generate diff reports:
```bash
./overview.py --diff
./snapshot.py --diff
```

3. Review the diff reports:
   - `.logs/diff-overview.md` - Version changes summary
   - `.logs/diff-snapshot.md` - Complete environment changes

---

## What Each Script Captures

### Overview Script
- **Kubernetes Components:** etcd, kubectl, kubeadm, kubelet, containerd, CNI
- **Helm Releases:** Chart version and App version
- **Kubernetes Workloads:** Deployments, StatefulSets, DaemonSets with image versions
- **Smart Detection:** Automatically identifies Helm-managed workloads to avoid duplication

### Snapshot Script
- **System Information:** OS, kernel, CPU, memory, disk
- **Kubernetes Cluster:** Nodes, namespaces, API versions
- **All Resources:** Pods, deployments, services, ingresses, configmaps, secrets, etc.
- **Storage:** PVs, PVCs, storage classes
- **RBAC:** Roles, role bindings, service accounts
- **Custom Resources:** CRDs and their instances
- **RunAI Specific:** RunAI namespaces, CRDs, and configurations
- **Hardware:** GPU information if available
- **Metrics:** Node and pod metrics if metrics-server is available

---

## Tips

1. **Run pre-upgrade captures well before the upgrade** to ensure you have a clean baseline
2. **The snapshot script can take several minutes** to complete due to the comprehensive data collection
3. **Diff reports are only generated if both pre and post data exist**
4. **All output files are stored in `.logs/` directory**
5. **JSON files from overview.py are used for diff generation** - don't delete them if you plan to run `--diff`

---

## Help

For more information on command-line options:
```bash
./overview.py --help
./snapshot.py --help
```
