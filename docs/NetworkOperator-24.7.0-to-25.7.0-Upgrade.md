# NVIDIA Network Operator SR-IOV Configuration Issue and Resolution

## Environment
- **Kubernetes Cluster**: DGX nodes managed by Base Command Manager (BCM)
- **Hardware**: DGX systems with NVIDIA ConnectX-7 InfiniBand adapters
- **Initial Network Operator Version**: 24.7.0
- **Target Version**: 25.7.0
- **Nodes Affected**: dgx030, dgx031

## Original Issue

### Problem Description
InfiniBand extended resources (`nvidia.com/resibp*`) were not appearing on Kubernetes nodes, preventing NCCL tests from scheduling. The SR-IOV Network Operator was deployed but unable to configure SR-IOV Virtual Functions (VFs) on the Mellanox ConnectX-7 adapters.

### Symptoms
1. `SriovNetworkNodeState` showed `SYNC STATUS: InProgress` with `CURRENT SYNC STATE: Idle`
2. Extended resources missing from node allocatable resources
3. Pods requiring InfiniBand VFs failed to schedule with error: "no suitable devices for scheduling"

### Root Cause #1: mstconfig Path Issue in Network Operator 24.7.0

The `sriov-network-config-daemon` pod was unable to configure the Mellanox NIC firmware due to a path/permission issue when executing `mstconfig` commands.

**Error from logs:**
```
Error when trying to check if NV access registers are supported
exit status 3
```

The daemon was attempting to access `/host/dev/mst/...` paths inside the container, but the `mstconfig` tool was failing to access the device registers properly. This appeared to be a container configuration issue in the 24.7.0 version of the network operator.

**Note**: This was NOT a secure boot issue, despite initial investigation in that direction. The devices had secure boot enabled, but that was not the blocking factor.

### Related Issues
While we did not find a specific GitHub issue matching this exact error, similar path and device access issues have been reported in the SR-IOV Network Operator repository related to containerized access to hardware devices.

## Resolution Part 1: Upgrade to Network Operator 25.7.0

### Decision Rationale
- Network Operator 24.7.0 had significant structural changes that made in-place upgrades difficult
- Attempting to upgrade to 24.10.1 or 25.7.0 directly via `helm upgrade` resulted in errors:
  - `nil pointer evaluating interface {}.pvcName` (25.7.0)
  - `nil pointer evaluating interface {}.enabled` for `nicConfigurationOperator` (24.10.1)
- Clean migration approach was chosen to ensure proper configuration

### Upgrade Steps

#### 1. Backup Existing Configuration
```bash
# Backup SR-IOV policies
kubectl get sriovnetworknodepolicy -n network-operator -o yaml > sriov-policies-backup.yaml

# Backup SR-IOV IB networks
kubectl get sriovibnetwork -n network-operator -o yaml > sriov-networks-backup.yaml

# Backup SR-IOV operator config
kubectl get sriovoperatorconfig -n network-operator -o yaml > sriov-config-backup.yaml
```

#### 2. Uninstall Old Network Operator
```bash
helm uninstall network-operator -n network-operator
```

#### 3. Create Custom Values File for 25.7.0

Created `network-operator-25.7.0-values.yaml`:

```yaml
# Enable NFD
nfd:
  enabled: true

# Enable SR-IOV Network Operator
sriovNetworkOperator:
  enabled: true

# Disable NIC Configuration Operator (deprecated)
nicConfigurationOperator:
  enabled: false

# Disable Maintenance Operator (not needed yet)
maintenanceOperator:
  enabled: false

# Deploy the operator config CR
deployCR: true

# Secondary network configuration
secondaryNetwork:
  deploy: true
  cniPlugins:
    deploy: true
  multus:
    deploy: true
  ipamPlugin:
    deploy: false

# NV-IPAM
nvIpam:
  deploy: true

# Disable components we don't need
ofedDriver:
  deploy: false
rdmaSharedDevicePlugin:
  deploy: false
sriovDevicePlugin:
  deploy: false
psp:
  enabled: false

# SR-IOV operator specific config
sriov-network-operator:
  sriovOperatorConfig:
    deploy: true
    configDaemonNodeSelector:
      beta.kubernetes.io/os: "linux"
      network.nvidia.com/operator.mofed.wait: "false"
```

#### 4. Install Network Operator 25.7.0
```bash
helm repo add nvidia https://helm.ngc.nvidia.com/nvidia
helm repo update

helm install network-operator nvidia/network-operator \
  --version 25.7.0 \
  --namespace network-operator \
  --create-namespace \
  -f network-operator-25.7.0-values.yaml
```

#### 5. Reapply SR-IOV Policies
```bash
kubectl apply -f sriov-policies-backup.yaml
kubectl apply -f sriov-networks-backup.yaml
kubectl apply -f sriov-config-backup.yaml
```

**Note**: Some conflict errors occurred during reapply, but these were harmless resource version conflicts indicating the resources were already applied during the helm install.

### SR-IOV Network Policies Configured

Eight ConnectX-7 InfiniBand interfaces per node:
- `ibp24s0` (mlx5_4, PCI 0000:18:00.0)
- `ibp64s0` (mlx5_7, PCI 0000:40:00.0)
- `ibp79s0` (mlx5_8, PCI 0000:4f:00.0)
- `ibp94s0` (mlx5_9, PCI 0000:5e:00.0)
- `ibp154s0` (mlx5_10, PCI 0000:9a:00.0)
- `ibp192s0` (mlx5_13, PCI 0000:c0:00.0)
- `ibp206s0` (mlx5_14, PCI 0000:ce:00.0)
- `ibp220s0` (mlx5_15, PCI 0000:dc:00.0)

Each policy configured with:
- `numVfs: 8` (8 Virtual Functions per Physical Function)
- `deviceType: netdevice`
- `isRdma: true`
- `linkType: ib`
- `vendor: 15b3` (Mellanox/NVIDIA)
- `nodeSelector: nvidia.com/gpu.present: "true"`

**Correctly Excluded Devices:**
- Internal mezz ConnectX-7 cards (`ibs14f0-3`, mlx5_0-3)
- BlueField-3 DPUs (`ibp41s0f0`, `ibp170s0f0`, mlx5_5, mlx5_11-12)

### NV-IPAM Configuration

In Network Operator 25.7.0, `nv-ipam` is no longer deployed directly through the main Helm chart. Instead, it must be deployed via a `NicClusterPolicy` custom resource.

#### Create NicClusterPolicy for nv-ipam

Created `nic-cluster-policy.yaml`:

```yaml
apiVersion: mellanox.com/v1alpha1
kind: NicClusterPolicy
metadata:
  name: nic-cluster-policy
  namespace: network-operator
spec:
  nvIpam:
    image: nvidia-k8s-ipam  # Note: Use nvidia-k8s-ipam (not nv-ipam) for 25.x
    repository: ghcr.io/mellanox
    version: v0.2.0
    imagePullSecrets: []
    enableWebhook: false
```

```bash
kubectl apply -f nic-cluster-policy.yaml
```

This deploys the `nv-ipam` DaemonSet and creates the `IPPool` CRD, allowing IP address management for secondary networks.

**Important**: Ensure the `image` field is set to `nvidia-k8s-ipam` (not `nv-ipam`). This is a critical change in Network Operator 25.x that is not well documented. See Resolution Part 3 for details if image pull errors occur.

## Resolution Part 2: Firmware Configuration and Power Cycle Requirement

### Root Cause #2: Incomplete Firmware Activation

After upgrading to Network Operator 25.7.0, the operator successfully wrote firmware changes to the ConnectX-7 adapters but the `SriovNetworkNodeState` remained in `Reboot_Required` status even after multiple OS reboots.

**Investigation revealed:**
```bash
# Checking firmware configuration on dgx030
ssh dgx030 "mstconfig -d 0000:18:00.0 q | grep NUM_OF_VFS"
```

Output showed:
```
*        NUM_OF_VFS                          16              16              8
         #                                   Default         Current         Next Boot
```

**Key Finding**: The firmware showed `Current: 16` and `Next Boot: 8`, indicating:
1. The operator successfully wrote `NUM_OF_VFS=8` to the NIC firmware (NVRAM)
2. The changes were queued for "Next Boot"
3. Standard OS reboots were NOT sufficient to activate the firmware changes
4. A **cold reboot (full power cycle)** was required

### Troubleshooting Steps Taken

#### 1. Verified VF Activation Status
```bash
# Check if VFs are enabled on the interfaces
ssh dgx030 "for iface in ibp24s0 ibp64s0 ibp79s0 ibp94s0 ibp154s0 ibp192s0 ibp206s0 ibp220s0; do \
  echo -n \"\$iface: \"; \
  cat /sys/class/net/\$iface/device/sriov_numvfs 2>/dev/null || echo 'not found'; \
done"
```

Result: All interfaces showed `0` VFs, confirming they were not activated.

#### 2. Checked SriovNetworkNodeState
```bash
kubectl get sriovnetworknodestate dgx030 -n network-operator -o jsonpath='{.status.syncStatus}'
```

Result: `InProgress` with annotation `Reboot_Required`

#### 3. Examined sriov-network-config-daemon Logs
```bash
kubectl logs -n network-operator \
  $(kubectl get pods -n network-operator -o wide | grep "sriov-network-config-daemon" | grep dgx030 | awk '{print $1}') \
  --tail=50
```

Logs showed:
```
LEVEL(-2) mellanox/mellanox_plugin.go:121 Changing TotalVfs, needs reboot 
{"current": 16, "requested": 8}
```

This confirmed the operator detected the mismatch and requested a reboot.

#### 4. Verified Firmware Configuration for All Devices
```bash
# Check all 8 ConnectX-7 devices
for pci in 0000:18:00.0 0000:40:00.0 0000:4f:00.0 0000:5e:00.0 \
           0000:9a:00.0 0000:c0:00.0 0000:ce:00.0 0000:dc:00.0; do
  echo "=== $pci ==="
  ssh dgx030 "mstconfig -d $pci q | grep NUM_OF_VFS"
done
```

All devices showed the same pattern: `Current: 16, Next Boot: 8`

#### 5. Attempted Standard OS Reboot (Multiple Times)
```bash
kubectl drain dgx030 --ignore-daemonsets --delete-emptydir-data
ssh dgx030 reboot
# Wait for node to come back online
kubectl uncordon dgx030
```

Result: **Failed** - `SriovNetworkNodeState` still showed `Reboot_Required` after multiple reboots.

#### 6. Investigated BCM Re-imaging Impact

**Question**: Does BCM re-imaging reset the firmware?

**Answer**: No. The `NUM_OF_VFS` setting is stored in the **non-volatile memory (NVRAM) on each ConnectX-7 adapter**, which is independent of the OS filesystem. BCM re-imaging only affects the host OS and does not touch PCIe adapter firmware.

### Final Resolution: Cold Reboot (Power Cycle)

#### Procedure
```bash
# 1. Drain the node
kubectl drain dgx030 --ignore-daemonsets --delete-emptydir-data

# 2. Perform a COLD REBOOT (full power cycle)
ssh dgx030 "shutdown -h now"

# 3. Wait for complete power-off (important!)
# Wait 30-60 seconds

# 4. Power the node back on
# (Use IPMI/BMC or physical power button)

# 5. Wait for node to rejoin cluster
kubectl get nodes -w

# 6. Uncordon the node
kubectl uncordon dgx030
```

#### Verification After Power Cycle
```bash
# 1. Check firmware now shows Current: 8
ssh dgx030 "mstconfig -d 0000:18:00.0 q | grep NUM_OF_VFS"
# Expected: Current: 8, Next Boot: 8

# 2. Check VFs are activated
ssh dgx030 "cat /sys/class/net/ibp24s0/device/sriov_numvfs"
# Expected: 8

# 3. Check SriovNetworkNodeState
kubectl get sriovnetworknodestate dgx030 -n network-operator
# Expected: SYNC STATUS: Succeeded

# 4. Verify extended resources appear on node
kubectl describe node dgx030 | grep -A 20 Allocatable
# Expected: nvidia.com/resibp* resources with quantity 8
```

#### Success Confirmation (dgx031)
```
Allocatable:
  cpu:                     224
  ephemeral-storage:       1699700525519
  hugepages-1Gi:           0
  hugepages-2Mi:           0
  memory:                  2113348180Ki
  nvidia.com/gpu:          8
  nvidia.com/resibp154s0:  8
  nvidia.com/resibp192s0:  8
  nvidia.com/resibp206s0:  8
  nvidia.com/resibp220s0:  8
  nvidia.com/resibp24s0:   8
  nvidia.com/resibp64s0:   8
  nvidia.com/resibp79s0:   8
  nvidia.com/resibp94s0:   8
```

## Resolution Part 3: NV-IPAM Image Configuration Issue

### Root Cause #3: Incorrect Image Name in NicClusterPolicy

After successfully deploying the Network Operator 25.7.0 and completing the cold reboot to activate SR-IOV VFs, a new issue emerged: the `nv-ipam` pods were failing to start with `ImagePullBackOff` or `ErrImagePull` status.

**Investigation revealed:**
```bash
kubectl get pods -n network-operator | grep ipam
```

Output showed:
```
nv-ipam-xxxxx    0/1    ImagePullBackOff    0    10m
```

**Checking the image pull error:**
```bash
kubectl describe pod <nv-ipam-pod-name> -n network-operator
```

Showed errors attempting to pull images from incorrect registries:
- `ghcr.io/mellanox/nv-ipam:v0.2.0` (403 Forbidden or 401 Unauthorized)
- `nvcr.io/nvstaging/mellanox/nv-ipam:v0.2.0` (authentication errors)

### Problem Analysis

The initial `NicClusterPolicy` configuration (created in Resolution Part 1) specified:

```yaml
apiVersion: mellanox.com/v1alpha1
kind: NicClusterPolicy
metadata:
  name: nic-cluster-policy
  namespace: network-operator
spec:
  nvIpam:
    image: nv-ipam              # ❌ INCORRECT
    repository: ghcr.io/mellanox
    version: v0.2.0
    imagePullSecrets: []
    enableWebhook: false
```

This configuration was based on assumptions from the 24.7.0 deployment, but **the image name changed in the Network Operator 25.7.0 release**.

### Solution: Update Image Name

The correct configuration was found in the Network Operator 25.1.0 documentation (the 25.7.0 documentation had incomplete information):

```yaml
apiVersion: mellanox.com/v1alpha1
kind: NicClusterPolicy
metadata:
  name: nic-cluster-policy
  namespace: network-operator
spec:
  nvIpam:
    image: nvidia-k8s-ipam      # ✅ CORRECT
    repository: ghcr.io/mellanox
    version: v0.2.0
    imagePullSecrets: []
    enableWebhook: false
```

**Key Change**: `image: nv-ipam` → `image: nvidia-k8s-ipam`

### Applying the Fix

```bash
# Edit the NicClusterPolicy
kubectl edit nicclusterpolicy nic-cluster-policy -n network-operator

# Update the nvIpam.image field from "nv-ipam" to "nvidia-k8s-ipam"
# Save and exit
```

After applying the change:
```bash
# Verify the nv-ipam pods are now running
kubectl get pods -n network-operator | grep ipam

# Expected output:
# nv-ipam-xxxxx    1/1    Running    0    2m
```

### Verification: IPPools Created

With `nv-ipam` running correctly, the IPPool custom resources were created to provide IP addresses for InfiniBand VFs:

```bash
kubectl get ippools.nv-ipam.nvidia.com -n network-operator
```

Expected output:
```
NAME                   SUBNET            GATEWAY   BLOCK SIZE
vf-pool-192-168-1      192.168.1.0/24              8
vf-pool-192-168-2      192.168.2.0/24              8
vf-pool-192-168-3      192.168.3.0/24              8
vf-pool-192-168-4      192.168.4.0/24              8
vf-pool-192-168-5      192.168.5.0/24              8
vf-pool-192-168-6      192.168.6.0/24              8
vf-pool-192-168-7      192.168.7.0/24              8
vf-pool-192-168-8      192.168.8.0/24              8
```

**IPPool Configuration Note**: Each DGX B200 node has 8 physical HCAs (InfiniBand adapters), and each HCA requires 8 VF IP addresses (one per GPU) for GPU-to-GPU communication. Therefore, 8 separate IP pools with `perNodeBlockSize: 8` were created to ensure sufficient IP address allocation (64 VF IPs per node total).

### Documentation Gap

**Important Note**: This image name discrepancy was not clearly documented in the Network Operator 25.7.0 upgrade guide. The correct image name (`nvidia-k8s-ipam`) was found by consulting the 25.1.0 documentation. Future upgraders should be aware of this change.

The correct image naming convention for NVIDIA Network Operator 25.x releases:
- **Correct**: `nvidia-k8s-ipam`
- **Incorrect**: `nv-ipam`, `nv-ipam-controller`, `ipam-controller`

## Resolution Part 4: Enabling RDMA Shared Device Plugin

### Root Cause #4: Missing RDMA Device Plugin Configuration

After successfully deploying SR-IOV VFs and NV-IPAM, NCCL tests were still unable to utilize InfiniBand for inter-GPU communication. The pods showed:
- `/dev/infiniband/uverbs*` devices were present in the pods
- NCCL logs reported: `NET/IB : No device found.` and fell back to `Using network Socket`
- UCX warnings: `network device 'mlx5:1' is not available`

**Investigation revealed:**
```bash
kubectl get pods -n network-operator | grep rdma-device-plugin
# No results - the RDMA device plugin was not deployed!
```

Checking the NicClusterPolicy status:
```bash
kubectl get nicclusterpolicies.mellanox.com -n network-operator -o yaml
```

Showed that the RDMA device plugin state was **ignored**:
```yaml
status:
  appliedStates:
  - name: state-RDMA-device-plugin
    state: ignore    # ❌ NOT DEPLOYED
```

### Problem Analysis

The `rdmaSharedDevicePlugin` was explicitly disabled in the initial Helm values (from Resolution Part 1):
```yaml
rdmaSharedDevicePlugin:
  deploy: false    # ❌ INCORRECT - This prevents NCCL from discovering IB devices
```

**Why RDMA Device Plugin is Required:**
- NCCL and other RDMA applications need proper device enumeration
- The RDMA device plugin exposes InfiniBand devices as Kubernetes extended resources
- Without it, applications can see `/dev/infiniband/uverbs*` but cannot properly initialize RDMA communication
- The plugin creates the necessary device mappings and resource allocation for RDMA workloads

### Solution: Enable RDMA Shared Device Plugin in NicClusterPolicy

The RDMA device plugin must be enabled in the `NicClusterPolicy` resource. Edit the existing policy:

```bash
kubectl edit nicclusterpolicies.mellanox.com nic-cluster-policy
```

Add the `rdmaSharedDevicePlugin` configuration to the spec:

```yaml
apiVersion: mellanox.com/v1alpha1
kind: NicClusterPolicy
metadata:
  name: nic-cluster-policy
spec:
  nvIpam:
    image: nvidia-k8s-ipam
    repository: ghcr.io/mellanox
    version: v0.2.0
    imagePullSecrets: []
    enableWebhook: false
  
  # Add RDMA Shared Device Plugin configuration
  rdmaSharedDevicePlugin:
    image: k8s-rdma-shared-dev-plugin
    repository: nvcr.io/nvidia/mellanox
    version: network-operator-v25.7.0
    config: |
      {
        "configList": [
          {
            "resourceName": "rdma_shared_device_a",
            "rdmaHcaMax": 63,
            "selectors": {
              "vendors": ["15b3"]
            }
          }
        ]
      }
```

**Configuration Details:**
- **`resourceName`**: Name of the Kubernetes extended resource (`rdma_shared_device_a`)
- **`rdmaHcaMax`**: Maximum number of RDMA resources per device (63 is recommended)
- **`selectors.vendors`**: `["15b3"]` is the PCI vendor ID for Mellanox/NVIDIA devices
  - This auto-discovers all Mellanox InfiniBand devices across all nodes
  - Device-specific configuration is not required (avoids issues with varying `mlx5_*` numbers)

### Common Configuration Mistakes to Avoid

#### ❌ Mistake 1: Empty Selectors
```yaml
# WRONG - Will cause plugin to crash
"selectors": {
  "vendors": [],
  "deviceIDs": [],
  "drivers": [],
  "linkTypes": []
}
```

**Error**: `configuration missmatch. neither "selectors" nor "devices" fields exits`

#### ❌ Mistake 2: Missing rdmaHcaMax Value
```yaml
# WRONG - Invalid JSON
"rdmaHcaMax":
```

**Error**: `invalid character '}' after array element`

#### ❌ Mistake 3: Hardcoded Device Names
```yaml
# WRONG - Device numbers vary by node
"devices": ["mlx5_15", "mlx5_10", "mlx5_14", "mlx5_13"]
```

**Problem**: Device numbers (`mlx5_X`) are different on each node and can change between reboots.

#### ✅ Correct: Use Vendor Selector
```yaml
# CORRECT - Auto-discovers all Mellanox devices
"selectors": {
  "vendors": ["15b3"]
}
```

### Verification After Enabling RDMA Device Plugin

#### 1. Check RDMA Device Plugin Pods
```bash
kubectl get pods -n network-operator -l app=rdma-shared-dp
```

Expected output:
```
NAME                      READY   STATUS    RESTARTS   AGE
rdma-shared-dp-ds-xxxxx   1/1     Running   0          2m
rdma-shared-dp-ds-yyyyy   1/1     Running   0          2m
...
```

#### 2. Check Plugin Logs
```bash
kubectl logs -n network-operator -l app=rdma-shared-dp --tail=20
```

Expected output (successful discovery):
```
Starting K8s RDMA Shared Device Plugin version= master
resource manager reading configs
Reading /k8s-rdma-shared-dev-plugin/config.json
loaded config: [{ResourceName:rdma_shared_device_a ... Selectors:{Vendors:[15b3]}}]
Discovering RDMA devices...
Found devices: [mlx5_0 mlx5_1 mlx5_2 ...]
```

#### 3. Verify Extended Resources on Nodes
```bash
kubectl get nodes -o json | jq '.items[] | {
  name: .metadata.name,
  rdma: .status.allocatable | with_entries(select(.key | startswith("rdma")))
}'
```

Expected output:
```json
{
  "name": "dgx030",
  "rdma": {
    "rdma/rdma_shared_device_a": "500"
  }
}
```

#### 4. Test NCCL with InfiniBand
Run the NCCL test and check the logs:
```bash
kubectl logs <nccl-test-pod> | grep -i "net/ib"
```

Expected output (successful InfiniBand usage):
```
NET/IB : Using [0]mlx5_20:1/IB [RO]; OOB ibv0:<0>
NET/IB : Using [1]mlx5_24:1/IB [RO]; OOB ibv1:<0>
...
NCCL version 2.x.x+cuda12.x
```

**No longer seeing**: `NET/IB : No device found.` or `Using network Socket`

### Integration with NCCL Environment Variables

With the RDMA device plugin enabled, update your NCCL job configurations to use wildcard patterns:

```bash
# In your job YAML or Python script
NCCL_IB_HCA=mlx5              # Auto-detect all mlx5_* devices (wildcard)
UCX_NET_DEVICES=mlx5:1        # Auto-detect all mlx5_* devices on port 1
NCCL_DEBUG=INFO               # Enable logging to verify IB usage
```

**Note**: The wildcard patterns (`mlx5` instead of `mlx5_15,mlx5_10,...`) work correctly once the RDMA device plugin is running and properly exposes the devices to NCCL.

### Troubleshooting RDMA Device Plugin Issues

If the `rdma-shared-dp` pods are crash-looping:

#### Check ConfigMap Generated by Network Operator
```bash
kubectl get configmap rdma-devices -n network-operator -o yaml
```

The ConfigMap should contain valid JSON:
```yaml
data:
  config.json: |
    {
      "configList": [
        {
          "resourceName": "rdma_shared_device_a",
          "rdmaHcaMax": 63,
          "selectors": {
            "vendors": ["15b3"]
          }
        }
      ]
    }
```

#### Validate JSON Syntax
```bash
kubectl get configmap rdma-devices -n network-operator -o jsonpath='{.data.config\.json}' | jq .
```

If `jq` returns an error, the JSON is invalid and needs to be corrected in the NicClusterPolicy.

#### Check for Empty Arrays
Look for empty selector arrays in the plugin logs:
```bash
kubectl logs -n network-operator <rdma-shared-dp-pod>
```

If you see:
```
Selectors:{Vendors:[] DeviceIDs:[] Drivers:[] IfNames:[] LinkTypes:[]}
error: configuration missmatch. neither "selectors" nor "devices" fields exits
```

This means the Network Operator added empty arrays as defaults. Fix by explicitly setting `vendors: ["15b3"]`.

### Secondary Network Components Configuration

#### Root Cause #5: Missing Secondary Network Components

After enabling the RDMA device plugin, the final piece required for NCCL to use InfiniBand was ensuring the **secondary network components** were properly configured in the `NicClusterPolicy`. These components are responsible for attaching SR-IOV VF interfaces to pods.

**Investigation revealed:**

The Network Operator 24.7.0 deployment had secondary network components enabled in the Helm values:
```yaml
secondaryNetwork:
  deploy: true
  cniPlugins:
    deploy: true
  multus:
    deploy: true
  ipamPlugin:
    deploy: false  # Using nv-ipam instead
```

However, these components must **also be configured in the `NicClusterPolicy`** in Network Operator 25.7.0 to be properly deployed and managed.

#### Why Secondary Network Components are Required

These three components work together to enable SR-IOV networking in Kubernetes:

1. **Multus CNI**
   - Meta-plugin that enables attaching multiple network interfaces to pods
   - Reads the `k8s.v1.cni.cncf.io/networks` annotation from pod specs
   - Without Multus, pods only get the default `eth0` interface
   - **Critical**: Your NCCL jobs use this annotation to request InfiniBand VF interfaces

2. **CNI Plugins**
   - Provides the actual CNI binaries (bridge, host-device, ipvlan, etc.)
   - Required by Multus to configure secondary interfaces
   - Handles the low-level network interface attachment

3. **Whereabouts IPAM** (optional, but recommended)
   - IP Address Management plugin for secondary networks
   - Can work alongside nv-ipam for different network types
   - Provides IP allocation for secondary interfaces that don't use nv-ipam

**Note**: In this deployment, `nv-ipam` handles IP allocation for InfiniBand VFs, while whereabouts provides flexibility for other secondary network types.

#### Solution: Add Secondary Network Components to NicClusterPolicy

According to the [NVIDIA Network Operator 25.7.0 deployment guide](https://docs.nvidia.com/networking/display/kubernetes2570/deployment-guide-kubernetes.html#network-operator-deployment-with-a-secondary-network), secondary network components must be configured in the `NicClusterPolicy`.

Edit the `NicClusterPolicy`:

```bash
kubectl edit nicclusterpolicies.mellanox.com nic-cluster-policy
```

Add the `secondaryNetwork` section to the spec:

```yaml
apiVersion: mellanox.com/v1alpha1
kind: NicClusterPolicy
metadata:
  name: nic-cluster-policy
spec:
  nvIpam:
    image: nvidia-k8s-ipam
    repository: ghcr.io/mellanox
    version: v0.2.0
    imagePullSecrets: []
    enableWebhook: false
  
  rdmaSharedDevicePlugin:
    image: k8s-rdma-shared-dev-plugin
    repository: nvcr.io/nvidia/mellanox
    version: network-operator-v25.7.0
    config: |
      {
        "configList": [
          {
            "resourceName": "rdma_shared_device_a",
            "rdmaHcaMax": 63,
            "selectors": {
              "vendors": ["15b3"]
            }
          }
        ]
      }
  
  # Add Secondary Network Components
  secondaryNetwork:
    cniPlugins:
      image: plugins
      repository: nvcr.io/nvidia/mellanox
      version: network-operator-v25.7.0
      imagePullSecrets: []
    multus:
      image: multus-cni
      repository: nvcr.io/nvidia/mellanox
      version: network-operator-v25.7.0
      imagePullSecrets: []
    ipamPlugin:
      image: whereabouts
      repository: nvcr.io/nvidia/mellanox
      version: network-operator-v25.7.0
      imagePullSecrets: []
```

#### Verification After Enabling Secondary Network Components

##### 1. Check Multus DaemonSet
```bash
kubectl get pods -n network-operator | grep multus
```

Expected output:
```
kube-multus-ds-xxxxx   1/1   Running   0   5m
kube-multus-ds-yyyyy   1/1   Running   0   5m
```

##### 2. Check CNI Plugins DaemonSet
```bash
kubectl get pods -n network-operator | grep cni-plugins
```

Expected output:
```
cni-plugins-ds-xxxxx   1/1   Running   0   5m
cni-plugins-ds-yyyyy   1/1   Running   0   5m
```

##### 3. Check Whereabouts IPAM DaemonSet
```bash
kubectl get pods -n network-operator | grep whereabouts
```

Expected output:
```
whereabouts-xxxxx   1/1   Running   0   5m
whereabouts-yyyyy   1/1   Running   0   5m
```

##### 4. Verify Multus Configuration
```bash
kubectl get network-attachment-definitions -A
```

This should list your SR-IOV IB network definitions (e.g., `ibp192s0`, `ibp206s0`, etc.).

##### 5. Test with NCCL Job

Run your NCCL test job and verify that the pods receive the InfiniBand VF interfaces:

```bash
# Get a running NCCL worker pod
kubectl exec -n runai-test <nccl-worker-pod> -- ip addr show

# Should see interfaces like:
# - eth0 (default network)
# - net1, net2, net3... (SR-IOV VF interfaces)
```

Check NCCL logs for InfiniBand usage:
```bash
kubectl logs <nccl-test-pod> | grep -E "NET/IB|Using.*mlx5"
```

Expected output (successful InfiniBand usage):
```
NET/IB : Using [0]mlx5_20:1/IB [RO]; OOB ibv0:<0>
NET/IB : Using [1]mlx5_24:1/IB [RO]; OOB ibv1:<0>
...
```

#### How These Components Work Together

The complete data flow for NCCL over InfiniBand in Kubernetes:

1. **Job Submission**: Your `b200_runai_nccl_test.py` script submits a job with:
   - SR-IOV resource requests (`nvidia.com/resibp24s0=1`, etc.)
   - Network annotation (`k8s.v1.cni.cncf.io/networks=default/ibp192s0,...`)

2. **Pod Scheduling**: Kubernetes scheduler places the pod on a node with available:
   - SR-IOV VF resources (exposed by SR-IOV device plugin)
   - RDMA resources (exposed by RDMA device plugin)

3. **Network Attachment**: When the pod starts:
   - **Multus** reads the `k8s.v1.cni.cncf.io/networks` annotation
   - **CNI plugins** attach the SR-IOV VF interfaces to the pod
   - **nv-ipam** allocates IP addresses to the VF interfaces
   - Pod now has multiple network interfaces (eth0 + IB VFs)

4. **NCCL Initialization**: Inside the pod:
   - NCCL environment variables (`NCCL_IB_HCA=mlx5`, etc.) guide device selection
   - **RDMA device plugin** has exposed the IB devices properly
   - NCCL finds and uses the InfiniBand interfaces for GPU-to-GPU communication

**Without any one of these components**, NCCL cannot use InfiniBand:
- No Multus → VF interfaces not attached to pods
- No RDMA device plugin → NCCL reports "No device found"
- No nv-ipam → VF interfaces have no IP addresses
- No SR-IOV configuration → No VFs created

#### Complete NicClusterPolicy Example

For reference, here is the complete `NicClusterPolicy` configuration with all components enabled:

```yaml
apiVersion: mellanox.com/v1alpha1
kind: NicClusterPolicy
metadata:
  name: nic-cluster-policy
  namespace: network-operator
spec:
  # NV-IPAM for InfiniBand VF IP allocation
  nvIpam:
    image: nvidia-k8s-ipam
    repository: ghcr.io/mellanox
    version: v0.2.0
    imagePullSecrets: []
    enableWebhook: false
  
  # RDMA Device Plugin for NCCL device discovery
  rdmaSharedDevicePlugin:
    image: k8s-rdma-shared-dev-plugin
    repository: nvcr.io/nvidia/mellanox
    version: network-operator-v25.7.0
    config: |
      {
        "configList": [
          {
            "resourceName": "rdma_shared_device_a",
            "rdmaHcaMax": 63,
            "selectors": {
              "vendors": ["15b3"]
            }
          }
        ]
      }
  
  # Secondary Network Components for VF interface attachment
  secondaryNetwork:
    cniPlugins:
      image: plugins
      repository: nvcr.io/nvidia/mellanox
      version: network-operator-v25.7.0
      imagePullSecrets: []
    multus:
      image: multus-cni
      repository: nvcr.io/nvidia/mellanox
      version: network-operator-v25.7.0
      imagePullSecrets: []
    ipamPlugin:
      image: whereabouts
      repository: nvcr.io/nvidia/mellanox
      version: network-operator-v25.7.0
      imagePullSecrets: []
```

## Key Learnings

### 1. Firmware Changes Require Cold Reboot
- Mellanox/NVIDIA ConnectX firmware changes (like `NUM_OF_VFS`) are written to NVRAM
- Changes are queued as "Next Boot" values
- **Standard OS reboots (warm reboots) do NOT activate firmware changes**
- **Full power cycle (cold reboot) is REQUIRED** for firmware changes to take effect
- This is a hardware requirement, not a software issue

### 2. Firmware Settings Persist Across OS Re-imaging
- `NUM_OF_VFS` is stored in the NIC's NVRAM, not the OS filesystem
- BCM re-imaging does NOT affect these settings
- Once configured and activated (after power cycle), the settings persist permanently
- Future OS reboots will respect the firmware settings without requiring additional power cycles

### 3. Network Operator Version Compatibility
- Network Operator 24.7.0 had issues with device access in containerized environments
- Version 25.7.0 resolved these issues
- Helm chart structure changed significantly between versions, making in-place upgrades difficult
- Clean migration (uninstall/reinstall) with custom values file was the most reliable approach

### 4. NV-IPAM Deployment Changes
- In Network Operator 25.7.0, `nv-ipam` is no longer part of the main Helm chart
- Must be deployed separately via `NicClusterPolicy` custom resource
- This provides more flexibility but requires an additional configuration step

### 5. SR-IOV Policy Targeting
- Use explicit `pfNames` in `nicSelector` to target specific interfaces
- This prevents accidental configuration of inappropriate devices (DPUs, internal mezz cards)
- Vendor filtering (`vendor: 15b3`) provides additional safety

### 6. NV-IPAM Image Name Change in 25.x
- Network Operator 25.x uses a different image name for the IPAM component
- Correct image name: `nvidia-k8s-ipam` (not `nv-ipam`)
- This change was not well documented in the 25.7.0 release notes
- Using the wrong image name causes `ImagePullBackOff` errors
- The correct configuration can be found in the 25.1.0 documentation

### 7. RDMA Device Plugin is Essential for NCCL
- Having `/dev/infiniband/uverbs*` devices in pods is **not sufficient** for NCCL to use InfiniBand
- The RDMA Shared Device Plugin must be enabled in the `NicClusterPolicy` to expose devices properly
- Without the plugin, NCCL reports `NET/IB : No device found.` and falls back to TCP/Socket
- Use vendor selector (`vendors: ["15b3"]`) for auto-discovery across all nodes
- Avoid hardcoding device names or using empty selector arrays
- The plugin is configured separately from SR-IOV device plugin and serves a different purpose

### 8. Secondary Network Components Must Be Configured in NicClusterPolicy
- In Network Operator 25.7.0, secondary network components (Multus, CNI plugins, whereabouts) must be configured in the `NicClusterPolicy`, not just in Helm values
- **Multus CNI** is critical for attaching SR-IOV VF interfaces to pods via the `k8s.v1.cni.cncf.io/networks` annotation
- Without Multus, pods requesting secondary networks will only receive the default `eth0` interface
- All three components (Multus, CNI plugins, IPAM) must be present for SR-IOV networking to function
- This configuration matches the pattern used in Network Operator 24.7.0 but with updated syntax for 25.7.0
- Reference: [NVIDIA Network Operator 25.7.0 Secondary Network Configuration](https://docs.nvidia.com/networking/display/kubernetes2570/deployment-guide-kubernetes.html#network-operator-deployment-with-a-secondary-network)

## Troubleshooting Tips for Future Issues

### Check Firmware Status
```bash
# View current and next boot firmware settings
mstconfig -d <PCI_ADDRESS> q | grep NUM_OF_VFS
```

### Check VF Activation
```bash
# Check if VFs are currently active
cat /sys/class/net/<INTERFACE>/device/sriov_numvfs
```

### Check Operator Status
```bash
# Check SriovNetworkNodeState
kubectl get sriovnetworknodestate -n network-operator

# Check daemon logs
kubectl logs -n network-operator -l app=sriov-network-config-daemon --tail=100
```

### Distinguish Between Warm and Cold Reboot
- **Warm Reboot**: `reboot` command - OS restarts but hardware stays powered
- **Cold Reboot**: `shutdown -h now` followed by power-on - complete power cycle
- For firmware changes: **Always use cold reboot**

### Verify Device List
```bash
# List all Mellanox devices
ibdev2netdev -v

# Check which devices have SR-IOV policies
kubectl get sriovnetworknodepolicy -n network-operator
```

## References

- [NVIDIA Network Operator Documentation](https://docs.nvidia.com/networking/display/COKAN10)
- [SR-IOV Network Operator GitHub](https://github.com/k8snetworkplumbingwg/sriov-network-operator)
- [Mellanox Firmware Tools (MFT) Documentation](https://docs.nvidia.com/networking/display/MFTV4231)
- [Network Operator Helm Chart](https://github.com/Mellanox/network-operator)

## Appendix: Complete Device Inventory (dgx030)

### ConnectX-7 Adapters (Configured for SR-IOV)
| PCI Address | mlx5 Device | Interface | Firmware | Status |
|-------------|-------------|-----------|----------|--------|
| 0000:18:00.0 | mlx5_4 | ibp24s0 | 28.43.2026 | Configured |
| 0000:40:00.0 | mlx5_7 | ibp64s0 | 28.43.2026 | Configured |
| 0000:4f:00.0 | mlx5_8 | ibp79s0 | 28.43.2026 | Configured |
| 0000:5e:00.0 | mlx5_9 | ibp94s0 | 28.43.2026 | Configured |
| 0000:9a:00.0 | mlx5_10 | ibp154s0 | 28.43.2026 | Configured |
| 0000:c0:00.0 | mlx5_13 | ibp192s0 | 28.43.2026 | Configured |
| 0000:ce:00.0 | mlx5_14 | ibp206s0 | 28.43.2026 | Configured |
| 0000:dc:00.0 | mlx5_15 | ibp220s0 | 28.43.2026 | Configured |

### Other Mellanox Devices (Excluded from SR-IOV)
| PCI Address | mlx5 Device | Interface | Type | Reason for Exclusion |
|-------------|-------------|-----------|------|---------------------|
| 0000:05:00.0-3 | mlx5_0-3 | ibs14f0-3 | Internal Mezz | Internal use only |
| 0000:29:00.0-1 | mlx5_5-6 | ibp41s0f0, bond0 | BlueField-3 DPU | Has own OS |
| 0000:aa:00.0-1 | mlx5_11-12 | ibp170s0f0, bond0 | BlueField-3 DPU | Has own OS |

---

**Document Created**: October 7, 2025  
**Last Updated**: October 14, 2025  
**Status**: ✅ Fully Resolved and Performance Validated

Both nodes (dgx030, dgx031) are operational with complete Network Operator 25.7.0 configuration:
- SR-IOV VFs active (8 per HCA, 64 total per node)
- NV-IPAM functioning correctly with proper image name (`nvidia-k8s-ipam`)
- RDMA Shared Device Plugin enabled for NCCL device discovery
- Secondary network components deployed (Multus, CNI plugins, whereabouts IPAM)
- Network Attachment Definitions created in `network-operator` namespace with `-sriovnet` suffix
- All components verified and showing `state: ready` in NicClusterPolicy status

**NCCL Performance Validation**:
- Multi-node NCCL tests successfully using InfiniBand with SHARP enabled
- Achieved **388.66 GB/s** average bus bandwidth on 2-node (16 GPU) tests
- NCCL correctly detecting and using all 8 InfiniBand adapters per node
- Optimized configuration deployed in `b200_runai_nccl_test_v2.py` with additional tuning parameters
