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

## Network Operator Health Check Script

### `healthcheck_network-operator.py`

A comprehensive pre-flight check script that validates all NVIDIA Network Operator components required for successful multi-node NCCL tests on B200 systems. **Run this before launching NCCL tests** to ensure your environment is properly configured.

**Usage:**
```bash
# Check specific nodes
python3 healthcheck_network-operator.py --nodes dgx030,dgx031

# Check all GPU nodes automatically
python3 healthcheck_network-operator.py

# Skip SSH-based node checks (useful if passwordless SSH is not configured)
python3 healthcheck_network-operator.py --skip-ssh
```

**What it checks:**

1. **Network Operator Deployment**
   - Helm release status
   - Operator controller pods running
   - NicClusterPolicy exists and is ready

2. **SR-IOV Configuration**
   - SriovNetworkNodeState shows "Succeeded" for all nodes
   - All 8 InfiniBand extended resources available on each node (nvidia.com/resibp*)
   - Each resource has quantity of 8 VFs

3. **NV-IPAM (IP Address Management)**
   - nv-ipam pods running
   - Correct image name (nvidia-k8s-ipam, not nv-ipam)
   - 8 IPPools configured with perNodeBlockSize=8

4. **RDMA Shared Device Plugin**
   - rdma-shared-dp pods running on all GPU nodes
   - rdma_shared_device_a resources available (required for NCCL)

5. **Secondary Network Components**
   - Multus CNI deployed (required for network attachments)
   - CNI plugins deployed
   - Whereabouts IPAM deployed

6. **Network Attachment Definitions**
   - All 8 NADs present in network-operator namespace
   - Correct naming convention (ibp*s0-sriovnet suffix)

7. **Node-Level Checks (via SSH)**
   - Virtual Functions activated on all 8 IB interfaces (sriov_numvfs=8)
   - InfiniBand ports in Active state with valid LIDs
   - No ports showing base lid 0xffff (disconnected from fabric)

**Output:**
- Color-coded status indicators (✅ PASS, ⚠️ WARN, ❌ FAIL)
- Detailed information for each check
- Clear summary of any issues found
- Exit code 0 if all checks pass, 1 if any failures

**Example Output:**
```
================================================================================
NVIDIA Network Operator Health Check for B200 NCCL Workloads
================================================================================

Target Nodes: dgx030, dgx031

================================================================================
1. Network Operator Deployment
================================================================================
✅ PASS Network Operator deployed
    Chart: network-operator-25.7.0, Status: deployed
✅ PASS Network Operator pods running (2/2)
✅ PASS NicClusterPolicy is ready
    state-multus-cni: ready
    state-rdma-device-plugin: ready
    state-nv-ipam-cni: ready

================================================================================
Health Check Summary
================================================================================

✅ ALL CHECKS PASSED

The Network Operator is properly configured for NCCL workloads.
You can proceed with running b200_runai_nccl_test.py
```

**When to use:**
- Before running NCCL tests to avoid failures
- After Network Operator upgrades
- After adding new nodes to the cluster
- When troubleshooting NCCL performance issues
- To validate SR-IOV and InfiniBand configuration

**Prerequisites:**
- kubectl configured with cluster admin access
- Passwordless SSH to GPU nodes (unless using --skip-ssh)
- Python 3.6+

## NCCL Test Script

### `b200_runai_nccl_test.py`

A Python script for running multi-node NCCL (NVIDIA Collective Communications Library) tests on NVIDIA B200 systems in a RunAI environment. The script automatically submits an MPI job and captures logs from all pods.

**Optimized for B200 Performance:**
- Achieves **388.66 GB/s** average bus bandwidth on 2-node (16 GPU) tests
- Enables InfiniBand with SHARP (Scalable Hierarchical Aggregation and Reduction Protocol)
- Utilizes all 8 InfiniBand adapters per B200 node
- Configured with proven NCCL and UCX environment variables

**Usage:**
```bash
# Normal mode (default - debug output disabled for best performance)
python3 b200_runai_nccl_test.py --project <PROJECT_NAME> --nodes <NUM_NODES>

# Debug mode (enables NCCL_DEBUG=INFO for troubleshooting)
python3 b200_runai_nccl_test.py --project <PROJECT_NAME> --nodes <NUM_NODES> --debug
```

**Examples:**
```bash
# Run 2-node NCCL test (16 GPUs total)
python3 b200_runai_nccl_test.py --project test --nodes 2

# Run with debug output enabled for troubleshooting
python3 b200_runai_nccl_test.py --project test --nodes 2 --debug

# Run 4-node NCCL test (32 GPUs total)
python3 b200_runai_nccl_test.py --project production --nodes 4
```

**Command-Line Options:**
- `--project` (required) - RunAI project name
- `--nodes` (required) - Number of worker nodes (each B200 has 8 GPUs)
- `--debug` (optional) - Enable NCCL debug output (NCCL_DEBUG=INFO, NCCL_DEBUG_SUBSYS=INIT,NET)

**What it does:**
- Configures the RunAI project
- Auto-increments job names (nccl-test1, nccl-test2, etc.)
- Submits an MPI job with optimized B200 NCCL configuration
- Waits for all pods (launcher + workers) to be created
- Automatically captures logs from all pods to `.logs/` directory
- Creates timestamped log files for each pod

**Output:**
- Log files in `.logs/` with format: `nccl-test<N>_{pod_name}_{timestamp}.log`
- Real-time log streaming in background threads
- NCCL bandwidth results showing bus bandwidth and algorithm bandwidth

**NCCL Configuration:**
- **InfiniBand**: Enabled with all 8 mlx5 adapters, adaptive routing, SHARP
- **NVLink Switch**: Enabled (NCCL_NVLS_ENABLE=1, critical for B200)
- **GPUDirect RDMA**: Level 5 for optimal GPU-to-IB performance
- **UCX Transport**: Reliable Connection (rc) for MPI
- **Debug Output**: Disabled by default for best performance, enable with `--debug`

### Manual Command (Copy & Paste Alternative)

If you prefer to run the `runai mpi submit` command directly without the Python script:

```bash
# First, configure your project
runai config project <PROJECT_NAME>

# Then submit the NCCL test job (2 nodes = 16 GPUs)
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
  --master-args "--allow-run-as-root --bind-to none -map-by slot -np 16 -x NCCL_IB_DISABLE -x NCCL_IB_HCA -x NCCL_IB_QPS_PER_CONNECTION -x NCCL_IB_SPLIT_DATA_ON_QPS -x NCCL_IB_ADAPTIVE_ROUTING -x NCCL_IB_SL -x NCCL_NET_GDR_LEVEL -x NCCL_NVLS_ENABLE -x NCCL_ALGO -x NCCL_SOCKET_IFNAME -x NCCL_ASYNC_ERROR_HANDLING -x CUDA_DEVICE_MAX_CONNECTIONS -x UCX_TLS -mca pml ob1 -mca btl self,tcp all_reduce_perf_mpi -b 1G -e 16G -f 2 -n 100 -g 1" \
  --image-pull-policy IfNotPresent \
  --annotation k8s.v1.cni.cncf.io/networks=network-operator/ibp192s0-sriovnet,network-operator/ibp206s0-sriovnet,network-operator/ibp154s0-sriovnet,network-operator/ibp220s0-sriovnet,network-operator/ibp24s0-sriovnet,network-operator/ibp64s0-sriovnet,network-operator/ibp79s0-sriovnet,network-operator/ibp94s0-sriovnet \
  -e CUDA_DEVICE_MAX_CONNECTIONS=1 \
  -e NCCL_IB_DISABLE=0 \
  -e NCCL_IB_HCA=mlx5 \
  -e NCCL_IB_QPS_PER_CONNECTION=2 \
  -e NCCL_IB_SPLIT_DATA_ON_QPS=0 \
  -e NCCL_IB_ADAPTIVE_ROUTING=1 \
  -e NCCL_IB_SL=1 \
  -e NCCL_NET_GDR_LEVEL=5 \
  -e NCCL_NVLS_ENABLE=1 \
  -e NCCL_ALGO=RING \
  -e NCCL_SOCKET_IFNAME=eth0 \
  -e NCCL_ASYNC_ERROR_HANDLING=1 \
  -e UCX_TLS=rc
```

**Note:** This command does NOT include NCCL debug output. To enable debug logging, add:
```bash
  -e NCCL_DEBUG=INFO \
  -e NCCL_DEBUG_SUBSYS=INIT,NET
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
  - Maps each InfiniBand device as a network attachment via Multus CNI
  - Uses `network-operator` namespace and `-sriovnet` suffix for NAD names
  - Format: `network-operator/ibp<PCI>s0-sriovnet` (e.g., `network-operator/ibp192s0-sriovnet`)
  - Must match the extended resources requested above (8 IB interfaces per B200 node)

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

**CUDA Configuration:**
- **`CUDA_DEVICE_MAX_CONNECTIONS=1`** - Limits CUDA streams for better NCCL performance

**InfiniBand Configuration:**
- **`NCCL_IB_DISABLE=0`** - Explicitly enable InfiniBand (critical)
- **`NCCL_IB_HCA=mlx5`** - Auto-detect all mlx5_* devices (wildcard pattern for 8 IB adapters)
- **`NCCL_IB_QPS_PER_CONNECTION=2`** - Queue pairs per IB connection
  - **[TWEAK]** Higher values (4, 8) can improve bandwidth but use more resources
- **`NCCL_IB_SPLIT_DATA_ON_QPS=0`** - Don't split data across queue pairs
- **`NCCL_IB_ADAPTIVE_ROUTING=1`** - Enable adaptive routing for better fabric utilization
- **`NCCL_IB_SL=1`** - Service level for QoS on InfiniBand fabric

**Performance Configuration:**
- **`NCCL_NET_GDR_LEVEL=5`** - Enable GPUDirect RDMA (GPU ↔ IB direct access)
- **`NCCL_NVLS_ENABLE=1`** - **[CRITICAL FOR B200]** Enable NVLink Switch
- **`NCCL_ALGO=RING`** - Use ring algorithm for collectives
- **`NCCL_SOCKET_IFNAME=eth0`** - Primary network interface for NCCL bootstrap
- **`NCCL_ASYNC_ERROR_HANDLING=1`** - Enables async error handling for better debugging

**MPI/UCX Configuration:**
- **`UCX_TLS=rc`** - Use reliable connection transport for MPI (InfiniBand RC)
  - Note: `UCX_NET_DEVICES` is intentionally NOT set (causes errors with wildcard patterns)

**Debug Configuration (optional, use `--debug` flag):**
- **`NCCL_DEBUG=INFO`** - Enable detailed NCCL logging
- **`NCCL_DEBUG_SUBSYS=INIT,NET`** - Focus on initialization and network subsystems
  - **Performance Impact:** Debug output adds overhead, disabled by default

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
├── healthcheck_network-operator.py  # Network Operator health check script
├── b200_runai_nccl_test.py          # NCCL test runner script
├── snapshot.py                      # Environment discovery/snapshot script
├── overview.py                      # Environment overview script
├── NetworkOperator-24.7.0-to-25.7.0-Upgrade.md  # Network Operator upgrade/troubleshooting guide
├── .logs/                           # Output directory (git-ignored)
│   ├── snapshot.md                  # Snapshot output
│   └── nccl-test*_*.log             # NCCL test logs (timestamped)
├── .gitignore                       # Git exclusions
└── README.md                        # This file
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
