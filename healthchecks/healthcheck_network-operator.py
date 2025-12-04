#!/usr/bin/env python3
"""
NVIDIA Network Operator Health Check for B200 NCCL Workloads

This script performs a comprehensive health check of the NVIDIA Network Operator
configuration to ensure all components are ready for multi-node NCCL tests on
B200 systems with 8 InfiniBand adapters per node.

Prerequisites:
- kubectl configured with cluster admin access
- Passwordless SSH access to DGX nodes
- Python 3.6+

Usage:
    python3 healthcheck_network-operator.py [--nodes NODE1,NODE2,...]
    
Example:
    python3 healthcheck_network-operator.py --nodes dgx030,dgx031
    python3 healthcheck_network-operator.py  # Checks all GPU nodes
"""

import argparse
import subprocess
import sys
import json
import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class Status(Enum):
    """Check status enum."""
    PASS = "✅ PASS"
    WARN = "⚠️  WARN"
    FAIL = "❌ FAIL"
    INFO = "ℹ️  INFO"


@dataclass
class CheckResult:
    """Result of a health check."""
    status: Status
    message: str
    details: Optional[str] = None


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'


def print_section(title: str):
    """Print a section header."""
    print(f"\n{Colors.BOLD}{'=' * 80}{Colors.END}")
    print(f"{Colors.BOLD}{title}{Colors.END}")
    print(f"{Colors.BOLD}{'=' * 80}{Colors.END}")


def print_result(result: CheckResult, indent: int = 0):
    """Print a check result with appropriate formatting."""
    prefix = "  " * indent
    
    # Color mapping
    color_map = {
        Status.PASS: Colors.GREEN,
        Status.WARN: Colors.YELLOW,
        Status.FAIL: Colors.RED,
        Status.INFO: Colors.BLUE,
    }
    
    color = color_map.get(result.status, "")
    print(f"{prefix}{color}{result.status.value}{Colors.END} {result.message}")
    
    if result.details:
        for line in result.details.split('\n'):
            if line.strip():
                print(f"{prefix}    {line}")


def run_command(cmd: List[str], capture_output=True, check=False) -> Tuple[int, str, str]:
    """
    Run a command and return exit code, stdout, stderr.
    
    Args:
        cmd: Command and arguments as list
        capture_output: Whether to capture output
        check: Whether to raise exception on non-zero exit
        
    Returns:
        Tuple of (exit_code, stdout, stderr)
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=capture_output,
            text=True,
            check=check
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.CalledProcessError as e:
        return e.returncode, e.stdout if e.stdout else "", e.stderr if e.stderr else ""
    except Exception as e:
        return 1, "", str(e)


def run_ssh_command(node: str, cmd: str) -> Tuple[int, str, str]:
    """
    Run a command on a remote node via SSH.
    
    Args:
        node: Node hostname
        cmd: Command to run
        
    Returns:
        Tuple of (exit_code, stdout, stderr)
    """
    ssh_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", node, cmd]
    return run_command(ssh_cmd)


def check_network_operator_deployment() -> CheckResult:
    """Check if Network Operator is deployed via Helm."""
    exit_code, stdout, stderr = run_command(
        ["helm", "list", "-n", "network-operator", "-o", "json"]
    )
    
    if exit_code != 0:
        return CheckResult(
            Status.FAIL,
            "Failed to query Helm releases",
            stderr
        )
    
    try:
        releases = json.loads(stdout)
        network_op = [r for r in releases if r.get("name") == "network-operator"]
        
        if not network_op:
            return CheckResult(
                Status.FAIL,
                "Network Operator Helm release not found"
            )
        
        release = network_op[0]
        status = release.get("status", "unknown")
        version = release.get("chart", "unknown")
        
        if status != "deployed":
            return CheckResult(
                Status.WARN,
                f"Network Operator status: {status}",
                f"Chart: {version}"
            )
        
        return CheckResult(
            Status.PASS,
            f"Network Operator deployed",
            f"Chart: {version}, Status: {status}"
        )
    except json.JSONDecodeError:
        return CheckResult(Status.FAIL, "Failed to parse Helm output")


def check_operator_pods() -> CheckResult:
    """Check if Network Operator controller pods are running."""
    exit_code, stdout, stderr = run_command([
        "kubectl", "get", "pods", "-n", "network-operator",
        "-l", "app.kubernetes.io/name=network-operator",
        "-o", "json"
    ])
    
    if exit_code != 0:
        return CheckResult(Status.FAIL, "Failed to query operator pods", stderr)
    
    try:
        pods = json.loads(stdout)
        items = pods.get("items", [])
        
        if not items:
            return CheckResult(Status.FAIL, "No Network Operator pods found")
        
        running = 0
        total = len(items)
        details = []
        
        for pod in items:
            name = pod["metadata"]["name"]
            phase = pod["status"].get("phase", "Unknown")
            
            if phase == "Running":
                running += 1
            else:
                details.append(f"Pod {name}: {phase}")
        
        if running == total:
            return CheckResult(
                Status.PASS,
                f"Network Operator pods running ({running}/{total})"
            )
        else:
            return CheckResult(
                Status.FAIL,
                f"Not all operator pods running ({running}/{total})",
                '\n'.join(details) if details else None
            )
    except (json.JSONDecodeError, KeyError) as e:
        return CheckResult(Status.FAIL, f"Failed to parse pod status: {e}")


def check_nic_cluster_policy() -> CheckResult:
    """Check NicClusterPolicy exists and is ready."""
    exit_code, stdout, stderr = run_command([
        "kubectl", "get", "nicclusterpolicies.mellanox.com",
        "nic-cluster-policy", "-o", "json"
    ])
    
    if exit_code != 0:
        return CheckResult(
            Status.FAIL,
            "NicClusterPolicy 'nic-cluster-policy' not found",
            "Create a NicClusterPolicy to enable Network Operator components"
        )
    
    try:
        policy = json.loads(stdout)
        status = policy.get("status", {})
        state = status.get("state", "unknown")
        applied_states = status.get("appliedStates", [])
        
        details = []
        all_ready = True
        
        for component in applied_states:
            name = component.get("name", "unknown")
            comp_state = component.get("state", "unknown")
            
            if comp_state == "ready":
                details.append(f"  {name}: ready")
            elif comp_state == "ignore":
                details.append(f"  {name}: ignored (not configured)")
            else:
                details.append(f"  {name}: {comp_state}")
                all_ready = False
        
        if state == "ready" and all_ready:
            return CheckResult(
                Status.PASS,
                "NicClusterPolicy is ready",
                '\n'.join(details)
            )
        else:
            return CheckResult(
                Status.WARN,
                f"NicClusterPolicy state: {state}",
                '\n'.join(details)
            )
    except (json.JSONDecodeError, KeyError) as e:
        return CheckResult(Status.FAIL, f"Failed to parse NicClusterPolicy: {e}")


def check_sriov_network_node_states(nodes: List[str]) -> CheckResult:
    """Check SR-IOV network node states for specified nodes."""
    exit_code, stdout, stderr = run_command([
        "kubectl", "get", "sriovnetworknodestate",
        "-n", "network-operator", "-o", "json"
    ])
    
    if exit_code != 0:
        return CheckResult(
            Status.FAIL,
            "Failed to query SriovNetworkNodeState resources",
            stderr
        )
    
    try:
        states = json.loads(stdout)
        items = states.get("items", [])
        
        if not items:
            return CheckResult(
                Status.FAIL,
                "No SriovNetworkNodeState resources found"
            )
        
        details = []
        failed_nodes = []
        
        for item in items:
            node_name = item["metadata"]["name"]
            
            # Skip if not in target nodes list
            if nodes and node_name not in nodes:
                continue
            
            status = item.get("status", {})
            sync_status = status.get("syncStatus", "Unknown")
            
            if sync_status == "Succeeded":
                details.append(f"  {node_name}: {sync_status}")
            else:
                details.append(f"  {node_name}: {sync_status}")
                failed_nodes.append(node_name)
        
        if failed_nodes:
            return CheckResult(
                Status.FAIL,
                f"SR-IOV configuration not succeeded on {len(failed_nodes)} node(s)",
                '\n'.join(details)
            )
        
        if not details:
            return CheckResult(
                Status.WARN,
                "No matching nodes found in SriovNetworkNodeState"
            )
        
        return CheckResult(
            Status.PASS,
            f"SR-IOV configuration succeeded on {len(details)} node(s)",
            '\n'.join(details)
        )
    except (json.JSONDecodeError, KeyError) as e:
        return CheckResult(Status.FAIL, f"Failed to parse SR-IOV states: {e}")


def check_ib_extended_resources(nodes: List[str]) -> CheckResult:
    """Check if InfiniBand extended resources are available on nodes."""
    if not nodes:
        exit_code, stdout, stderr = run_command([
            "kubectl", "get", "nodes", "-l", "nvidia.com/gpu.present=true",
            "-o", "jsonpath={.items[*].metadata.name}"
        ])
        if exit_code == 0:
            nodes = stdout.strip().split()
    
    if not nodes:
        return CheckResult(Status.WARN, "No nodes specified for checking")
    
    expected_resources = [
        "nvidia.com/resibp24s0",
        "nvidia.com/resibp64s0",
        "nvidia.com/resibp79s0",
        "nvidia.com/resibp94s0",
        "nvidia.com/resibp154s0",
        "nvidia.com/resibp192s0",
        "nvidia.com/resibp206s0",
        "nvidia.com/resibp220s0",
    ]
    
    details = []
    failed_nodes = []
    
    for node in nodes:
        exit_code, stdout, stderr = run_command([
            "kubectl", "get", "node", node, "-o", "json"
        ])
        
        if exit_code != 0:
            details.append(f"  {node}: Failed to query")
            failed_nodes.append(node)
            continue
        
        try:
            node_obj = json.loads(stdout)
            allocatable = node_obj.get("status", {}).get("allocatable", {})
            
            found_resources = [r for r in expected_resources if r in allocatable]
            
            if len(found_resources) == 8:
                # Check if all have quantity 8
                quantities = [int(allocatable.get(r, "0")) for r in found_resources]
                if all(q == 8 for q in quantities):
                    details.append(f"  {node}: All 8 IB resources available (8 VFs each)")
                else:
                    details.append(f"  {node}: Resources present but incorrect quantities: {quantities}")
                    failed_nodes.append(node)
            else:
                details.append(f"  {node}: Only {len(found_resources)}/8 IB resources found")
                failed_nodes.append(node)
        except (json.JSONDecodeError, KeyError) as e:
            details.append(f"  {node}: Parse error")
            failed_nodes.append(node)
    
    if failed_nodes:
        return CheckResult(
            Status.FAIL,
            f"IB extended resources missing/incorrect on {len(failed_nodes)} node(s)",
            '\n'.join(details)
        )
    
    return CheckResult(
        Status.PASS,
        f"All IB extended resources available on {len(nodes)} node(s)",
        '\n'.join(details)
    )


def check_nv_ipam() -> CheckResult:
    """Check NV-IPAM deployment and configuration."""
    # Check nv-ipam node pods (DaemonSet)
    exit_code, stdout, stderr = run_command([
        "kubectl", "get", "pods", "-n", "network-operator",
        "-l", "component=nv-ipam-node", "-o", "json"
    ])
    
    if exit_code != 0:
        return CheckResult(Status.FAIL, "Failed to query nv-ipam pods", stderr)
    
    try:
        pods = json.loads(stdout)
        items = pods.get("items", [])
        
        if not items:
            return CheckResult(
                Status.FAIL,
                "NV-IPAM pods not found",
                "Enable nvIpam in NicClusterPolicy with correct image name (nvidia-k8s-ipam)"
            )
        
        running = sum(1 for p in items if p["status"].get("phase") == "Running")
        total = len(items)
        
        if running != total:
            return CheckResult(
                Status.FAIL,
                f"Not all nv-ipam pods running ({running}/{total})"
            )
        
        # Check IPPools
        exit_code, stdout, stderr = run_command([
            "kubectl", "get", "ippools.nv-ipam.nvidia.com",
            "-n", "network-operator", "-o", "json"
        ])
        
        if exit_code != 0:
            return CheckResult(
                Status.WARN,
                f"NV-IPAM pods running ({running}/{total}) but IPPools not found",
                "IPPools may not be created yet"
            )
        
        pools = json.loads(stdout)
        pool_items = pools.get("items", [])
        
        if len(pool_items) != 8:
            return CheckResult(
                Status.WARN,
                f"NV-IPAM running but expected 8 IPPools, found {len(pool_items)}"
            )
        
        # Check block sizes
        details = []
        for pool in pool_items:
            name = pool["metadata"]["name"]
            spec = pool.get("spec", {})
            block_size = spec.get("perNodeBlockSize", 0)
            subnet = spec.get("subnet", "unknown")
            
            if block_size == 8:
                details.append(f"  {name}: {subnet}, blockSize={block_size}")
            else:
                details.append(f"  {name}: {subnet}, blockSize={block_size} (expected 8)")
        
        return CheckResult(
            Status.PASS,
            f"NV-IPAM running with {len(pool_items)} IPPools",
            '\n'.join(details)
        )
    except (json.JSONDecodeError, KeyError) as e:
        return CheckResult(Status.FAIL, f"Failed to parse NV-IPAM status: {e}")


def check_rdma_device_plugin() -> CheckResult:
    """Check RDMA Shared Device Plugin deployment."""
    exit_code, stdout, stderr = run_command([
        "kubectl", "get", "pods", "-n", "network-operator",
        "-l", "app=rdma-shared-dp", "-o", "json"
    ])
    
    if exit_code != 0:
        return CheckResult(Status.FAIL, "Failed to query RDMA device plugin pods", stderr)
    
    try:
        pods = json.loads(stdout)
        items = pods.get("items", [])
        
        if not items:
            return CheckResult(
                Status.FAIL,
                "RDMA Shared Device Plugin not found",
                "Enable rdmaSharedDevicePlugin in NicClusterPolicy"
            )
        
        running = sum(1 for p in items if p["status"].get("phase") == "Running")
        total = len(items)
        
        if running != total:
            return CheckResult(
                Status.FAIL,
                f"Not all RDMA device plugin pods running ({running}/{total})"
            )
        
        # Check for rdma resources on nodes
        exit_code, stdout, stderr = run_command([
            "kubectl", "get", "nodes", "-o", "json"
        ])
        
        if exit_code == 0:
            nodes_obj = json.loads(stdout)
            nodes_with_rdma = 0
            
            for node in nodes_obj.get("items", []):
                allocatable = node.get("status", {}).get("allocatable", {})
                if "rdma/rdma_shared_device_a" in allocatable:
                    nodes_with_rdma += 1
            
            return CheckResult(
                Status.PASS,
                f"RDMA Device Plugin running on {total} node(s)",
                f"  rdma_shared_device_a resources available on {nodes_with_rdma} nodes"
            )
        
        return CheckResult(
            Status.PASS,
            f"RDMA Device Plugin running on {total} node(s)"
        )
    except (json.JSONDecodeError, KeyError) as e:
        return CheckResult(Status.FAIL, f"Failed to parse RDMA plugin status: {e}")


def check_secondary_network_components() -> CheckResult:
    """Check Multus, CNI plugins, and whereabouts."""
    components = [
        ("Multus CNI", "kube-multus-ds"),
        ("CNI Plugins", "cni-plugins-ds"),
        ("Whereabouts IPAM", "whereabouts"),
    ]
    
    details = []
    all_running = True
    
    for name, label_value in components:
        exit_code, stdout, stderr = run_command([
            "kubectl", "get", "pods", "-n", "network-operator",
            "-o", "json"
        ])
        
        if exit_code != 0:
            details.append(f"  {name}: Failed to query")
            all_running = False
            continue
        
        try:
            pods = json.loads(stdout)
            items = pods.get("items", [])
            
            # Filter pods by name pattern
            component_pods = [p for p in items if label_value in p["metadata"]["name"]]
            
            if not component_pods:
                details.append(f"  {name}: Not found")
                all_running = False
                continue
            
            running = sum(1 for p in component_pods if p["status"].get("phase") == "Running")
            total = len(component_pods)
            
            if running == total:
                details.append(f"  {name}: Running ({total} pod(s))")
            else:
                details.append(f"  {name}: {running}/{total} running")
                all_running = False
        except (json.JSONDecodeError, KeyError):
            details.append(f"  {name}: Parse error")
            all_running = False
    
    if all_running:
        return CheckResult(
            Status.PASS,
            "All secondary network components running",
            '\n'.join(details)
        )
    else:
        return CheckResult(
            Status.FAIL,
            "Some secondary network components not running",
            '\n'.join(details)
        )


def check_network_attachment_definitions() -> CheckResult:
    """Check that all required NADs exist."""
    expected_nads = [
        "ibp24s0-sriovnet",
        "ibp64s0-sriovnet",
        "ibp79s0-sriovnet",
        "ibp94s0-sriovnet",
        "ibp154s0-sriovnet",
        "ibp192s0-sriovnet",
        "ibp206s0-sriovnet",
        "ibp220s0-sriovnet",
    ]
    
    exit_code, stdout, stderr = run_command([
        "kubectl", "get", "network-attachment-definitions",
        "-n", "network-operator", "-o", "json"
    ])
    
    if exit_code != 0:
        return CheckResult(
            Status.FAIL,
            "Failed to query Network Attachment Definitions",
            stderr
        )
    
    try:
        nads = json.loads(stdout)
        items = nads.get("items", [])
        
        found_names = [item["metadata"]["name"] for item in items]
        missing = [nad for nad in expected_nads if nad not in found_names]
        
        if not missing:
            return CheckResult(
                Status.PASS,
                f"All 8 Network Attachment Definitions found",
                f"  Namespace: network-operator"
            )
        else:
            return CheckResult(
                Status.FAIL,
                f"Missing {len(missing)} NAD(s)",
                f"  Missing: {', '.join(missing)}"
            )
    except (json.JSONDecodeError, KeyError) as e:
        return CheckResult(Status.FAIL, f"Failed to parse NADs: {e}")


def check_node_vf_activation(node: str) -> CheckResult:
    """Check if VFs are activated on a node."""
    interfaces = [
        "ibp24s0", "ibp64s0", "ibp79s0", "ibp94s0",
        "ibp154s0", "ibp192s0", "ibp206s0", "ibp220s0"
    ]
    
    details = []
    failed_ifaces = []
    
    for iface in interfaces:
        cmd = f"cat /sys/class/net/{iface}/device/sriov_numvfs 2>/dev/null"
        exit_code, stdout, stderr = run_ssh_command(node, cmd)
        
        if exit_code != 0:
            details.append(f"  {iface}: Not found or inaccessible")
            failed_ifaces.append(iface)
        else:
            num_vfs = stdout.strip()
            if num_vfs == "8":
                details.append(f"  {iface}: {num_vfs} VFs active")
            else:
                details.append(f"  {iface}: {num_vfs} VFs (expected 8)")
                failed_ifaces.append(iface)
    
    if failed_ifaces:
        return CheckResult(
            Status.FAIL,
            f"{node}: VF activation issues on {len(failed_ifaces)} interface(s)",
            '\n'.join(details)
        )
    
    return CheckResult(
        Status.PASS,
        f"{node}: All 8 IB interfaces have 8 VFs active",
        '\n'.join(details)
    )


def check_node_ib_ports(node: str) -> CheckResult:
    """Check InfiniBand port status on a node."""
    cmd = "ibstat 2>/dev/null | grep -E '(CA |Port |State:|base lid:)'"
    exit_code, stdout, stderr = run_ssh_command(node, cmd)
    
    if exit_code != 0:
        return CheckResult(
            Status.FAIL,
            f"{node}: Failed to run ibstat",
            "Ensure InfiniBand drivers are loaded"
        )
    
    # Parse ibstat output
    lines = stdout.strip().split('\n')
    current_ca = None
    current_port = None
    port_states = []
    
    for line in lines:
        line = line.strip()
        
        if line.startswith("CA '"):
            current_ca = line.split("'")[1]
        elif line.startswith("Port "):
            current_port = line.split()[1].rstrip(':')
        elif "State:" in line:
            state = line.split("State:")[-1].strip()
            if current_ca and current_port:
                port_states.append((current_ca, current_port, state))
        elif "base lid:" in line:
            lid = line.split("base lid:")[-1].strip()
            # Check for invalid LID (0xffff or 65535)
            if lid in ["0xffff", "65535"]:
                port_states[-1] = port_states[-1] + (lid,)
    
    details = []
    down_ports = []
    
    for state_info in port_states:
        if len(state_info) == 3:
            ca, port, state = state_info
            if state == "Active":
                details.append(f"  {ca} port {port}: {state}")
            else:
                details.append(f"  {ca} port {port}: {state} (expected Active)")
                down_ports.append(f"{ca}:{port}")
        elif len(state_info) == 4:
            ca, port, state, lid = state_info
            if state == "Active" and lid not in ["0xffff", "65535"]:
                details.append(f"  {ca} port {port}: {state}, LID {lid}")
            else:
                details.append(f"  {ca} port {port}: {state}, LID {lid} (invalid)")
                down_ports.append(f"{ca}:{port}")
    
    if down_ports:
        return CheckResult(
            Status.WARN,
            f"{node}: {len(down_ports)} IB port(s) not active or invalid LID",
            '\n'.join(details)
        )
    
    return CheckResult(
        Status.PASS,
        f"{node}: All IB ports Active",
        '\n'.join(details)
    )


def main():
    """Main health check execution."""
    parser = argparse.ArgumentParser(
        description="NVIDIA Network Operator Health Check for B200 NCCL Workloads",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check specific nodes
  python3 healthcheck_network-operator.py --nodes dgx030,dgx031
  
  # Check all GPU nodes
  python3 healthcheck_network-operator.py
        """
    )
    
    parser.add_argument(
        "--nodes",
        type=str,
        help="Comma-separated list of node names to check (e.g., dgx030,dgx031). If not specified, checks all GPU nodes."
    )
    
    parser.add_argument(
        "--skip-ssh",
        action="store_true",
        help="Skip SSH-based node checks (VF activation, IB port status)"
    )
    
    args = parser.parse_args()
    
    # Parse node list
    nodes = []
    if args.nodes:
        nodes = [n.strip() for n in args.nodes.split(',')]
    
    print(f"\n{Colors.BOLD}{'=' * 80}{Colors.END}")
    print(f"{Colors.BOLD}NVIDIA Network Operator Health Check for B200 NCCL Workloads{Colors.END}")
    print(f"{Colors.BOLD}{'=' * 80}{Colors.END}")
    
    if nodes:
        print(f"\n{Colors.BLUE}Target Nodes: {', '.join(nodes)}{Colors.END}")
    else:
        print(f"\n{Colors.BLUE}Target Nodes: All GPU nodes (nvidia.com/gpu.present=true){Colors.END}")
    
    # Track overall status
    failed_checks = []
    warning_checks = []
    
    # 1. Network Operator Deployment
    print_section("1. Network Operator Deployment")
    
    result = check_network_operator_deployment()
    print_result(result)
    if result.status == Status.FAIL:
        failed_checks.append("Network Operator Deployment")
    
    result = check_operator_pods()
    print_result(result)
    if result.status == Status.FAIL:
        failed_checks.append("Network Operator Pods")
    
    result = check_nic_cluster_policy()
    print_result(result)
    if result.status == Status.FAIL:
        failed_checks.append("NicClusterPolicy")
    elif result.status == Status.WARN:
        warning_checks.append("NicClusterPolicy")
    
    # 2. SR-IOV Configuration
    print_section("2. SR-IOV Configuration")
    
    result = check_sriov_network_node_states(nodes)
    print_result(result)
    if result.status == Status.FAIL:
        failed_checks.append("SR-IOV Node States")
    
    result = check_ib_extended_resources(nodes)
    print_result(result)
    if result.status == Status.FAIL:
        failed_checks.append("IB Extended Resources")
    
    # 3. NV-IPAM
    print_section("3. NV-IPAM Configuration")
    
    result = check_nv_ipam()
    print_result(result)
    if result.status == Status.FAIL:
        failed_checks.append("NV-IPAM")
    elif result.status == Status.WARN:
        warning_checks.append("NV-IPAM")
    
    # 4. RDMA Device Plugin
    print_section("4. RDMA Shared Device Plugin")
    
    result = check_rdma_device_plugin()
    print_result(result)
    if result.status == Status.FAIL:
        failed_checks.append("RDMA Device Plugin")
    
    # 5. Secondary Network Components
    print_section("5. Secondary Network Components (Multus, CNI, IPAM)")
    
    result = check_secondary_network_components()
    print_result(result)
    if result.status == Status.FAIL:
        failed_checks.append("Secondary Network Components")
    
    # 6. Network Attachment Definitions
    print_section("6. Network Attachment Definitions")
    
    result = check_network_attachment_definitions()
    print_result(result)
    if result.status == Status.FAIL:
        failed_checks.append("Network Attachment Definitions")
    
    # 7. Node-level checks (via SSH)
    if not args.skip_ssh:
        print_section("7. Node-Level InfiniBand Configuration")
        
        # Resolve node list if not specified
        if not nodes:
            exit_code, stdout, stderr = run_command([
                "kubectl", "get", "nodes", "-l", "nvidia.com/gpu.present=true",
                "-o", "jsonpath={.items[*].metadata.name}"
            ])
            if exit_code == 0:
                nodes = stdout.strip().split()
        
        if not nodes:
            print_result(CheckResult(
                Status.WARN,
                "No GPU nodes found for SSH checks"
            ))
        else:
            for node in nodes:
                print(f"\n{Colors.BOLD}Node: {node}{Colors.END}")
                
                result = check_node_vf_activation(node)
                print_result(result, indent=1)
                if result.status == Status.FAIL:
                    failed_checks.append(f"VF Activation ({node})")
                
                result = check_node_ib_ports(node)
                print_result(result, indent=1)
                if result.status == Status.FAIL:
                    failed_checks.append(f"IB Ports ({node})")
                elif result.status == Status.WARN:
                    warning_checks.append(f"IB Ports ({node})")
    else:
        print_section("7. Node-Level Checks")
        print_result(CheckResult(
            Status.INFO,
            "Skipped (--skip-ssh flag)"
        ))
    
    # Final Summary
    print_section("Health Check Summary")
    
    if not failed_checks and not warning_checks:
        print(f"\n{Colors.GREEN}{Colors.BOLD}✅ ALL CHECKS PASSED{Colors.END}")
        print(f"\n{Colors.GREEN}The Network Operator is properly configured for NCCL workloads.{Colors.END}")
        print(f"{Colors.GREEN}You can proceed with running b200_runai_nccl_test.py{Colors.END}")
        return 0
    elif not failed_checks:
        print(f"\n{Colors.YELLOW}{Colors.BOLD}⚠️  CHECKS PASSED WITH WARNINGS{Colors.END}")
        print(f"\n{Colors.YELLOW}Warnings in:{Colors.END}")
        for check in warning_checks:
            print(f"  - {check}")
        print(f"\n{Colors.YELLOW}The Network Operator should work, but review warnings above.{Colors.END}")
        return 0
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}❌ HEALTH CHECK FAILED{Colors.END}")
        print(f"\n{Colors.RED}Failed checks:{Colors.END}")
        for check in failed_checks:
            print(f"  - {check}")
        
        if warning_checks:
            print(f"\n{Colors.YELLOW}Warnings in:{Colors.END}")
            for check in warning_checks:
                print(f"  - {check}")
        
        print(f"\n{Colors.RED}Please resolve the failed checks before running NCCL tests.{Colors.END}")
        print(f"{Colors.RED}Refer to NetworkOperator-24.7.0-to-25.7.0-Upgrade.md for troubleshooting guidance.{Colors.END}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

