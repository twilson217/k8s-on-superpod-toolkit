# RunAI 2.23 / Kubernetes 1.34 Environment

This repository contains tools and scripts for managing a SuperPOD customer environment running RunAI and Kubernetes.

## Environment Discovery Script

### `discover-environment.sh`

A comprehensive discovery script that captures a complete snapshot of the Kubernetes and RunAI environment.

**Usage:**
```bash
./discover-environment.sh
```

**Output:**
- Creates `.logs/pre-upgrade-snapshot.txt` with complete environment details
- Captures all Kubernetes resources, Helm releases, RunAI configurations, and system information

**What it captures:**
- System information (OS, CPU, memory, disk)
- Kubernetes cluster details (nodes, namespaces, API resources)
- All Helm releases with values and manifests
- RunAI specific configurations and CRDs
- All Kubernetes resources (pods, deployments, services, etc.)
- Storage configuration (PVs, PVCs, storage classes)
- Security & RBAC (roles, bindings, service accounts)
- Network policies and CNI plugin information
- GPU information (NVIDIA)
- Events, metrics, and component status

**Use cases:**
- Pre-upgrade documentation
- Disaster recovery planning
- Configuration auditing
- Troubleshooting reference
- Compliance documentation

## Directory Structure

```
.
├── discover-environment.sh    # Environment discovery script
├── .logs/                     # Output directory (git-ignored)
│   └── pre-upgrade-snapshot.txt
├── .gitignore                 # Git exclusions
└── README.md                  # This file
```

## Notes

- The `.logs` directory is excluded from git to prevent committing large snapshot files
- The discovery script is read-only and safe to run at any time
- Secret values are redacted in the output for security
