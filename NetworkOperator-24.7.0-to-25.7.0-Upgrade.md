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
**Last Updated**: October 13, 2025  
**Status**: Resolved - Both nodes (dgx030, dgx031) operational with SR-IOV VFs active and nv-ipam functioning correctly
