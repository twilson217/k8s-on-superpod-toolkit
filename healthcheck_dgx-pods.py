#!/usr/bin/env python3
"""
DGX Node Pod Placement Health Check Script

This script validates that DGX worker nodes (GPU nodes) are only running:
1. DaemonSet pods (allowed on all nodes)
2. User workload pods from runai-<project> namespaces

Any other pods (system infrastructure, monitoring, runai core components)
should be running on runai-system/control-plane nodes, not on DGX workers.

Node Classification:
- RunAI System Nodes: Have 'runai-system' role or control-plane/master role
- DGX Worker Nodes: All other nodes (intended for user workloads only)

Expected Pod Distribution:
- runai namespace: Should run on runai-system nodes only
- runai-backend namespace: Should run on runai-system nodes only
- runai-<project> namespaces: Should run on DGX worker nodes (user workloads)
- Other namespaces: Should run on runai-system nodes only
- DaemonSets: Allowed on all nodes (not checked)

Usage:
    python3 healthcheck_dgx-pods.py
"""

import subprocess
import json
import sys
from datetime import datetime
from collections import defaultdict


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'


def run_command(cmd, capture_output=True, text=True, timeout=30):
    """Execute a shell command and return the result."""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=capture_output,
            text=text,
            timeout=timeout
        )
        return result
    except subprocess.TimeoutExpired:
        print(f"{Colors.RED}✗ Command timed out: {cmd}{Colors.END}")
        return None
    except Exception as e:
        print(f"{Colors.RED}✗ Error executing command: {e}{Colors.END}")
        return None


def print_header(title):
    """Print a formatted header."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 80}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{title}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 80}{Colors.END}\n")


def get_node_classification():
    """
    Classify nodes into runai-system nodes and DGX worker nodes.
    
    Returns:
        tuple: (runai_system_nodes, dgx_worker_nodes) as lists of node names
    """
    cmd = "kubectl get nodes -o json"
    result = run_command(cmd)
    
    if not result or result.returncode != 0:
        print(f"{Colors.RED}✗ Failed to get nodes{Colors.END}")
        return [], []
    
    try:
        data = json.loads(result.stdout)
        nodes = data.get('items', [])
        
        runai_system_nodes = []
        dgx_worker_nodes = []
        
        for node in nodes:
            name = node['metadata']['name']
            labels = node['metadata'].get('labels', {})
            
            # Check if node has runai-system, control-plane, or master role
            is_system_node = (
                'node-role.kubernetes.io/runai-system' in labels or
                'node-role.kubernetes.io/control-plane' in labels or
                'node-role.kubernetes.io/master' in labels
            )
            
            if is_system_node:
                runai_system_nodes.append(name)
            else:
                dgx_worker_nodes.append(name)
        
        return runai_system_nodes, dgx_worker_nodes
        
    except (json.JSONDecodeError, KeyError) as e:
        print(f"{Colors.RED}✗ Failed to parse node information: {e}{Colors.END}")
        return [], []


def get_pods_on_dgx_nodes(dgx_nodes):
    """
    Get all pods running on DGX worker nodes.
    
    Args:
        dgx_nodes: List of DGX worker node names
        
    Returns:
        list: List of pod objects with relevant information
    """
    if not dgx_nodes:
        return []
    
    cmd = "kubectl get pods -A -o json"
    result = run_command(cmd)
    
    if not result or result.returncode != 0:
        print(f"{Colors.RED}✗ Failed to get pods{Colors.END}")
        return []
    
    try:
        data = json.loads(result.stdout)
        all_pods = data.get('items', [])
        
        dgx_pods = []
        for pod in all_pods:
            node_name = pod['spec'].get('nodeName', '')
            if node_name in dgx_nodes:
                dgx_pods.append(pod)
        
        return dgx_pods
        
    except (json.JSONDecodeError, KeyError) as e:
        print(f"{Colors.RED}✗ Failed to parse pod information: {e}{Colors.END}")
        return []


def get_pod_owner_kind(pod):
    """
    Determine the owner kind of a pod (Deployment, StatefulSet, DaemonSet, etc.).
    
    Args:
        pod: Pod object from kubectl
        
    Returns:
        str: Owner kind (e.g., "DaemonSet", "Deployment", "StatefulSet", "Pod")
    """
    owner_references = pod['metadata'].get('ownerReferences', [])
    
    if not owner_references:
        return "Pod"
    
    # Get the first owner (typically the direct controller)
    owner = owner_references[0]
    owner_kind = owner.get('kind', 'Unknown')
    
    # Map ReplicaSet to Deployment (common pattern)
    if owner_kind == 'ReplicaSet':
        # Try to find if this ReplicaSet is owned by a Deployment
        # For simplicity, we'll just report as Deployment
        return "Deployment"
    
    return owner_kind


def analyze_pod_placement(dgx_pods):
    """
    Analyze pods on DGX nodes and identify violations.
    
    Args:
        dgx_pods: List of pod objects running on DGX nodes
        
    Returns:
        tuple: (total_dgx_pods, daemonset_count, user_workload_count, violations)
    """
    total_dgx_pods = len(dgx_pods)
    daemonset_count = 0
    user_workload_count = 0
    violations = []
    
    for pod in dgx_pods:
        namespace = pod['metadata']['namespace']
        pod_name = pod['metadata']['name']
        owner_kind = get_pod_owner_kind(pod)
        
        # Skip DaemonSets (allowed on all nodes)
        if owner_kind == 'DaemonSet':
            daemonset_count += 1
            continue
        
        # Check if this is a user workload namespace (runai-<project>)
        # Exclude runai and runai-backend (core system namespaces)
        if namespace.startswith('runai-') and namespace not in ['runai-backend']:
            user_workload_count += 1
            continue
        
        # This is a violation - system/infrastructure pod on DGX node
        violations.append({
            'namespace': namespace,
            'pod_name': pod_name,
            'owner_kind': owner_kind,
            'node': pod['spec'].get('nodeName', 'unknown')
        })
    
    return total_dgx_pods, daemonset_count, user_workload_count, violations


def print_violations_table(violations):
    """
    Print violations in a formatted table.
    
    Args:
        violations: List of violation dictionaries
    """
    if not violations:
        return
    
    # Group violations by namespace and owner kind
    grouped = defaultdict(lambda: defaultdict(list))
    for v in violations:
        grouped[v['namespace']][v['owner_kind']].append(v)
    
    # Print table header
    print(f"\n{Colors.RED}{Colors.BOLD}Misplaced Pods on DGX Worker Nodes:{Colors.END}\n")
    print(f"{Colors.BOLD}{'Namespace':<25} {'Type':<20} {'Pod Name':<40} {'Node':<15}{Colors.END}")
    print("-" * 100)
    
    # Print violations grouped by namespace and type
    for namespace in sorted(grouped.keys()):
        for owner_kind in sorted(grouped[namespace].keys()):
            pods = grouped[namespace][owner_kind]
            for idx, pod in enumerate(sorted(pods, key=lambda x: x['pod_name'])):
                # Print namespace and type only for first pod in group
                if idx == 0:
                    print(f"{namespace:<25} {owner_kind:<20} {pod['pod_name']:<40} {pod['node']:<15}")
                else:
                    print(f"{'':>25} {'':>20} {pod['pod_name']:<40} {pod['node']:<15}")


def main():
    """Main execution function."""
    print_header("DGX Node Pod Placement Health Check")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Purpose: Validate that DGX worker nodes only run user workloads and DaemonSets")
    
    # Step 1: Classify nodes
    print(f"\n{Colors.BOLD}Step 1: Classifying Nodes{Colors.END}")
    runai_system_nodes, dgx_worker_nodes = get_node_classification()
    
    if not dgx_worker_nodes:
        print(f"{Colors.YELLOW}⚠ No DGX worker nodes found in cluster{Colors.END}")
        print(f"{Colors.YELLOW}All nodes appear to be runai-system/control-plane nodes{Colors.END}")
        return 0
    
    print(f"  • RunAI System Nodes: {len(runai_system_nodes)} ({', '.join(runai_system_nodes)})")
    print(f"  • DGX Worker Nodes: {len(dgx_worker_nodes)} ({', '.join(dgx_worker_nodes)})")
    
    # Step 2: Get pods on DGX nodes
    print(f"\n{Colors.BOLD}Step 2: Scanning Pods on DGX Nodes{Colors.END}")
    dgx_pods = get_pods_on_dgx_nodes(dgx_worker_nodes)
    
    if not dgx_pods:
        print(f"{Colors.GREEN}✓ No pods found on DGX nodes{Colors.END}")
        return 0
    
    print(f"  • Total pods on DGX nodes: {len(dgx_pods)}")
    
    # Step 3: Analyze pod placement
    print(f"\n{Colors.BOLD}Step 3: Analyzing Pod Placement{Colors.END}")
    total_dgx_pods, daemonset_count, user_workload_count, violations = analyze_pod_placement(dgx_pods)
    
    print(f"  • DaemonSet pods (allowed): {daemonset_count}")
    print(f"  • User workload pods from runai-<project> (allowed): {user_workload_count}")
    print(f"  • System/infrastructure pods (violations): {len(violations)}")
    
    # Step 4: Report results
    print_header("Health Check Results")
    
    if not violations:
        print(f"{Colors.GREEN}{Colors.BOLD}✓ PASS: All DGX nodes are correctly configured{Colors.END}")
        print(f"{Colors.GREEN}DGX worker nodes are only running:{Colors.END}")
        print(f"{Colors.GREEN}  • DaemonSet pods ({daemonset_count} pods){Colors.END}")
        print(f"{Colors.GREEN}  • User workload pods from runai-<project> namespaces ({user_workload_count} pods){Colors.END}")
        print(f"\n{Colors.GREEN}No system or infrastructure pods found on DGX nodes.{Colors.END}\n")
        return 0
    else:
        print(f"{Colors.RED}{Colors.BOLD}✗ FAIL: Found {len(violations)} misplaced pod(s) on DGX worker nodes{Colors.END}")
        print(f"\n{Colors.RED}System and infrastructure pods should run on runai-system nodes, not DGX workers.{Colors.END}")
        
        # Print detailed violations table
        print_violations_table(violations)
        
        # Print summary by namespace
        print(f"\n{Colors.BOLD}Summary by Namespace:{Colors.END}")
        namespace_counts = defaultdict(int)
        for v in violations:
            namespace_counts[v['namespace']] += 1
        
        for namespace in sorted(namespace_counts.keys()):
            count = namespace_counts[namespace]
            print(f"  • {namespace}: {count} pod(s)")
        
        print(f"\n{Colors.YELLOW}Recommendation: Review pod affinity/nodeSelector configurations for these workloads.{Colors.END}")
        print(f"{Colors.YELLOW}These pods should have affinity rules or nodeSelectors to run on runai-system nodes.{Colors.END}\n")
        
        return 1


if __name__ == "__main__":
    sys.exit(main())

