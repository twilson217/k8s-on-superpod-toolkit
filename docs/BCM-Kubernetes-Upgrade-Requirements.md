# BCM-Specific Requirements for Kubernetes Control Plane Upgrades

**Source:** BCM Containerization Manual, Section 4.22  
**Environment:** Superpod (Ubuntu-based) - All commands use Ubuntu/apt syntax

---

## 🔴 Critical BCM-Specific Steps

### 1. **Update BCM Kubernetes Version Metadata** (REQUIRED)

After upgrading the Kubernetes control plane, you **MUST manually update the version in BCM** to match the new Kubernetes version.

**Location:** Section 4.22.7 - Updating The Status In BCM

```bash
# Check current BCM Kubernetes version
module load kubernetes/<TAB><TAB>
# Example output: kubernetes/default/1.27.13-150500.2.1

# Update BCM to reflect new version
cmsh
[basecm10]% kubernetes
[basecm10->kubernetes[default]]% get version
# Shows: 1.27.13-150500.2.1

# Get the new version info (Ubuntu)
[basecm10->kubernetes[default]]% !apt-cache policy kubeadm | grep -E '(Installed|Candidate)'
Installed: 1.28.9-1.1
Candidate: 1.28.9-1.1

# Set the new version in BCM
[basecm10->kubernetes[default]]% set version 1.28.9-1.1
[basecm10->kubernetes*[default*]]% commit
[basecm10->kubernetes[default]]% quit

# Verify the change
module load kubernetes/<TAB><TAB>
# Should show: kubernetes/default/1.28.9-1.1
```

**Why This Matters:**
- BCM tracks Kubernetes versions independently from the actual installed version
- Module files won't reflect correct version until BCM is updated
- Automation and monitoring may rely on this metadata

---

### 2. **Software Image Management for Non-Head Nodes**

BCM uses **software images** to provision compute nodes. When upgrading Kubernetes on compute nodes, you must update the software image.

**Process (Ubuntu):**
1. Enter the software image via chroot
2. Update `/etc/apt/sources.list.d/kubernetes.list` to new minor version
3. Unhold, update, and re-hold kubeadm, kubelet, kubectl packages
4. Exit chroot
5. Update nodes using the software image

**Example for compute nodes (Ubuntu):**
```bash
# Find the software image for a node
cmsh
[basecm10]% device use node001
[basecm10->device[node001]]% get softwareimage
default-image (category:default)
[basecm10->device[node001]]% softwareimage
[basecm10->softwareimage]% use default-image
[basecm10->softwareimage[default-image]]% get path
/cm/images/default-image

# Enter chroot and update packages
cm-chroot-sw-img /cm/images/default-image
[root@default-image /]# vi /etc/apt/sources.list.d/kubernetes.list
# Change v1.27 to v1.28 in the deb line
# Example: deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.28/deb/ /

[root@default-image /]# apt-mark unhold kubeadm kubelet kubectl
[root@default-image /]# apt-get update
[root@default-image /]# apt-get install -y kubeadm kubelet kubectl
[root@default-image /]# apt-mark hold kubeadm kubelet kubectl
[root@default-image /]# exit

# Update the node with new software image
export host=node001
cmsh -c "device use $host; imageupdate -w --wait"
ssh $host kubeadm upgrade node
kubectl drain $host --ignore-daemonsets
ssh $host sudo systemctl daemon-reload
ssh $host sudo systemctl restart kubelet
kubectl uncordon $host
```

---

### 3. **Check Supported Kubernetes Versions**

BCM only supports specific Kubernetes versions. Always verify before upgrading:

```bash
cm-kubernetes-setup --list-versions
```

**Example output:**
```
1.30
1.29 (NVIDIA AI Enterprise certified)
1.28 (NVIDIA AI Enterprise certified)
1.27 (NVIDIA AI Enterprise certified)
```

---

### 4. **Ingress Certificate Reconfiguration** (If Using Ingress)

**⚠️ CRITICAL:** Based on our recent experience, after upgrading Kubernetes, the ingress-nginx controller may lose its certificate configuration in BCM-managed environments.

**Solution:** Run `cm-kubernetes-setup` after the upgrade:
```bash
cm-kubernetes-setup
# Choose: Configure Ingress → Configure Ingress Server Certificate
# Follow prompts to reconfigure the CA-signed SSL certificate
```

**Reference:** 
- Section 4.22.11 - Configuring The Ingress HTTPS Server Certificate
- Our experience: [IngressNginx-1.12-to-1.13-Upgrade.md](IngressNginx-1.12-to-1.13-Upgrade.md)

---

## 🔄 General Upgrade Flow for BCM Clusters

### Order of Operations:
1. **Head Node** (first control plane) - if head node runs control plane
2. **Remaining Control Plane Nodes** - one at a time
3. **Worker Nodes** - one at a time (or in small batches)
4. **Update BCM Kubernetes Version** - critical final step!

### Key Differences from Standard Kubernetes Upgrades:

| Standard Kubernetes | BCM Kubernetes (Ubuntu) |
|---------------------|-------------------------|
| Direct package updates | Software image updates for compute nodes |
| Version tracked by kubeadm | Version tracked by BCM + kubeadm |
| Single upgrade procedure | Different procedures for head node vs. compute nodes |
| - | Must update BCM metadata after upgrade |
| `apt-get install` directly | `apt-mark unhold` → update → `apt-mark hold` in chroot |

---

## 📋 Pre-Upgrade Checklist

- [ ] Verify target version is supported: `cm-kubernetes-setup --list-versions`
- [ ] Back up etcd database
- [ ] Review third-party components (CNI, CSI, GPU Operator, etc.)
- [ ] Plan for DaemonSet handling (`--ignore-daemonsets`)
- [ ] Identify software images used by compute nodes
- [ ] Plan capacity for pod migration during node drains
- [ ] Test in non-production environment first

---

## 📋 Post-Upgrade Checklist

- [ ] Verify all nodes show new version: `kubectl get nodes`
- [ ] **Update BCM Kubernetes version metadata** ← CRITICAL!
- [ ] Verify module file shows correct version: `module load kubernetes/<TAB><TAB>`
- [ ] Reconfigure ingress certificate if using ingress-nginx: `cm-kubernetes-setup`
- [ ] Test critical applications (Run:AI, ingress, storage, GPU workloads)
- [ ] Verify CNI/CSI/GPU Operator functionality
- [ ] Update monitoring/alerting for new version

---

## 🔍 BCM-Specific Troubleshooting

### Issue: Nodes show old version after image update
**Solution:** Ensure `imageupdate` completed successfully and node rebooted with new image

### Issue: Module file shows old Kubernetes version
**Solution:** Update BCM metadata using `cmsh` (see section 1 above)

### Issue: Ingress certificate errors after upgrade
**Solution:** Reconfigure certificate using `cm-kubernetes-setup` → Configure Ingress

### Issue: Compute nodes fail to provision with new version
**Solution:** Verify software image was updated in chroot before node updates

---

## 📚 References

- **BCM Documentation:** `.nosync/bcm-docs/containerization-manual.txt`, Section 4.22
  - Section 4.22.8: Notes For Ubuntu (command translations from RHEL)
- **Upstream Kubernetes Docs:** https://kubernetes.io/docs/tasks/administer-cluster/kubeadm/kubeadm-upgrade/
- **CAPI Upgrade Guide:** https://cluster-api.sigs.k8s.io/tasks/upgrading-clusters.html

---

## 🔄 RHEL vs Ubuntu Command Reference

Since the BCM manual primarily uses RHEL examples, here's a quick reference (from BCM Manual Section 4.22.8):

| Task | RHEL/Rocky | Ubuntu (Superpod) |
|------|------------|-------------------|
| Check repo config | `grep v /etc/yum.repos.d/kubernetes.repo` | `grep v /etc/apt/sources.list.d/kubernetes.list` |
| Edit repo config | `vi /etc/yum.repos.d/kubernetes.repo` | `vi /etc/apt/sources.list.d/kubernetes.list` |
| List available versions | `yum list --showduplicates kubeadm --disableexcludes=kubernetes` | `apt-get update && apt-cache madison kubeadm` |
| Install packages | `yum install -y kubeadm kubelet kubectl --disableexcludes=kubernetes` | `apt-mark unhold kubeadm kubelet kubectl && apt-get update && apt-get install -y kubeadm kubelet kubectl && apt-mark hold kubeadm kubelet kubectl` |
| Get version info | `yum info kubeadm` | `apt-cache policy kubeadm` |

**Note:** Ubuntu uses `apt-mark hold` to prevent automatic updates of critical packages like kubeadm/kubelet/kubectl. You must `unhold` before upgrading, then `hold` again after.

---

## 💡 Key Insights

1. **BCM is a Meta-Layer:** BCM manages Kubernetes but doesn't automatically track version changes
2. **Software Images Are Key:** Compute nodes get their binaries from software images, not direct package managers
3. **Certificate Management:** BCM has special handling for ingress certificates that standard Kubernetes doesn't
4. **Version Support:** Not all Kubernetes versions work with BCM - always check supported versions first
5. **Manual Metadata Update:** The BCM version update is **not automatic** - forgetting this step causes confusion later

---

**Last Updated:** 2025-10-16  
**Related Documentation:**
- [IngressNginx-1.12-to-1.13-Upgrade.md](IngressNginx-1.12-to-1.13-Upgrade.md) - Ingress upgrade with BCM certificate fix
- [K8s-1.31-to-1.33-Upgrade-Plan.md](.logs/k8s-high-level-upgrade-plan.md) - Overall upgrade strategy

