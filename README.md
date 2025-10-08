# Kubernetes on SuperPOD Toolkit

This repository contains tools and scripts for managing a SuperPOD customer environment running RunAI and Kubernetes.

## Environment Discovery Script

### `snapshot.py`

A comprehensive Python-based discovery script that captures a complete snapshot of the Kubernetes and RunAI environment in Markdown format with a table of contents.

**Usage:**
```bash
./snapshot.py
```

Or with Python directly:
```bash
python3 snapshot.py
```

**Output:**
- Creates `.logs/snapshot.md` with complete environment details in Markdown format
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

## NCCL Test Script

### `b200_runai_nccl_test.py`

A Python script for running multi-node NCCL (NVIDIA Collective Communications Library) tests in a RunAI environment. The script automatically submits an MPI job and captures logs from all pods.

**Usage:**
```bash
python3 b200_runai_nccl_test.py --project <PROJECT_NAME> --nodes <NUM_NODES>
```

**Example:**
```bash
python3 b200_runai_nccl_test.py --project test --nodes 2
```

**What it does:**
- Configures the RunAI project
- Submits an MPI job with the specified number of worker nodes
- Waits for all pods (launcher + workers) to be created
- Automatically captures logs from all pods to `.logs/` directory
- Creates timestamped log files for each pod

**Output:**
- Log files in `.logs/` with format: `nccl-test1_{pod_name}_{timestamp}.log`
- Real-time log streaming in background threads

### Manual Command (Copy & Paste Alternative)

If you prefer to run the `runai mpi submit` command directly without the Python script:

```bash
# First, configure your project
runai config project <PROJECT_NAME>

# Then submit the NCCL test job
runai mpi submit nccl-test1 \
  -i docker.io/deepops/nccl-tests:2312 \
  --workers 2 \
  --gpu-devices-request 8 \
  --extended-resource nvidia.com/resibp24s0=1 \
  --extended-resource nvidia.com/resibp64s0=1 \
  --extended-resource nvidia.com/resibp79s0=1 \
  --extended-resource nvidia.com/resibp94s0=1 \
  --extended-resource nvidia.com/resibp154s0=1 \
  --extended-resource nvidia.com/resibp192s0=1 \
  --extended-resource nvidia.com/resibp206s0=1 \
  --extended-resource nvidia.com/resibp220s0=1 \
  --large-shm \
  --stdin \
  --tty \
  --master-command mpirun \
  --master-args "--allow-run-as-root --bind-to none -map-by slot -np 16 -mca pml ob1 -mca btl self,tcp all_reduce_perf_mpi -b 1G -e 16G -f 2 -n 100 -g 1" \
  --image-pull-policy IfNotPresent \
  --annotation k8s.v1.cni.cncf.io/networks=default/ibp192s0,default/ibp206s0,default/ibp154s0,default/ibp220s0,default/ibp24s0,default/ibp64s0,default/ibp79s0,default/ibp94s0 \
  -e CUDA_DEVICE_MAX_CONNECTIONS=1 \
  -e NCCL_SOCKET_IFNAME=eth0 \
  -e NCCL_ASYNC_ERROR_HANDLING=1 \
  -e NCCL_IB_QPS_PER_CONNECTION=2 \
  -e NCCL_IB_SPLIT_DATA_ON_QPS=0
```

### Command Options Explained

#### RunAI Job Configuration
- **`nccl-test1`** - Job name (can be changed to any unique identifier)
- **`-i docker.io/deepops/nccl-tests:2312`** - Container image with NCCL test binaries
- **`--workers 2`** - Number of worker nodes (adjust based on your test requirements)
  - Each worker runs on a separate node
  - Total GPUs = workers × 8 (for B200 systems with 8 GPUs per node)
- **`--gpu-devices-request 8`** - Number of GPUs per worker (8 for full node)

#### InfiniBand Resources
- **`--extended-resource nvidia.com/resibp*`** - InfiniBand network interface resources
  - Each line requests one IB HCA (Host Channel Adapter)
  - B200 systems typically have 8 IB interfaces per node (ibp24s0, ibp64s0, etc.)
  - These should match your system's available IB devices
  - Check available resources: `kubectl describe node <node-name>`

#### Container Settings
- **`--large-shm`** - Enables large shared memory (/dev/shm) for inter-process communication
  - Required for NCCL to work efficiently
- **`--stdin`** / **`--tty`** - Allocates a terminal for interactive debugging
- **`--image-pull-policy IfNotPresent`** - Only pulls image if not already cached locally

#### Network Annotation
- **`--annotation k8s.v1.cni.cncf.io/networks=...`** - Attaches secondary network interfaces
  - Maps each InfiniBand device as a network attachment
  - Must match the extended resources requested above

#### MPI Configuration (--master-args)

The `--master-args` parameter contains arguments passed directly to `mpirun`. Here's what each option does:

**MPI Runtime Options:**
- **`--allow-run-as-root`** - Permits running MPI as root user (required in containers)
- **`--bind-to none`** - Disables CPU binding (lets CUDA handle GPU affinity)
- **`-map-by slot`** - Maps MPI processes to available slots (GPUs)
- **`-np 16`** - **[IMPORTANT]** Total number of MPI processes
  - **Calculate as: workers × 8 GPUs**
  - For 2 workers: `-np 16`
  - For 4 workers: `-np 32`
  - Must match total GPU count

**MPI Communication Options:**
- **`-mca pml ob1`** - Use OpenMPI's "ob1" point-to-point messaging layer
- **`-mca btl self,tcp`** - Byte Transfer Layer: use self (loopback) and TCP
  - NCCL handles InfiniBand directly, so MPI uses TCP for control messages

**NCCL Test Parameters:**
- **`all_reduce_perf_mpi`** - The specific NCCL test to run (all-reduce collective operation)
  - Other options: `all_gather_perf`, `broadcast_perf`, `reduce_scatter_perf`
- **`-b 1G`** - **[TWEAK]** Starting buffer size (1 GB)
  - Adjust based on memory: `-b 8M`, `-b 512M`, `-b 2G`
- **`-e 16G`** - **[TWEAK]** Ending buffer size (16 GB)
  - Maximum message size to test
  - Must be ≤ available GPU memory
- **`-f 2`** - **[TWEAK]** Multiplication factor between tests
  - Doubles buffer size each iteration: 1G → 2G → 4G → 8G → 16G
  - Use `-f 4` for fewer iterations, `-f 1.5` for more granular results
- **`-n 100`** - **[TWEAK]** Number of iterations per buffer size
  - More iterations = more accurate but slower
  - Typical range: 20-200 iterations
- **`-g 1`** - GPUs per thread (1 = one GPU per MPI rank)

#### Environment Variables

- **`CUDA_DEVICE_MAX_CONNECTIONS=1`** - Limits CUDA streams for better NCCL performance
- **`NCCL_SOCKET_IFNAME=eth0`** - Primary network interface for NCCL bootstrap
- **`NCCL_ASYNC_ERROR_HANDLING=1`** - Enables async error handling for better debugging
- **`NCCL_IB_QPS_PER_CONNECTION=2`** - **[TWEAK]** Queue pairs per IB connection
  - Higher values (4, 8) can improve bandwidth but use more resources
- **`NCCL_IB_SPLIT_DATA_ON_QPS=0`** - Disables splitting data across QPs (for testing)

### Common Tweaks

**For shorter tests:**
```bash
--master-args "-np 16 ... all_reduce_perf_mpi -b 8M -e 1G -f 2 -n 50 -g 1"
```

**For comprehensive bandwidth testing:**
```bash
--master-args "-np 16 ... all_reduce_perf_mpi -b 8M -e 8G -f 1.5 -n 200 -g 1"
```

**For different NCCL tests:**
```bash
# All-gather test
--master-args "-np 16 ... all_gather_perf_mpi -b 1G -e 16G -f 2 -n 100 -g 1"

# Broadcast test
--master-args "-np 16 ... broadcast_perf_mpi -b 1G -e 16G -f 2 -n 100 -g 1"
```

### Viewing Logs

**With the Python script:**
Logs are automatically captured in `.logs/` directory with timestamped filenames.

**Manual log viewing:**
```bash
# View launcher logs
kubectl logs -f nccl-test1-launcher-<pod-id> -n runai-<project>

# View worker logs
kubectl logs -f nccl-test1-worker-0 -n runai-<project>
kubectl logs -f nccl-test1-worker-1 -n runai-<project>
```

## Directory Structure

```
.
├── b200_runai_nccl_test.py    # NCCL test runner script
├── snapshot.py                # Environment discovery/snapshot script
├── overview.py                # Environment overview script
├── .logs/                     # Output directory (git-ignored)
│   ├── snapshot.md            # Snapshot output
│   └── nccl-test1_*.log       # NCCL test logs (timestamped)
├── .gitignore                 # Git exclusions
└── README.md                  # This file
```

## Naming Convention

Scripts are named to match their output files for easy tracking:
- `snapshot.py` → `.logs/snapshot.md`

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
