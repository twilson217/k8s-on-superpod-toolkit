# Kubernetes 1.31.9 to 1.32.9 Control Plane Upgrade

**Environment:** BCM-managed Superpod (Ubuntu)  
**Date:** October 20, 2025  
**Upgrade Path:** v1.31.9 → v1.32.9

---

## ⚠️ IMPORTANT: BCM Version Support Limitation

**BCM Support verified that `cm-kubernetes-setup` supports Kubernetes up to v1.32.x only.**

🔴 **DO NOT upgrade to Kubernetes 1.33** until BCM releases updated tooling with 1.33 support.

To verify supported versions on your system:
```bash
cm-kubernetes-setup --list-versions
```

---

## 📋 Table of Contents

1. [Pre-Upgrade Preparation](#pre-upgrade-preparation)
2. [Upgrade Procedure](#upgrade-procedure)
3. [Critical Issues & Resolutions](#critical-issues--resolutions)
4. [Post-Upgrade Validation](#post-upgrade-validation)
5. [BCM-Specific Steps](#bcm-specific-steps)
6. [Rollback Procedure](#rollback-procedure)

---

## 🎯 Pre-Upgrade Preparation

### 1. Verify BCM Support
```bash
# Check supported K8s versions
cm-kubernetes-setup --list-versions

# Expected output should include 1.32.x
# If 1.32 is NOT listed, DO NOT proceed
```

### 2. Backup Current State
```bash
# Backup etcd
sudo ETCDCTL_API=3 etcdctl --endpoints=https://127.0.0.1:2379 \
  --cacert=/etc/kubernetes/pki/runaicluster/etcd/ca.crt \
  --cert=/etc/kubernetes/pki/runaicluster/etcd/server.crt \
  --key=/etc/kubernetes/pki/runaicluster/etcd/server.key \
  snapshot save /backup/etcd-snapshot-$(date +%Y%m%d-%H%M%S).db

# Backup critical manifests
mkdir -p ~/k8s-backup/1.31-to-1.32
kubectl get nodes -o yaml > ~/k8s-backup/1.31-to-1.32/nodes.yaml
kubectl get pods -A -o yaml > ~/k8s-backup/1.31-to-1.32/all-pods.yaml
kubectl -n kube-system get cm kubeadm-config -o yaml > ~/k8s-backup/1.31-to-1.32/kubeadm-config.yaml

# Backup kube-apiserver manifest
sudo cp /etc/kubernetes/manifests/kube-apiserver.yaml ~/k8s-backup/1.31-to-1.32/kube-apiserver-1.31.yaml
sudo cp /etc/kubernetes/manifests/kube-controller-manager.yaml ~/k8s-backup/1.31-to-1.32/kube-controller-manager-1.31.yaml
sudo cp /etc/kubernetes/manifests/kube-scheduler.yaml ~/k8s-backup/1.31-to-1.32/kube-scheduler-1.31.yaml

# Backup LoadBalancer service specs (CRITICAL for BCM!)
kubectl -n ingress-nginx get svc ingress-nginx-controller -o yaml > ~/k8s-backup/1.31-to-1.32/ingress-nginx-lb.yaml
kubectl -n runai get svc -l app=runai -o yaml > ~/k8s-backup/1.31-to-1.32/runai-lb.yaml
```

### 3. Pre-Upgrade Checklist
- [ ] BCM `cm-kubernetes-setup --list-versions` shows 1.32.x support
- [ ] Etcd backup completed and verified
- [ ] All critical manifests backed up
- [ ] LoadBalancer service specs saved (ingress-nginx, Run:AI)
- [ ] TLS certificates documented (will need to reconfigure)
- [ ] Cluster is healthy (all nodes Ready, no CrashLooping pods)
- [ ] Recent application backups completed
- [ ] Maintenance window scheduled
- [ ] Rollback plan reviewed

---

## 🔧 Upgrade Procedure

### Phase 1: Update APT Repository

On **each control plane node**:

```bash
# Update Kubernetes apt repository
sudo vi /etc/apt/sources.list.d/kubernetes.list

# Change from:
# deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.31/deb/ /

# To:
# deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.32/deb/ /

# Update package list
sudo apt-get update

# Verify 1.32.9 is available
apt-cache madison kubeadm | grep 1.32
```

### Phase 2: Upgrade First Control Plane Node (Head Node)

```bash
# Unhold packages
sudo apt-mark unhold kubeadm kubelet kubectl

# Install kubeadm 1.32.9
sudo apt-get install -y kubeadm=1.32.9-1.1

# Hold kubeadm
sudo apt-mark hold kubeadm

# Verify version
kubeadm version

# Check upgrade plan
sudo kubeadm upgrade plan

# Apply upgrade (head node)
sudo kubeadm upgrade apply v1.32.9

# Upgrade kubelet and kubectl
sudo apt-get install -y kubelet=1.32.9-1.1 kubectl=1.32.9-1.1
sudo apt-mark hold kubelet kubectl

# Restart kubelet
sudo systemctl daemon-reload
sudo systemctl restart kubelet
```

### Phase 3: Fix kube-apiserver Manifest (CRITICAL!)

🔴 **After the upgrade, kube-apiserver will CRASH with Exit Code 1**

**Root Cause:** The `kubeadm upgrade` process:
1. Empties the `--etcd-servers` flag
2. Leaves deprecated `--feature-gates=MaxUnavailableStatefulSet=true`

**Fix:**
```bash
# Edit the kube-apiserver manifest
sudo vi /etc/kubernetes/manifests/kube-apiserver.yaml

# CHANGE 1: Restore etcd-servers
# Find: - --etcd-servers=
# Change to: - --etcd-servers=https://NODE1_IP:2379,https://NODE2_IP:2379,https://NODE3_IP:2379
# Example: - --etcd-servers=https://165.123.217.16:2379,https://165.123.217.17:2379,https://165.123.217.18:2379

# CHANGE 2: Remove deprecated feature gate
# Delete this entire line:
# - --feature-gates=MaxUnavailableStatefulSet=true

# Save and exit - kubelet will automatically restart the pod
```

**Verification:**
```bash
# Watch for kube-apiserver to start
watch kubectl -n kube-system get pod -l component=kube-apiserver

# Check logs for errors
kubectl -n kube-system logs kube-apiserver-<NODE_NAME> --previous

# Verify API server is responding
kubectl get nodes
```

### Phase 4: Upgrade Additional Control Plane Nodes

For **each additional control plane node** (runai-02, runai-03, etc.):

```bash
# SSH to the node
ssh <control-plane-node>

# Unhold packages
sudo apt-mark unhold kubeadm kubelet kubectl

# Install kubeadm 1.32.9
sudo apt-get install -y kubeadm=1.32.9-1.1
sudo apt-mark hold kubeadm

# Apply upgrade (NOT "apply", use "node" for additional nodes)
sudo kubeadm upgrade node

# Edit kube-apiserver manifest (SAME FIXES AS HEAD NODE!)
sudo vi /etc/kubernetes/manifests/kube-apiserver.yaml
# 1. Restore --etcd-servers
# 2. Remove --feature-gates line

# Upgrade kubelet and kubectl
sudo apt-get install -y kubelet=1.32.9-1.1 kubectl=1.32.9-1.1
sudo apt-mark hold kubelet kubectl

# Restart kubelet
sudo systemctl daemon-reload
sudo systemctl restart kubelet

# From head node: verify this node's API server is running
kubectl -n kube-system get pod kube-apiserver-<NODE_NAME>
```

### Phase 5: Upgrade Worker Nodes

**IMPORTANT:** In BCM environments, worker nodes are upgraded via **software images**. See [BCM-Kubernetes-Upgrade-Requirements.md](BCM-Kubernetes-Upgrade-Requirements.md) for detailed procedure.

```bash
# Update software image (on BCM head node)
cm-chroot-sw-img /cm/images/default-image

# Update kubernetes apt source
vi /etc/apt/sources.list.d/kubernetes.list
# Change v1.31 to v1.32

# Update packages
apt-mark unhold kubeadm kubelet kubectl
apt-get update
apt-get install -y kubeadm=1.32.9-1.1 kubelet=1.32.9-1.1 kubectl=1.32.9-1.1
apt-mark hold kubeadm kubelet kubectl
exit

# Apply image and upgrade each worker node
export host=dgx030
cmsh -c "device use $host; imageupdate -w --wait"
ssh $host sudo kubeadm upgrade node
kubectl drain $host --ignore-daemonsets --delete-emptydir-data
ssh $host sudo systemctl daemon-reload
ssh $host sudo systemctl restart kubelet
kubectl uncordon $host

# Repeat for each worker node
```

---

## 🔥 Critical Issues & Resolutions

### Issue 1: kube-apiserver CrashLoopBackOff - Missing etcd-servers

**Symptom:**
```
kube-apiserver-runai-01   0/1   CrashLoopBackOff   4   2m
```

**Diagnosis:**
```bash
kubectl -n kube-system logs kube-apiserver-runai-01 --previous
# Output: E1020 15:45:29.558679 1 run.go:72] "command failed" err="--etcd-servers must be specified"

kubectl -n kube-system describe pod kube-apiserver-runai-01 | grep etcd-servers
# Output: --etcd-servers=   (EMPTY!)
```

**Root Cause:** `kubeadm upgrade` empties the `--etcd-servers` flag

**Resolution:**
```bash
sudo vi /etc/kubernetes/manifests/kube-apiserver.yaml
# Restore: - --etcd-servers=https://NODE1:2379,https://NODE2:2379,https://NODE3:2379
```

**Time to Resolution:** Immediate (kubelet auto-restarts pod)

---

### Issue 2: Deprecated Feature Gate - MaxUnavailableStatefulSet

**Symptom:**
```
Flag --default-watch-cache-size has been deprecated
```

**Diagnosis:**
```bash
grep feature-gates /etc/kubernetes/manifests/kube-apiserver.yaml
# Output: - --feature-gates=MaxUnavailableStatefulSet=true
```

**Root Cause:** 
- `MaxUnavailableStatefulSet` graduated to GA in K8s 1.31
- Feature gate was **removed** in K8s 1.32
- Having it in the manifest causes deprecation warnings (or failures in future versions)

**Resolution:**
```bash
sudo vi /etc/kubernetes/manifests/kube-apiserver.yaml
# Delete the entire line: - --feature-gates=MaxUnavailableStatefulSet=true
```

**Impact:** Low (currently just a warning, but will break in future K8s versions)

---

### Issue 3: Calico Pods Cycling - Tigera Operator Conflict

**Symptom:**
```
calico-kube-controllers-* pods appearing, then disappearing repeatedly
calico-node DaemonSet pods Running, but controller pod never stabilizes
```

**Diagnosis:**
```bash
kubectl get deployments -A | grep tigera
# Output: tigera-operator   1/1   1   1   5d22h

kubectl get installation -A
# If this returns resources, Tigera Operator is ACTIVE and conflicting with BCM
```

**Root Cause:** 
- **BCM manages Calico** via direct manifest application
- **Tigera Operator** is an alternative Calico installation method
- **Both cannot coexist** - they fight over the same resources
- Previous technician may have installed Tigera Operator by mistake

**Resolution:**
```bash
# Delete Tigera Operator
kubectl delete deployment tigera-operator -n tigera-operator

# If Installation CRs exist, delete those too
kubectl delete installation --all -A

# Wait for BCM to recreate Calico pods (happens automatically)
watch kubectl -n kube-system get pods -l k8s-app=calico-kube-controllers
```

**Prevention:** Never install Tigera Operator in BCM-managed environments. BCM handles Calico lifecycle.

**Time to Resolution:** 2-3 minutes after operator deletion

---

### Issue 4: LoadBalancer Services Disappeared

**Symptom:**
```
ingress-nginx LoadBalancer service: MISSING
Run:AI LoadBalancer service: MISSING
Pods exist, but services don't
```

**Diagnosis:**
```bash
kubectl -n ingress-nginx get svc
# ingress-nginx-controller service is GONE

kubectl -n runai get svc
# Main Run:AI LoadBalancer service is GONE
```

**Root Cause:** 
Unknown. Possibly:
- BCM application reconciliation during upgrade
- Control plane upgrade side effect
- Service type LoadBalancer behavior during K8s version change

**Resolution:**

**For ingress-nginx:**
```bash
# Recreate LoadBalancer service from backup
kubectl apply -f ~/k8s-backup/1.31-to-1.32/ingress-nginx-lb.yaml

# OR recreate manually (if no backup)
# Use Helm to reinstall with same values
helm upgrade ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx \
  --reuse-values
```

**For Run:AI:**
```bash
# Recreate from backup
kubectl apply -f ~/k8s-backup/1.31-to-1.32/runai-lb.yaml

# Verify MetalLB assigned the same IP
kubectl -n runai get svc -l app=runai -o wide
```

**Critical Follow-up:** After recreating ingress-nginx LoadBalancer, you **MUST reconfigure TLS certificates** (see Issue 5)

**Time to Resolution:** 5-10 minutes per service

---

### Issue 5: Ingress TLS Certificate Lost (CRITICAL for Run:AI)

**Symptom:**
```
Run:AI web UI shows certificate error
ingress-nginx using default self-signed cert
Run:AI pods may be CrashLooping (cluster-api, cluster-sync, researcher-service, runai-agent)
```

**Diagnosis:**
```bash
kubectl -n ingress-nginx get secret
# ingress-server-default-tls is MISSING or shows "ingress.local"

openssl s_client -connect <RUNAI_HOSTNAME>:443 -servername <RUNAI_HOSTNAME> < /dev/null 2>/dev/null | openssl x509 -noout -subject
# Subject shows "ingress.local" instead of your actual domain
```

**Root Cause:** 
- When ingress-nginx LoadBalancer service is recreated, TLS secret is lost
- BCM-managed environments require `cm-kubernetes-setup` to properly configure certificates

**Resolution (BCM-Specific):**
```bash
# Reconfigure TLS certificate via BCM tool
cm-kubernetes-setup

# Choose: "Configure Ingress"
# Select your CA-signed certificate (you should have this from initial setup)
# BCM will create the ingress-server-default-tls secret

# Verify secret was created
kubectl -n ingress-nginx get secret ingress-server-default-tls

# Restart Run:AI pods to pick up new certificate
kubectl -n runai-backend delete pods --all
# Wait for all pods to come up
kubectl -n runai delete pods --all
```

**Verification:**
```bash
# Test certificate
openssl s_client -connect <RUNAI_HOSTNAME>:443 -servername <RUNAI_HOSTNAME> < /dev/null 2>/dev/null | openssl x509 -noout -subject -dates

# Access Run:AI web UI
# Should load without certificate errors
```

**Time to Resolution:** 10-15 minutes (including Run:AI pod restarts)

**Reference:** See [IngressNginx-1.12-to-1.13-Upgrade.md](IngressNginx-1.12-to-1.13-Upgrade.md) for detailed certificate management

---

## ✅ Post-Upgrade Validation

### 1. Verify Control Plane Version
```bash
kubectl get nodes
# All control plane nodes should show v1.32.9

kubectl version --short
# Client and Server should both be v1.32.9
```

### 2. Verify All Control Plane Components
```bash
kubectl -n kube-system get pods -l tier=control-plane
# All kube-apiserver, kube-controller-manager, kube-scheduler pods should be Running

# Check specific component versions
kubectl -n kube-system describe pod kube-apiserver-runai-01 | grep Image:
# Should show: registry.k8s.io/kube-apiserver:v1.32.9
```

### 3. Verify Calico (CNI)
```bash
kubectl -n kube-system get pods -l k8s-app=calico-node
# All calico-node pods Running (1 per node)

kubectl -n kube-system get pods -l k8s-app=calico-kube-controllers
# 1 controller pod Running

# Verify no Tigera Operator
kubectl get deployments -A | grep tigera
# Should return NO results
```

### 4. Verify LoadBalancer Services
```bash
# Check ingress-nginx
kubectl -n ingress-nginx get svc ingress-nginx-controller
# Should show EXTERNAL-IP (MetalLB assigned)

# Check Run:AI
kubectl -n runai get svc -l app=runai
# Should show EXTERNAL-IP
```

### 5. Verify TLS Certificates
```bash
# Check ingress certificate secret
kubectl -n ingress-nginx get secret ingress-server-default-tls

# Verify certificate is correct (not ingress.local)
openssl s_client -connect <RUNAI_HOSTNAME>:443 -servername <RUNAI_HOSTNAME> < /dev/null 2>/dev/null | openssl x509 -noout -subject

# Test Run:AI web UI
# Should be accessible without certificate errors
```

### 6. Run Health Check Scripts
```bash
# Test ingress-nginx
python3 healthcheck_ingress-nginx.py

# Test storage functionality
python3 healthcheck_storage.py

# Test Run:AI workload submission (if available)
python3 b200_runai_nccl_test.py --project test --nodes 1
```

### 7. Verify Core Workloads
```bash
# Check all namespaces for issues
kubectl get pods -A | grep -v Running | grep -v Completed

# Check for recent errors
kubectl get events -A --sort-by='.lastTimestamp' | grep -i error | tail -20

# Verify GPU operator
kubectl -n gpu-operator get pods
```

---

## 🏢 BCM-Specific Steps

### 1. Update BCM Kubernetes Version Metadata

**CRITICAL:** BCM tracks Kubernetes version independently. You MUST update this after the upgrade.

```bash
cmsh
[basecm10]% kubernetes
[basecm10->kubernetes[default]]% get version
# Shows old version: 1.31.9-1.1

# Get the new version
[basecm10->kubernetes[default]]% !apt-cache policy kubeadm | grep Installed
Installed: 1.32.9-1.1

# Set the new version in BCM
[basecm10->kubernetes[default]]% set version 1.32.9-1.1
[basecm10->kubernetes*[default*]]% commit
[basecm10->kubernetes[default]]% quit

# Verify the change
module load kubernetes/<TAB><TAB>
# Should show: kubernetes/default/1.32.9-1.1
```

### 2. Verify BCM Applications Status
```bash
cmsh -c "kubernetes;appgroups;use system;applications;list"

# Ensure all applications are enabled:
# - calico-v3.30 (enabled: yes)
# - NO tigera-operator or calico-v3.29 should be present/enabled
```

### 3. Update Worker Node Software Images

See [BCM-Kubernetes-Upgrade-Requirements.md](BCM-Kubernetes-Upgrade-Requirements.md) for complete procedure.

---

## 🔄 Rollback Procedure

If critical issues occur during upgrade:

### Rollback Control Plane (Head Node)

```bash
# Restore etcd from backup
sudo systemctl stop etcd
sudo rm -rf /var/lib/etcd
sudo ETCDCTL_API=3 etcdctl snapshot restore /backup/etcd-snapshot-<timestamp>.db \
  --data-dir=/var/lib/etcd
sudo systemctl start etcd

# Downgrade packages
sudo apt-mark unhold kubeadm kubelet kubectl
sudo apt-get install -y \
  kubeadm=1.31.9-1.1 \
  kubelet=1.31.9-1.1 \
  kubectl=1.31.9-1.1
sudo apt-mark hold kubeadm kubelet kubectl

# Restore manifests
sudo cp ~/k8s-backup/1.31-to-1.32/kube-apiserver-1.31.yaml /etc/kubernetes/manifests/kube-apiserver.yaml
sudo cp ~/k8s-backup/1.31-to-1.32/kube-controller-manager-1.31.yaml /etc/kubernetes/manifests/kube-controller-manager.yaml
sudo cp ~/k8s-backup/1.31-to-1.32/kube-scheduler-1.31.yaml /etc/kubernetes/manifests/kube-scheduler.yaml

# Restart kubelet
sudo systemctl daemon-reload
sudo systemctl restart kubelet
```

### Rollback BCM Metadata

```bash
cmsh
[basecm10]% kubernetes
[basecm10->kubernetes[default]]% set version 1.31.9-1.1
[basecm10->kubernetes*[default*]]% commit
[basecm10->kubernetes[default]]% quit
```

---

## 📊 Upgrade Summary

| Component | Before | After | Issues Encountered |
|-----------|--------|-------|-------------------|
| Control Plane | v1.31.9 | v1.32.9 | kube-apiserver crash (etcd-servers empty) |
| Worker Nodes | v1.31.9 | v1.32.9 | Via BCM software images |
| Calico | v3.30.3 | v3.30.3 | Tigera Operator conflict |
| ingress-nginx | v1.13.3 | v1.13.3 | LoadBalancer service disappeared |
| Run:AI | (stable) | (stable) | LoadBalancer service + TLS cert issues |

**Total Downtime:** ~30-45 minutes (mainly due to troubleshooting certificate issues)

**Actual Upgrade Time:** ~15 minutes per control plane node (when issues are known)

---

## 📝 Lessons Learned

### 1. **Always Backup LoadBalancer Service Specs**
BCM upgrades may remove LoadBalancer services. Save specs before upgrade.

### 2. **kube-apiserver Manifest Requires Manual Fixes**
- `--etcd-servers` gets cleared
- Deprecated feature gates remain and must be removed
- **These fixes are NOT documented in standard K8s upgrade guides**

### 3. **Tigera Operator Conflicts with BCM Calico Management**
Never use Tigera Operator in BCM environments. BCM manages Calico directly.

### 4. **TLS Certificates Require BCM-Specific Reconfiguration**
`cm-kubernetes-setup` is REQUIRED to properly configure ingress TLS certificates.

### 5. **BCM Version Support is Critical**
Always verify BCM supports the target K8s version BEFORE starting the upgrade.

### 6. **BCM Metadata Update is Mandatory**
The upgrade is NOT complete until BCM's Kubernetes version metadata is updated via `cmsh`.

---

## 📚 References

- **BCM Documentation:** [BCM-Kubernetes-Upgrade-Requirements.md](BCM-Kubernetes-Upgrade-Requirements.md)
- **Upstream Kubernetes Docs:** https://kubernetes.io/docs/tasks/administer-cluster/kubeadm/kubeadm-upgrade/
- **Calico Compatibility:** https://docs.tigera.io/calico/latest/getting-started/kubernetes/requirements
- **Related Upgrades:** 
  - [IngressNginx-1.12-to-1.13-Upgrade.md](IngressNginx-1.12-to-1.13-Upgrade.md)
  - [Calico-3.29-to-3.30-Upgrade.md](Calico-3.29-to-3.30-Upgrade.md)

---

## ✅ Sign-Off Checklist

- [ ] All control plane nodes upgraded to 1.32.9
- [ ] All worker nodes upgraded to 1.32.9
- [ ] BCM Kubernetes version metadata updated
- [ ] kube-apiserver manifests fixed (etcd-servers, feature gates)
- [ ] Tigera Operator removed (if present)
- [ ] LoadBalancer services recreated (ingress-nginx, Run:AI)
- [ ] TLS certificates reconfigured via `cm-kubernetes-setup`
- [ ] All health check scripts passing
- [ ] Run:AI web UI accessible and functional
- [ ] Test workloads successfully submitted
- [ ] No CrashLooping pods
- [ ] Documentation updated with any additional findings

---

**Upgrade Completed:** [Date]  
**Performed By:** [Name]  
**Cluster Status:** ✅ Healthy and operational on Kubernetes v1.32.9

