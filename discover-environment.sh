#!/bin/bash

#############################################################################
# Kubernetes & RunAI Environment Discovery Script
# Purpose: Complete pre-upgrade snapshot of the environment
# Output: pre-upgrade-snapshot.txt
#############################################################################

set -e

# Create .logs directory if it doesn't exist
LOGS_DIR=".logs"
mkdir -p "$LOGS_DIR"

OUTPUT_FILE="$LOGS_DIR/pre-upgrade-snapshot.txt"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S %Z')

echo "Starting environment discovery..."
echo "Output will be written to: $OUTPUT_FILE"

# Clear or create output file
> "$OUTPUT_FILE"

#############################################################################
# Helper function to add section headers
#############################################################################
add_section() {
    local title="$1"
    echo "" >> "$OUTPUT_FILE"
    echo "================================================================================" >> "$OUTPUT_FILE"
    echo "  $title" >> "$OUTPUT_FILE"
    echo "================================================================================" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
}

#############################################################################
# Helper function to run command and capture output
#############################################################################
capture_output() {
    local description="$1"
    shift
    echo "Collecting: $description"
    echo "## $description" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
    if "$@" >> "$OUTPUT_FILE" 2>&1; then
        echo "" >> "$OUTPUT_FILE"
    else
        echo "ERROR: Command failed with exit code $?" >> "$OUTPUT_FILE"
        echo "" >> "$OUTPUT_FILE"
    fi
}

#############################################################################
# Start Discovery
#############################################################################

add_section "ENVIRONMENT DISCOVERY REPORT"
echo "Generated: $TIMESTAMP" >> "$OUTPUT_FILE"
echo "Hostname: $(hostname)" >> "$OUTPUT_FILE"
echo "User: $(whoami)" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

#############################################################################
# System Information
#############################################################################
add_section "SYSTEM INFORMATION"

capture_output "Operating System" cat /etc/os-release
capture_output "Kernel Version" uname -a
capture_output "CPU Information" lscpu
capture_output "Memory Information" free -h
capture_output "Disk Usage" df -h

#############################################################################
# Kubernetes Cluster Information
#############################################################################
add_section "KUBERNETES CLUSTER INFORMATION"

capture_output "Kubectl Version" kubectl version --short
capture_output "Cluster Info" kubectl cluster-info
capture_output "Cluster API Versions" kubectl api-versions
capture_output "Cluster API Resources" kubectl api-resources

#############################################################################
# Kubernetes Nodes
#############################################################################
add_section "KUBERNETES NODES"

capture_output "Node List" kubectl get nodes -o wide
capture_output "Node Details (YAML)" kubectl get nodes -o yaml
capture_output "Node Capacity and Allocatable" kubectl describe nodes

#############################################################################
# Namespaces
#############################################################################
add_section "KUBERNETES NAMESPACES"

capture_output "Namespace List" kubectl get namespaces
capture_output "Namespace Details (YAML)" kubectl get namespaces -o yaml

#############################################################################
# Helm Releases
#############################################################################
add_section "HELM RELEASES"

capture_output "Helm Version" helm version
capture_output "Helm Releases (All Namespaces)" helm list --all-namespaces

# Get detailed information for each Helm release
echo "" >> "$OUTPUT_FILE"
echo "## Detailed Helm Release Information" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

helm list --all-namespaces --output json 2>/dev/null | \
    jq -r '.[] | "\(.namespace) \(.name)"' 2>/dev/null | \
    while read -r namespace release; do
        if [ -n "$namespace" ] && [ -n "$release" ]; then
            echo "Collecting: Helm release details for $release in namespace $namespace"
            echo "### Helm Release: $release (Namespace: $namespace)" >> "$OUTPUT_FILE"
            echo "" >> "$OUTPUT_FILE"
            helm get values "$release" -n "$namespace" >> "$OUTPUT_FILE" 2>&1 || echo "Could not retrieve values" >> "$OUTPUT_FILE"
            echo "" >> "$OUTPUT_FILE"
            echo "#### Manifest:" >> "$OUTPUT_FILE"
            helm get manifest "$release" -n "$namespace" >> "$OUTPUT_FILE" 2>&1 || echo "Could not retrieve manifest" >> "$OUTPUT_FILE"
            echo "" >> "$OUTPUT_FILE"
            echo "---" >> "$OUTPUT_FILE"
            echo "" >> "$OUTPUT_FILE"
        fi
    done

#############################################################################
# RunAI Specific Information
#############################################################################
add_section "RUNAI CONFIGURATION"

# Check for RunAI namespaces
RUNAI_NAMESPACES=$(kubectl get namespaces -o json | jq -r '.items[].metadata.name' | grep -i runai || echo "")

if [ -n "$RUNAI_NAMESPACES" ]; then
    echo "## RunAI Namespaces Found:" >> "$OUTPUT_FILE"
    echo "$RUNAI_NAMESPACES" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
    
    for ns in $RUNAI_NAMESPACES; do
        capture_output "RunAI Resources in Namespace: $ns" kubectl get all -n "$ns" -o wide
    done
else
    echo "No RunAI-specific namespaces found" >> "$OUTPUT_FILE"
fi

# Check for RunAI CRDs
capture_output "RunAI Custom Resource Definitions" kubectl get crd | grep -i runai || echo "No RunAI CRDs found"

# Get all RunAI-related CRDs details
RUNAI_CRDS=$(kubectl get crd -o json | jq -r '.items[].metadata.name' | grep -i runai || echo "")
if [ -n "$RUNAI_CRDS" ]; then
    for crd in $RUNAI_CRDS; do
        capture_output "CRD Details: $crd" kubectl get crd "$crd" -o yaml
    done
fi

#############################################################################
# All Pods Across All Namespaces
#############################################################################
add_section "PODS (ALL NAMESPACES)"

capture_output "Pod List (All Namespaces)" kubectl get pods --all-namespaces -o wide
capture_output "Pod Details (YAML)" kubectl get pods --all-namespaces -o yaml

#############################################################################
# Deployments
#############################################################################
add_section "DEPLOYMENTS (ALL NAMESPACES)"

capture_output "Deployment List" kubectl get deployments --all-namespaces -o wide
capture_output "Deployment Details (YAML)" kubectl get deployments --all-namespaces -o yaml

#############################################################################
# StatefulSets
#############################################################################
add_section "STATEFULSETS (ALL NAMESPACES)"

capture_output "StatefulSet List" kubectl get statefulsets --all-namespaces -o wide
capture_output "StatefulSet Details (YAML)" kubectl get statefulsets --all-namespaces -o yaml

#############################################################################
# DaemonSets
#############################################################################
add_section "DAEMONSETS (ALL NAMESPACES)"

capture_output "DaemonSet List" kubectl get daemonsets --all-namespaces -o wide
capture_output "DaemonSet Details (YAML)" kubectl get daemonsets --all-namespaces -o yaml

#############################################################################
# Services
#############################################################################
add_section "SERVICES (ALL NAMESPACES)"

capture_output "Service List" kubectl get services --all-namespaces -o wide
capture_output "Service Details (YAML)" kubectl get services --all-namespaces -o yaml

#############################################################################
# Ingresses
#############################################################################
add_section "INGRESSES (ALL NAMESPACES)"

capture_output "Ingress List" kubectl get ingresses --all-namespaces -o wide
capture_output "Ingress Details (YAML)" kubectl get ingresses --all-namespaces -o yaml

#############################################################################
# ConfigMaps
#############################################################################
add_section "CONFIGMAPS (ALL NAMESPACES)"

capture_output "ConfigMap List" kubectl get configmaps --all-namespaces
capture_output "ConfigMap Details (YAML)" kubectl get configmaps --all-namespaces -o yaml

#############################################################################
# Secrets (names only, not values)
#############################################################################
add_section "SECRETS (ALL NAMESPACES)"

capture_output "Secret List" kubectl get secrets --all-namespaces
echo "## Secret Names and Types (values redacted for security)" >> "$OUTPUT_FILE"
kubectl get secrets --all-namespaces -o json | \
    jq -r '.items[] | "\(.metadata.namespace)/\(.metadata.name) (\(.type))"' >> "$OUTPUT_FILE" 2>&1

#############################################################################
# Persistent Volumes and Claims
#############################################################################
add_section "STORAGE"

capture_output "Persistent Volumes" kubectl get pv -o wide
capture_output "Persistent Volume Details (YAML)" kubectl get pv -o yaml
capture_output "Persistent Volume Claims (All Namespaces)" kubectl get pvc --all-namespaces -o wide
capture_output "Persistent Volume Claim Details (YAML)" kubectl get pvc --all-namespaces -o yaml
capture_output "Storage Classes" kubectl get storageclasses -o wide
capture_output "Storage Class Details (YAML)" kubectl get storageclasses -o yaml

#############################################################################
# Network Policies
#############################################################################
add_section "NETWORK POLICIES"

capture_output "Network Policy List" kubectl get networkpolicies --all-namespaces -o wide
capture_output "Network Policy Details (YAML)" kubectl get networkpolicies --all-namespaces -o yaml

#############################################################################
# RBAC Configuration
#############################################################################
add_section "RBAC CONFIGURATION"

capture_output "Cluster Roles" kubectl get clusterroles
capture_output "Cluster Role Bindings" kubectl get clusterrolebindings
capture_output "Roles (All Namespaces)" kubectl get roles --all-namespaces
capture_output "Role Bindings (All Namespaces)" kubectl get rolebindings --all-namespaces
capture_output "Service Accounts (All Namespaces)" kubectl get serviceaccounts --all-namespaces

#############################################################################
# Custom Resource Definitions
#############################################################################
add_section "CUSTOM RESOURCE DEFINITIONS"

capture_output "CRD List" kubectl get crds
capture_output "CRD Details (YAML)" kubectl get crds -o yaml

#############################################################################
# Jobs and CronJobs
#############################################################################
add_section "JOBS AND CRONJOBS"

capture_output "Job List" kubectl get jobs --all-namespaces -o wide
capture_output "Job Details (YAML)" kubectl get jobs --all-namespaces -o yaml
capture_output "CronJob List" kubectl get cronjobs --all-namespaces -o wide
capture_output "CronJob Details (YAML)" kubectl get cronjobs --all-namespaces -o yaml

#############################################################################
# Resource Quotas and Limit Ranges
#############################################################################
add_section "RESOURCE QUOTAS AND LIMITS"

capture_output "Resource Quotas" kubectl get resourcequotas --all-namespaces
capture_output "Resource Quota Details (YAML)" kubectl get resourcequotas --all-namespaces -o yaml
capture_output "Limit Ranges" kubectl get limitranges --all-namespaces
capture_output "Limit Range Details (YAML)" kubectl get limitranges --all-namespaces -o yaml

#############################################################################
# Priority Classes
#############################################################################
add_section "PRIORITY CLASSES"

capture_output "Priority Class List" kubectl get priorityclasses
capture_output "Priority Class Details (YAML)" kubectl get priorityclasses -o yaml

#############################################################################
# Pod Disruption Budgets
#############################################################################
add_section "POD DISRUPTION BUDGETS"

capture_output "PDB List" kubectl get poddisruptionbudgets --all-namespaces
capture_output "PDB Details (YAML)" kubectl get poddisruptionbudgets --all-namespaces -o yaml

#############################################################################
# Horizontal Pod Autoscalers
#############################################################################
add_section "HORIZONTAL POD AUTOSCALERS"

capture_output "HPA List" kubectl get hpa --all-namespaces
capture_output "HPA Details (YAML)" kubectl get hpa --all-namespaces -o yaml

#############################################################################
# Vertical Pod Autoscalers (if installed)
#############################################################################
add_section "VERTICAL POD AUTOSCALERS"

if kubectl get crd verticalpodautoscalers.autoscaling.k8s.io >/dev/null 2>&1; then
    capture_output "VPA List" kubectl get vpa --all-namespaces
    capture_output "VPA Details (YAML)" kubectl get vpa --all-namespaces -o yaml
else
    echo "VPA CRD not found - skipping" >> "$OUTPUT_FILE"
fi

#############################################################################
# Events
#############################################################################
add_section "RECENT EVENTS (ALL NAMESPACES)"

capture_output "Events" kubectl get events --all-namespaces --sort-by='.lastTimestamp'

#############################################################################
# Component Status
#############################################################################
add_section "COMPONENT STATUS"

capture_output "Component Status" kubectl get componentstatuses || echo "Component status API may be deprecated in this Kubernetes version"

#############################################################################
# Metrics (if metrics-server is installed)
#############################################################################
add_section "METRICS"

if kubectl top nodes >/dev/null 2>&1; then
    capture_output "Node Metrics" kubectl top nodes
    capture_output "Pod Metrics (All Namespaces)" kubectl top pods --all-namespaces
else
    echo "Metrics server not available - skipping metrics collection" >> "$OUTPUT_FILE"
fi

#############################################################################
# GPU Information (NVIDIA)
#############################################################################
add_section "GPU INFORMATION"

if command -v nvidia-smi >/dev/null 2>&1; then
    capture_output "NVIDIA GPU Status" nvidia-smi
    capture_output "NVIDIA GPU Details" nvidia-smi -q
else
    echo "nvidia-smi not found - skipping GPU information" >> "$OUTPUT_FILE"
fi

# Check for GPU operator or device plugin
capture_output "GPU Device Plugin Pods" kubectl get pods --all-namespaces | grep -i "gpu\|nvidia" || echo "No GPU-related pods found"

#############################################################################
# Container Runtime Information
#############################################################################
add_section "CONTAINER RUNTIME"

# Try to detect container runtime
if command -v docker >/dev/null 2>&1; then
    capture_output "Docker Version" docker version
    capture_output "Docker Info" docker info
elif command -v crictl >/dev/null 2>&1; then
    capture_output "CRI-CTL Version" crictl version
    capture_output "CRI-CTL Info" crictl info
elif command -v nerdctl >/dev/null 2>&1; then
    capture_output "Nerdctl Version" nerdctl version
else
    echo "No container runtime CLI found" >> "$OUTPUT_FILE"
fi

#############################################################################
# Kubernetes Configuration Files
#############################################################################
add_section "KUBERNETES CONFIGURATION"

if [ -f /etc/kubernetes/admin.conf ]; then
    echo "## Kubernetes admin.conf exists" >> "$OUTPUT_FILE"
    echo "Path: /etc/kubernetes/admin.conf" >> "$OUTPUT_FILE"
elif [ -f ~/.kube/config ]; then
    echo "## Kubeconfig location" >> "$OUTPUT_FILE"
    echo "Path: ~/.kube/config" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
    echo "Current Context:" >> "$OUTPUT_FILE"
    kubectl config current-context >> "$OUTPUT_FILE" 2>&1
    echo "" >> "$OUTPUT_FILE"
    echo "Available Contexts:" >> "$OUTPUT_FILE"
    kubectl config get-contexts >> "$OUTPUT_FILE" 2>&1
fi

#############################################################################
# Network Plugin Information
#############################################################################
add_section "NETWORK PLUGIN"

# Check for common CNI plugins
capture_output "Calico Resources" kubectl get pods -n kube-system | grep -i calico || echo "Calico not found"
capture_output "Flannel Resources" kubectl get pods -n kube-system | grep -i flannel || echo "Flannel not found"
capture_output "Weave Resources" kubectl get pods -n kube-system | grep -i weave || echo "Weave not found"
capture_output "Cilium Resources" kubectl get pods -n kube-system | grep -i cilium || echo "Cilium not found"

#############################################################################
# Installed Operators
#############################################################################
add_section "OPERATORS"

# Check for Operator Lifecycle Manager
if kubectl get crd clusterserviceversions.operators.coreos.com >/dev/null 2>&1; then
    capture_output "Cluster Service Versions (OLM)" kubectl get csv --all-namespaces
    capture_output "Operator Subscriptions" kubectl get subscriptions --all-namespaces
    capture_output "Install Plans" kubectl get installplans --all-namespaces
else
    echo "OLM not detected" >> "$OUTPUT_FILE"
fi

#############################################################################
# Finalizing
#############################################################################
add_section "DISCOVERY COMPLETE"

echo "Discovery completed at: $(date '+%Y-%m-%d %H:%M:%S %Z')" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

#############################################################################
# Summary
#############################################################################

echo ""
echo "================================================================================"
echo "Discovery Complete!"
echo "================================================================================"
echo ""
echo "Output file: $OUTPUT_FILE"
echo "File size: $(du -h "$OUTPUT_FILE" | cut -f1)"
echo ""
echo "Summary:"
echo "  - Kubernetes cluster information captured"
echo "  - Helm releases documented"
echo "  - All resources across all namespaces recorded"
echo "  - RunAI specific configurations extracted"
echo "  - System and hardware information included"
echo ""
echo "This snapshot can be used for:"
echo "  - Pre-upgrade documentation"
echo "  - Disaster recovery planning"
echo "  - Configuration auditing"
echo "  - Troubleshooting reference"
echo ""
echo "================================================================================"
