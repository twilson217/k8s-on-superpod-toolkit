#!/bin/bash

# Script to replace all deprecated Kubernetes labels
# - beta.kubernetes.io/os → kubernetes.io/os
# - node-role.kubernetes.io/master → node-role.kubernetes.io/control-plane

NAMESPACE="network-operator"

echo "Fixing deprecated Kubernetes labels in namespace: $NAMESPACE"
echo "=============================================================="

# Function to update resources
update_resource() {
    local resource_type=$1
    local resource_name=$2
    local namespace=$3
    
    kubectl get $resource_type $resource_name -n $namespace -o yaml | \
        sed 's/beta\.kubernetes\.io\/os/kubernetes.io\/os/g' | \
        sed 's/node-role\.kubernetes\.io\/master/node-role.kubernetes.io\/control-plane/g' | \
        kubectl apply -f -
}

# Fix Deployments
echo ""
echo "Checking Deployments..."
echo "----------------------"
for deployment in $(kubectl get deployments -n $NAMESPACE -o json | jq -r '.items[].metadata.name'); do
    echo "Checking: $deployment"
    
    if kubectl get deployment $deployment -n $NAMESPACE -o yaml | grep -qE "beta\.kubernetes\.io/os|node-role\.kubernetes\.io/master"; then
        echo "  ✗ Found deprecated labels"
        echo "  → Updating..."
        update_resource "deployment" "$deployment" "$NAMESPACE" && echo "  ✓ Success" || echo "  ✗ Failed"
    else
        echo "  ✓ OK"
    fi
done

# Fix DaemonSets
echo ""
echo "Checking DaemonSets..."
echo "---------------------"
for ds in $(kubectl get daemonsets -n $NAMESPACE -o json | jq -r '.items[].metadata.name'); do
    echo "Checking: $ds"
    
    if kubectl get daemonset $ds -n $NAMESPACE -o yaml | grep -qE "beta\.kubernetes\.io/os|node-role\.kubernetes\.io/master"; then
        echo "  ✗ Found deprecated labels"
        echo "  → Updating..."
        update_resource "daemonset" "$ds" "$NAMESPACE" && echo "  ✓ Success" || echo "  ✗ Failed"
    else
        echo "  ✓ OK"
    fi
done

# Fix StatefulSets
echo ""
echo "Checking StatefulSets..."
echo "-----------------------"
for sts in $(kubectl get statefulsets -n $NAMESPACE -o json | jq -r '.items[].metadata.name' 2>/dev/null); do
    echo "Checking: $sts"
    
    if kubectl get statefulset $sts -n $NAMESPACE -o yaml | grep -qE "beta\.kubernetes\.io/os|node-role\.kubernetes\.io/master"; then
        echo "  ✗ Found deprecated labels"
        echo "  → Updating..."
        update_resource "statefulset" "$sts" "$NAMESPACE" && echo "  ✓ Success" || echo "  ✗ Failed"
    else
        echo "  ✓ OK"
    fi
done

echo ""
echo "=============================================================="
echo "Update complete!"