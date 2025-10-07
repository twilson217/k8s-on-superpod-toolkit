# Kubernetes on SuperPOD Toolkit

This repository contains tools and scripts for managing a SuperPOD customer environment running RunAI and Kubernetes.

## Environment Discovery Script

### `pre-upgrade-snapshot.py`

A comprehensive Python-based discovery script that captures a complete snapshot of the Kubernetes and RunAI environment in Markdown format with a table of contents.

**Usage:**
```bash
./pre-upgrade-snapshot.py
```

Or with Python directly:
```bash
python3 pre-upgrade-snapshot.py
```

**Output:**
- Creates `.logs/pre-upgrade-snapshot.md` with complete environment details in Markdown format
- Includes an automatically generated table of contents at the beginning
- Well-structured with sections, subsections, and code blocks
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
├── pre-upgrade-snapshot.py    # Pre-upgrade environment discovery script
├── .logs/                     # Output directory (git-ignored)
│   └── pre-upgrade-snapshot.md
├── .gitignore                 # Git exclusions
└── README.md                  # This file
```

## Naming Convention

Scripts are named to match their output files for easy tracking:
- `pre-upgrade-snapshot.py` → `.logs/pre-upgrade-snapshot.md`

## Requirements

- Python 3.6+
- kubectl configured with cluster access
- helm (if capturing Helm releases)
- Standard Linux utilities (lscpu, free, df, etc.)

## Notes

- The `.logs` directory is excluded from git to prevent committing large snapshot files
- The discovery script is read-only and safe to run at any time
- Secret values are redacted in the output for security
- Output is in Markdown format for easy viewing and sharing
