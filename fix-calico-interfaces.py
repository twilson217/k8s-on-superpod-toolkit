#!/usr/bin/env python3
"""
Fix Calico Interface Routing Conflicts

This script identifies and cleans up orphaned Calico network interfaces
that cause routing conflicts when pods fail to start with errors like:
"route already exists for an interface other than 'caliXXX'"

Usage:
    python3 fix-calico-interfaces.py [options]

Options:
    --node NODE           Check specific node only
    --dry-run            Show what would be deleted without deleting
    --auto-fix           Automatically fix issues without prompting
    -v, --verbose        Verbose output
"""

import subprocess
import json
import sys
import argparse
import re
from typing import Dict, List, Set, Tuple
from collections import defaultdict


class Colors:
    """ANSI color codes for terminal output"""
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def run_command(cmd: str, check=True, capture=True, node=None) -> Tuple[int, str, str]:
    """
    Execute a shell command
    
    Args:
        cmd: Command to run
        check: Whether to raise exception on non-zero exit
        capture: Whether to capture output
        node: If provided, run command via SSH on this node
        
    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    if node:
        cmd = f"ssh {node} '{cmd}'"
    
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=capture,
            text=True,
            check=check
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.CalledProcessError as e:
        if check:
            raise
        return e.returncode, e.stdout if e.stdout else "", e.stderr if e.stderr else ""


def get_all_nodes() -> List[str]:
    """Get list of all Kubernetes nodes"""
    _, stdout, _ = run_command("kubectl get nodes -o json")
    nodes_data = json.loads(stdout)
    return [node['metadata']['name'] for node in nodes_data['items']]


def get_running_pods_by_node() -> Dict[str, List[Dict]]:
    """
    Get all running pods grouped by node
    
    Returns:
        Dict mapping node_name -> list of pod info dicts
    """
    cmd = "kubectl get pods -A -o json --field-selector status.phase=Running"
    _, stdout, _ = run_command(cmd)
    pods_data = json.loads(stdout)
    
    pods_by_node = defaultdict(list)
    
    for pod in pods_data['items']:
        node_name = pod['spec'].get('nodeName')
        pod_ip = pod['status'].get('podIP')
        
        if node_name and pod_ip:
            pods_by_node[node_name].append({
                'name': pod['metadata']['name'],
                'namespace': pod['metadata']['namespace'],
                'ip': pod_ip,
                'node': node_name
            })
    
    return pods_by_node


def get_calico_interfaces(node: str) -> List[Dict]:
    """
    Get all Calico interfaces and their associated IPs on a node
    
    Args:
        node: Node name to check
        
    Returns:
        List of dicts with interface info
    """
    # Get all routes that include calico interfaces
    cmd = "ip route show | grep -E '^172\\.' | grep cali"
    returncode, stdout, _ = run_command(cmd, check=False, node=node)
    
    if returncode != 0 or not stdout.strip():
        return []
    
    interfaces = []
    
    for line in stdout.strip().split('\n'):
        # Parse route lines like: "172.16.106.21 dev califabcd1234 scope link"
        match = re.match(r'^(\d+\.\d+\.\d+\.\d+)(?:/\d+)?\s+dev\s+(cali\w+)', line)
        if match:
            ip, iface = match.groups()
            interfaces.append({
                'interface': iface,
                'ip': ip,
                'route_line': line.strip()
            })
    
    return interfaces


def check_interface_exists(node: str, interface: str) -> bool:
    """Check if a network interface still exists on the node"""
    cmd = f"ip link show {interface}"
    returncode, _, _ = run_command(cmd, check=False, node=node)
    return returncode == 0


def delete_interface(node: str, interface: str, dry_run: bool = False) -> bool:
    """
    Delete a network interface
    
    Args:
        node: Node to delete interface from
        interface: Interface name
        dry_run: If True, don't actually delete
        
    Returns:
        True if successful (or dry_run), False otherwise
    """
    if dry_run:
        print(f"  {Colors.YELLOW}[DRY-RUN]{Colors.RESET} Would delete: {interface}")
        return True
    
    cmd = f"ip link delete {interface}"
    returncode, stdout, stderr = run_command(cmd, check=False, node=node)
    
    if returncode == 0:
        print(f"  {Colors.GREEN}✓{Colors.RESET} Deleted: {interface}")
        return True
    else:
        print(f"  {Colors.RED}✗{Colors.RESET} Failed to delete {interface}: {stderr}")
        return False


def find_orphaned_interfaces(node: str, running_pod_ips: Set[str], verbose: bool = False) -> List[Dict]:
    """
    Find Calico interfaces that don't correspond to running pods
    
    Args:
        node: Node to check
        running_pod_ips: Set of IPs for pods that should be running on this node
        verbose: Print verbose output
        
    Returns:
        List of orphaned interface dicts
    """
    interfaces = get_calico_interfaces(node)
    
    if verbose:
        print(f"\n{Colors.CYAN}Checking node: {node}{Colors.RESET}")
        print(f"  Running pod IPs: {len(running_pod_ips)}")
        print(f"  Calico interfaces found: {len(interfaces)}")
    
    orphaned = []
    
    for iface_info in interfaces:
        ip = iface_info['ip']
        iface = iface_info['interface']
        
        if ip not in running_pod_ips:
            # Verify the interface still exists
            if check_interface_exists(node, iface):
                orphaned.append(iface_info)
                if verbose:
                    print(f"  {Colors.RED}✗{Colors.RESET} Orphaned: {iface} -> {ip}")
            elif verbose:
                print(f"  {Colors.YELLOW}○{Colors.RESET} Already gone: {iface} -> {ip}")
        elif verbose:
            print(f"  {Colors.GREEN}✓{Colors.RESET} Active: {iface} -> {ip}")
    
    return orphaned


def main():
    parser = argparse.ArgumentParser(
        description='Fix Calico interface routing conflicts',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument('--node', help='Check specific node only')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Show what would be deleted without deleting')
    parser.add_argument('--auto-fix', action='store_true',
                       help='Automatically fix issues without prompting')
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Verbose output')
    
    args = parser.parse_args()
    
    print(f"{Colors.BOLD}=== Calico Interface Cleanup Tool ==={Colors.RESET}\n")
    
    # Get nodes to check
    if args.node:
        nodes_to_check = [args.node]
    else:
        print("Getting list of all nodes...")
        nodes_to_check = get_all_nodes()
    
    print(f"Nodes to check: {', '.join(nodes_to_check)}\n")
    
    # Get all running pods
    print("Getting running pods...")
    pods_by_node = get_running_pods_by_node()
    
    # Track what we find
    total_orphaned = 0
    total_deleted = 0
    issues_by_node = {}
    
    # Check each node
    for node in nodes_to_check:
        running_pods = pods_by_node.get(node, [])
        running_pod_ips = {pod['ip'] for pod in running_pods}
        
        if args.verbose:
            print(f"\n{Colors.BOLD}Node: {node}{Colors.RESET}")
            print(f"  Running pods: {len(running_pods)}")
        
        orphaned = find_orphaned_interfaces(node, running_pod_ips, args.verbose)
        
        if orphaned:
            total_orphaned += len(orphaned)
            issues_by_node[node] = orphaned
            
            print(f"\n{Colors.RED}Found {len(orphaned)} orphaned interface(s) on {node}:{Colors.RESET}")
            for iface_info in orphaned:
                print(f"  - {iface_info['interface']} -> {iface_info['ip']}")
    
    # Summary
    print(f"\n{Colors.BOLD}=== Summary ==={Colors.RESET}")
    print(f"Total nodes checked: {len(nodes_to_check)}")
    print(f"Total orphaned interfaces: {total_orphaned}")
    
    if total_orphaned == 0:
        print(f"{Colors.GREEN}✓ No orphaned interfaces found!{Colors.RESET}")
        return 0
    
    # Cleanup
    if args.dry_run:
        print(f"\n{Colors.YELLOW}[DRY-RUN MODE] - No changes will be made{Colors.RESET}")
    
    if not args.auto_fix and not args.dry_run:
        response = input(f"\n{Colors.YELLOW}Delete orphaned interfaces? [y/N]: {Colors.RESET}")
        if response.lower() != 'y':
            print("Aborted.")
            return 1
    
    # Delete orphaned interfaces
    print(f"\n{Colors.BOLD}Cleaning up orphaned interfaces...{Colors.RESET}")
    
    for node, orphaned_list in issues_by_node.items():
        print(f"\n{Colors.CYAN}Node: {node}{Colors.RESET}")
        for iface_info in orphaned_list:
            if delete_interface(node, iface_info['interface'], args.dry_run):
                total_deleted += 1
    
    print(f"\n{Colors.BOLD}=== Results ==={Colors.RESET}")
    if args.dry_run:
        print(f"Would delete: {total_deleted} interfaces")
    else:
        print(f"Successfully deleted: {total_deleted} interfaces")
        if total_deleted < total_orphaned:
            print(f"{Colors.RED}Failed to delete: {total_orphaned - total_deleted} interfaces{Colors.RESET}")
    
    return 0 if total_deleted == total_orphaned else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Interrupted by user{Colors.RESET}")
        sys.exit(130)
    except Exception as e:
        print(f"\n{Colors.RED}Error: {e}{Colors.RESET}", file=sys.stderr)
        if '--verbose' in sys.argv or '-v' in sys.argv:
            import traceback
            traceback.print_exc()
        sys.exit(1)

