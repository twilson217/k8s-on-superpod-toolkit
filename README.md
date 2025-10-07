# RunAI 2.23 / Kubernetes 1.34 Environment

This repository contains tools and scripts for managing a SuperPOD customer environment running RunAI and Kubernetes.

## Environment Discovery Script

### `discover_environment.py`

A comprehensive Python-based discovery script that captures a complete snapshot of the Kubernetes and RunAI environment in Markdown format with a table of contents.

**Usage:**
```bash
./discover_environment.py
```

Or with Python directly:
```bash
python3 discover_environment.py
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
├── discover_environment.py    # Environment discovery script (Python)
├── discover-environment.sh    # Legacy bash script (deprecated)
├── .logs/                     # Output directory (git-ignored)
│   └── pre-upgrade-snapshot.md
├── .gitignore                 # Git exclusions
└── README.md                  # This file
```

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
