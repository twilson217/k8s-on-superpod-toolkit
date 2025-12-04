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

### 7. **CRITICAL: Reconfigure TLS Certificate via BCM**

⚠️ **This step is mandatory in BCM-managed environments!**

The ingress-nginx upgrade requires reconfiguring the default SSL certificate. Without this step, applications using ingress will fail with certificate errors.

```bash
# Run BCM Kubernetes setup
cm-kubernetes-setup

# Select option: "Configure Ingress"
# Follow prompts to upload/configure the SSL certificate
# This creates the ingress-server-default-tls secret in ingress-nginx namespace
```

**What this does:**
- Creates `ingress-server-default-tls` secret in `ingress-nginx` namespace
- This is the default certificate referenced by: `--default-ssl-certificate=$(POD_NAMESPACE)/ingress-server-default-tls`
- All ingress resources without specific TLS secrets will use this default certificate

**Verification:**
```bash
# Verify the secret was created
kubectl get secret ingress-server-default-tls -n ingress-nginx

# Check certificate details
kubectl get secret ingress-server-default-tls -n ingress-nginx -o jsonpath='{.data.tls\.crt}' | base64 -d | openssl x509 -noout -subject -issuer -dates

# Test from outside
openssl s_client -connect <your-domain>:443 -servername <your-domain> < /dev/null 2>/dev/null | openssl x509 -noout -subject -issuer
```

### 8. Test Ingress Functionality

```bash
# List all ingresses
kubectl get ingress -A

# Test an existing ingress (check connectivity and certificate)
curl -v -k https://<ingress-hostname>

# Check for certificate errors in logs
kubectl logs -n ingress-nginx deploy/ingress-nginx-controller --tail=100 | grep -i "tls\|certificate\|ssl"
```

### 9. Disable Old Version

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
- ✅ **SSL certificate configured via `cm-kubernetes-setup`**
- ✅ **`ingress-server-default-tls` secret exists in `ingress-nginx` namespace**
- ✅ **Certificate matches your domain (not `ingress.local`)**
- ✅ Applications using ingress are functioning (e.g., Run:AI web UI)
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

### Issue 3: Missing TLS Certificate Configuration (CRITICAL)
**Problem:** After upgrade, applications using ingress (Run:AI) failed with certificate errors:
```
x509: certificate is valid for ingress.local, not <your-domain>
```
Run:AI pods crashed with:
```
failed fetching oidc configuration: dial tcp <ip>:443: connect: no route to host
```

**Root Cause:** The ingress-nginx upgrade did not preserve the TLS certificate secret. The controller fell back to a default self-signed certificate valid for `ingress.local`.

**Symptom Timeline:**
1. After VAST CSI upgrade, Run:AI web UI stopped working
2. Four Run:AI pods entered CrashLoopBackOff: `cluster-api`, `cluster-sync`, `researcher-service`, `runai-agent`
3. Prometheus pod logs showed: `tls: failed to verify certificate: x509: certificate is valid for ingress.local, not <domain>`
4. Ingress was routing traffic, but with wrong certificate

**Solution:** Run BCM's certificate configuration tool:
```bash
cm-kubernetes-setup
# Select: "Configure Ingress"
# Upload/configure your CA-signed SSL certificate
```

This creates the `ingress-server-default-tls` secret in the `ingress-nginx` namespace, which is referenced by the controller's `--default-ssl-certificate` argument.

**Key Insight:** In BCM-managed environments, certificates are managed through `cm-kubernetes-setup`, not manually via `kubectl create secret`. The BCM tool ensures proper integration with the ingress controller configuration.

**Verification After Fix:**
- ✅ `ingress-server-default-tls` secret exists in `ingress-nginx` namespace
- ✅ Certificate is valid for your actual domain
- ✅ Run:AI pods started successfully
- ✅ Run:AI web UI accessible
- ✅ No certificate errors in logs

---

## Files

- **Backup:** `.nosync/working/ingress-controller/backup/bcm-config-v1.12.1.yaml`
- **Original Manifest:** `.nosync/working/ingress-controller/deploy_v1.13.3.yaml`
- **Customized Manifest:** `.nosync/working/ingress-controller/deploy_v1.13.3-customized.yaml`
- **Customization Script:** `.nosync/working/ingress-controller/customize_manifest.py`

---

## Lessons Learned

### BCM Certificate Management
In BCM-managed Kubernetes environments:
1. **Always reconfigure certificates after ingress-nginx upgrades** using `cm-kubernetes-setup`
2. The certificate is stored as `ingress-server-default-tls` in the `ingress-nginx` namespace
3. This is NOT the same as per-ingress TLS secrets (e.g., `runai-backend-tls`)
4. The default certificate is used as a fallback for all ingresses
5. BCM's approach is more robust: one centrally-managed default certificate

### Troubleshooting Certificate Issues
If applications start failing with certificate errors after ingress upgrade:
```bash
# 1. Check if default certificate exists
kubectl get secret ingress-server-default-tls -n ingress-nginx

# 2. Verify certificate domain
kubectl get secret ingress-server-default-tls -n ingress-nginx -o jsonpath='{.data.tls\.crt}' | base64 -d | openssl x509 -noout -subject

# 3. Check ingress controller configuration
kubectl get deployment ingress-nginx-controller -n ingress-nginx -o yaml | grep default-ssl-certificate

# 4. Test certificate from client
openssl s_client -connect <domain>:443 -servername <domain> < /dev/null 2>/dev/null | openssl x509 -noout -subject -issuer

# 5. If certificate is wrong or missing, reconfigure via BCM
cm-kubernetes-setup  # Select "Configure Ingress"
```

---

**Status:** ✅ Complete - Upgrade successful with all issues resolved

