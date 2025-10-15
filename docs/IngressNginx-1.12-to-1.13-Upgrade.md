# Ingress-NGINX Upgrade: v1.12.1 → v1.13.3

**Date:** October 15, 2025  
**Environment:** SuperPod with BCM-managed Kubernetes  
**Reason:** Required for Kubernetes 1.33 compatibility (v1.12.1 only supports up to K8s 1.32)

---

## Pre-Upgrade Status

- **Current Version:** v1.12.1
- **Target Version:** v1.13.3
- **Management:** Bright Cluster Manager (BCM)
- **Deployment Strategy:** BCM clone-and-toggle

---

## BCM Customizations

The ingress-nginx deployment has the following BCM-specific settings:

1. **ConfigMap:** `allow-snippet-annotations: "false"` (security)
2. **Service NodePorts:** BCM variables for HTTP/HTTPS ports (main service only, not admission webhook)
3. **Deployment Replicas:** BCM variable `${replicas}`
4. **Pod Scheduling:**
   - **NodeAffinity:** Prefer nodes with `node-role.kubernetes.io/runai-system` label
   - **Tolerations:** Tolerate `node-role.kubernetes.io/control-plane:NoSchedule`
5. **Controller Arguments:**
   - `--publish-service`: LoadBalancer service publication
   - `--default-ssl-certificate`: Default TLS certificate
   - `--enable-metrics=false`: Metrics disabled
   - `--enable-ssl-passthrough`: SSL passthrough enabled

---

## Pre-Upgrade Steps

### 1. Backup Current Configuration

```bash
# Export current BCM config
cmsh -c "device use runai-cluster; applicationconfiguration use ingress-nginx; get" > \
  /home/travisw/dev/k8s-on-superpod-toolkit/.nosync/working/ingress-controller/backup/bcm-config-v1.12.1.yaml
```

### 2. Check Current Status

```bash
# Verify ingress-nginx pods
kubectl get pods -n ingress-nginx

# Check ingress resources
kubectl get ingress -A

# Verify services
kubectl get svc -n ingress-nginx
```

---

## Upgrade Procedure

### 3. Download New Manifest

```bash
# Download ingress-nginx v1.13.3 manifest
curl -L https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.13.3/deploy/static/provider/cloud/deploy.yaml \
  > /home/travisw/dev/k8s-on-superpod-toolkit/.nosync/working/ingress-controller/deploy_v1.13.3.yaml
```

### 4. Apply Customizations

```bash
# Run customization script
cd /home/travisw/dev/k8s-on-superpod-toolkit/.nosync/working/ingress-controller
python3 customize_manifest.py
```

**Output:** `/home/travisw/dev/k8s-on-superpod-toolkit/.nosync/working/ingress-controller/deploy_v1.13.3-customized.yaml`

### 5. BCM Clone-and-Toggle Strategy

```bash
# Clone the current ingress-nginx application
cmsh -c "device use runai-cluster; applicationconfiguration clone ingress-nginx ingress-nginx-v1-13-3"

# Disable the new clone initially
cmsh -c "device use runai-cluster; applicationconfiguration use ingress-nginx-v1-13-3; set enabled=no"

# Update the new clone with v1.13.3 manifest
cmsh -c "device use runai-cluster; applicationconfiguration use ingress-nginx-v1-13-3; \
  set kubernetesresourcesurl=file:///home/travisw/dev/k8s-on-superpod-toolkit/.nosync/working/ingress-controller/deploy_v1.13.3-customized.yaml"

# Enable the new version
cmsh -c "device use runai-cluster; applicationconfiguration use ingress-nginx-v1-13-3; set enabled=yes"

# Wait for pods to be ready
kubectl wait --for=condition=ready pod -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx --timeout=300s
```

### 6. Verify New Version

```bash
# Check pod status
kubectl get pods -n ingress-nginx -o wide

# Verify version
kubectl get deployment -n ingress-nginx ingress-nginx-controller -o yaml | grep "image:"

# Check logs for errors
kubectl logs -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx --tail=50
```

### 7. Test Ingress Functionality

```bash
# List all ingresses
kubectl get ingress -A

# Test an existing ingress (check connectivity)
# curl -k https://<ingress-hostname>

# Check controller logs
kubectl logs -n ingress-nginx deploy/ingress-nginx-controller --tail=100
```

### 8. Disable Old Version

Once the new version is confirmed working:

```bash
# Disable old v1.12.1
cmsh -c "device use runai-cluster; applicationconfiguration use ingress-nginx; set enabled=no"

# Verify old pods are terminated
kubectl get pods -n ingress-nginx --show-labels
```

---

## Post-Upgrade Validation

### Verification Checklist

- ✅ All ingress-nginx pods are `Running`
- ✅ Deployment shows v1.13.3 image
- ✅ No errors in controller logs
- ✅ Existing ingresses still accessible
- ✅ NodePorts functional
- ✅ SSL certificates working
- ✅ No service disruptions reported

---

## Rollback Procedure

If issues occur:

```bash
# Re-enable old version
cmsh -c "device use runai-cluster; applicationconfiguration use ingress-nginx; set enabled=yes"

# Disable new version
cmsh -c "device use runai-cluster; applicationconfiguration use ingress-nginx-v1-13-3; set enabled=no"

# Wait for old pods to be ready
kubectl wait --for=condition=ready pod -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx --timeout=300s

# Verify rollback
kubectl get pods -n ingress-nginx -o wide
```

---

## Key Differences: v1.12.1 → v1.13.3

### Image Updates
- **Controller:** `v1.12.1` → `v1.13.3`
- **Webhook Certgen:** `v1.5.2` → `v1.6.3`

### New Features
- Improved Kubernetes 1.33 compatibility
- Enhanced webhook certificate management
- Performance improvements
- Bug fixes and security updates

### Behavioral Changes
- Added `ttlSecondsAfterFinished: 0` to admission Jobs (immediate cleanup)
- Enhanced `automountServiceAccountToken` explicit settings

---

## Issues Resolved During Upgrade

### Issue 1: ClusterIP Service with NodePort
**Problem:** Initial manifest incorrectly added `nodePort` to the admission webhook service (type: ClusterIP).  
**Symptom:** Namespace stuck in create/delete loop, pods terminating immediately.  
**Solution:** Updated customization script to only add `nodePort` to the main service (type: NodePort), not the admission webhook service.

### Issue 2: Missing NodeAffinity
**Problem:** Pods were scheduling on GPU nodes (DGXs) instead of control-plane nodes.  
**Solution:** Added `nodeAffinity` to prefer nodes with `node-role.kubernetes.io/runai-system` label, ensuring pods run on control-plane/management nodes.

---

## Files

- **Backup:** `.nosync/working/ingress-controller/backup/bcm-config-v1.12.1.yaml`
- **Original Manifest:** `.nosync/working/ingress-controller/deploy_v1.13.3.yaml`
- **Customized Manifest:** `.nosync/working/ingress-controller/deploy_v1.13.3-customized.yaml`
- **Customization Script:** `.nosync/working/ingress-controller/customize_manifest.py`

---

**Status:** Ready for execution

