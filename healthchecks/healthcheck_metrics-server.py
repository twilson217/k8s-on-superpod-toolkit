#!/usr/bin/env python3
"""
Metrics-Server Health Check Script

This script validates the health and functionality of metrics-server,
which provides real-time resource metrics (CPU/memory) for containers and nodes.

Tests:
1. Metrics-Server Pod Status
2. Service Availability
3. API Service Registration
4. Metrics API Availability
5. Node Metrics Collection
6. Pod Metrics Collection
7. Configuration Validation

Usage:
    python3 healthcheck_metrics-server.py
"""

import subprocess
import json
import sys
import re
from datetime import datetime


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
    """Print a formatted test header."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 80}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{title}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 80}{Colors.END}\n")


def print_test_result(test_num, test_name, passed, message=""):
    """Print a formatted test result."""
    if passed is None:
        # Just print the test header while checking
        print(f"{Colors.BOLD}Test {test_num}: {test_name}{Colors.END}")
        if message:
            print(f"{message}")
    else:
        # Print the final result
        status = f"{Colors.GREEN}✓ PASS{Colors.END}" if passed else f"{Colors.RED}✗ FAIL{Colors.END}"
        print(f"{Colors.BOLD}Test {test_num}: {test_name}{Colors.END}")
        print(f"Status: {status}")
        if message:
            print(f"Details: {message}")
    print()


def test_pod_status():
    """Test 1: Check metrics-server pods are running."""
    print_test_result(1, "Metrics-Server Pod Status", None, "Checking...")
    
    # Try app.kubernetes.io/name label first (modern Helm charts)
    cmd = "kubectl get pods -n kube-system -l app.kubernetes.io/name=metrics-server -o json"
    result = run_command(cmd)
    
    # Fallback to older k8s-app label if no pods found
    if result and result.returncode == 0:
        try:
            data = json.loads(result.stdout)
            if not data.get('items', []):
                cmd = "kubectl get pods -n kube-system -l k8s-app=metrics-server -o json"
                result = run_command(cmd)
        except:
            pass
    
    if not result or result.returncode != 0:
        print_test_result(1, "Metrics-Server Pod Status", False, 
                         "Failed to get metrics-server pods")
        return False, None
    
    try:
        data = json.loads(result.stdout)
        pods = data.get('items', [])
        
        if not pods:
            print_test_result(1, "Metrics-Server Pod Status", False,
                             "No metrics-server pods found")
            return False, None
        
        running_pods = 0
        ready_pods = 0
        pod_details = []
        pod_names = []
        
        for pod in pods:
            name = pod['metadata']['name']
            pod_names.append(name)
            phase = pod['status'].get('phase', 'Unknown')
            
            # Check if pod is ready
            conditions = pod['status'].get('conditions', [])
            is_ready = False
            for condition in conditions:
                if condition['type'] == 'Ready' and condition['status'] == 'True':
                    is_ready = True
                    break
            
            # Get restart count
            container_statuses = pod['status'].get('containerStatuses', [])
            restart_count = sum(cs.get('restartCount', 0) for cs in container_statuses)
            
            if phase == 'Running':
                running_pods += 1
            if is_ready:
                ready_pods += 1
            
            pod_details.append(f"  • {name}: {phase}, Ready: {is_ready}, Restarts: {restart_count}")
        
        total_pods = len(pods)
        details = f"Found {total_pods} pod(s): {running_pods} running, {ready_pods} ready\n" + "\n".join(pod_details)
        
        if running_pods == total_pods and ready_pods == total_pods:
            print_test_result(1, "Metrics-Server Pod Status", True, details)
            return True, pod_names[0] if pod_names else None
        else:
            print_test_result(1, "Metrics-Server Pod Status", False, details)
            return False, None
            
    except json.JSONDecodeError:
        print_test_result(1, "Metrics-Server Pod Status", False,
                         "Failed to parse kubectl output")
        return False, None


def test_service_availability():
    """Test 2: Check metrics-server service status."""
    print_test_result(2, "Service Availability", None, "Checking...")
    
    cmd = "kubectl get svc -n kube-system metrics-server -o json"
    result = run_command(cmd)
    
    if not result or result.returncode != 0:
        print_test_result(2, "Service Availability", False,
                         "Failed to get metrics-server service")
        return False
    
    try:
        data = json.loads(result.stdout)
        name = data['metadata']['name']
        svc_type = data['spec']['type']
        cluster_ip = data['spec'].get('clusterIP', 'None')
        ports = data['spec'].get('ports', [])
        
        port_info = []
        for p in ports:
            port_name = p.get('name', 'unnamed')
            port_num = p.get('port')
            target_port = p.get('targetPort')
            port_info.append(f"{port_name}={port_num}→{target_port}")
        
        details = f"Service: {name}\n"
        details += f"  • Type: {svc_type}\n"
        details += f"  • ClusterIP: {cluster_ip}\n"
        details += f"  • Ports: {', '.join(port_info)}"
        
        print_test_result(2, "Service Availability", True, details)
        return True
        
    except (json.JSONDecodeError, KeyError) as e:
        print_test_result(2, "Service Availability", False,
                         f"Failed to parse service information: {e}")
        return False


def test_apiservice_registration():
    """Test 3: Check API Service registration for metrics.k8s.io."""
    print_test_result(3, "API Service Registration", None, "Checking...")
    
    cmd = "kubectl get apiservice v1beta1.metrics.k8s.io -o json"
    result = run_command(cmd)
    
    if not result or result.returncode != 0:
        print_test_result(3, "API Service Registration", False,
                         "API Service v1beta1.metrics.k8s.io not found")
        return False
    
    try:
        data = json.loads(result.stdout)
        name = data['metadata']['name']
        spec = data.get('spec', {})
        status = data.get('status', {})
        
        service_name = spec.get('service', {}).get('name', 'unknown')
        service_namespace = spec.get('service', {}).get('namespace', 'unknown')
        
        conditions = status.get('conditions', [])
        is_available = False
        condition_details = []
        
        for condition in conditions:
            cond_type = condition.get('type', '')
            cond_status = condition.get('status', '')
            cond_reason = condition.get('reason', '')
            cond_message = condition.get('message', '')
            
            condition_details.append(f"    - {cond_type}: {cond_status} ({cond_reason})")
            
            if cond_type == 'Available' and cond_status == 'True':
                is_available = True
        
        details = f"API Service: {name}\n"
        details += f"  • Service: {service_namespace}/{service_name}\n"
        details += f"  • Conditions:\n" + "\n".join(condition_details)
        
        if is_available:
            print_test_result(3, "API Service Registration", True, details)
            return True
        else:
            print_test_result(3, "API Service Registration", False,
                             f"{details}\n\n  WARNING: API Service not available!")
            return False
        
    except (json.JSONDecodeError, KeyError) as e:
        print_test_result(3, "API Service Registration", False,
                         f"Failed to parse API Service information: {e}")
        return False


def test_metrics_api():
    """Test 4: Check Metrics API availability."""
    print_test_result(4, "Metrics API Availability", None, "Checking...")
    
    # Try to query the metrics API
    cmd = "kubectl get --raw /apis/metrics.k8s.io/v1beta1 2>&1"
    result = run_command(cmd)
    
    if not result or result.returncode != 0:
        error_msg = result.stdout if result else "Unknown error"
        print_test_result(4, "Metrics API Availability", False,
                         f"Cannot access Metrics API:\n  {error_msg}")
        return False
    
    try:
        # Parse the API response
        data = json.loads(result.stdout)
        resources = data.get('resources', [])
        
        resource_names = [r.get('name', '') for r in resources]
        
        details = "Metrics API responding successfully\n"
        details += f"  • API Version: {data.get('groupVersion', 'unknown')}\n"
        details += f"  • Resources available: {', '.join(resource_names)}"
        
        print_test_result(4, "Metrics API Availability", True, details)
        return True
        
    except json.JSONDecodeError:
        # Even if we can't parse JSON, if the command succeeded, API is available
        print_test_result(4, "Metrics API Availability", True,
                         "Metrics API responding (non-JSON response)")
        return True


def test_node_metrics():
    """Test 5: Check node metrics collection."""
    print_test_result(5, "Node Metrics Collection", None, "Checking...")
    
    # Get actual node count
    cmd = "kubectl get nodes --no-headers | wc -l"
    result = run_command(cmd)
    
    if not result or result.returncode != 0:
        print_test_result(5, "Node Metrics Collection", False,
                         "Cannot get node count")
        return False
    
    actual_node_count = int(result.stdout.strip())
    
    # Try to get node metrics
    cmd = "kubectl top nodes --no-headers 2>&1"
    result = run_command(cmd)
    
    if not result or result.returncode != 0:
        error_msg = result.stdout if result else "Unknown error"
        print_test_result(5, "Node Metrics Collection", False,
                         f"Cannot retrieve node metrics:\n  {error_msg}")
        return False
    
    # Count lines (each line is a node)
    metric_lines = [line for line in result.stdout.strip().split('\n') if line.strip()]
    metric_node_count = len(metric_lines)
    
    # Show sample of first few nodes
    sample = '\n  '.join(metric_lines[:5])
    if len(metric_lines) > 5:
        sample += f"\n  ... and {len(metric_lines) - 5} more nodes"
    
    details = f"Node metrics collected: {metric_node_count}/{actual_node_count} nodes\n"
    details += f"Sample metrics:\n  {sample}"
    
    if metric_node_count == actual_node_count:
        print_test_result(5, "Node Metrics Collection", True, details)
        return True
    else:
        print_test_result(5, "Node Metrics Collection", False,
                         f"{details}\n\n  WARNING: Not all nodes have metrics!")
        return False


def test_pod_metrics():
    """Test 6: Check pod metrics collection."""
    print_test_result(6, "Pod Metrics Collection", None, "Checking...")
    
    # Get actual pod count
    cmd = "kubectl get pods -A --no-headers | wc -l"
    result = run_command(cmd)
    
    if not result or result.returncode != 0:
        print_test_result(6, "Pod Metrics Collection", False,
                         "Cannot get pod count")
        return False
    
    actual_pod_count = int(result.stdout.strip())
    
    # Try to get pod metrics
    cmd = "kubectl top pods -A --no-headers 2>&1"
    result = run_command(cmd, timeout=45)  # Longer timeout for many pods
    
    if not result or result.returncode != 0:
        error_msg = result.stdout if result else "Unknown error"
        print_test_result(6, "Pod Metrics Collection", False,
                         f"Cannot retrieve pod metrics:\n  {error_msg}")
        return False
    
    # Count lines (each line is a pod)
    metric_lines = [line for line in result.stdout.strip().split('\n') if line.strip()]
    metric_pod_count = len(metric_lines)
    
    # Show sample of first few pods
    sample = '\n  '.join(metric_lines[:5])
    if len(metric_lines) > 5:
        sample += f"\n  ... and {len(metric_lines) - 5} more pods"
    
    # Allow for some discrepancy due to pod lifecycle (pending, completed, etc.)
    coverage_percent = (metric_pod_count / actual_pod_count * 100) if actual_pod_count > 0 else 0
    
    details = f"Pod metrics collected: {metric_pod_count}/{actual_pod_count} pods ({coverage_percent:.1f}%)\n"
    details += f"Sample metrics:\n  {sample}"
    
    # Pass if we have metrics for at least 80% of pods (some may be pending/completed)
    if coverage_percent >= 80:
        print_test_result(6, "Pod Metrics Collection", True, details)
        return True
    else:
        print_test_result(6, "Pod Metrics Collection", False,
                         f"{details}\n\n  WARNING: Low metrics coverage!")
        return False


def test_configuration():
    """Test 7: Validate metrics-server configuration."""
    print_test_result(7, "Configuration Validation", None, "Checking...")
    
    cmd = "kubectl get deployment -n kube-system metrics-server -o json"
    result = run_command(cmd)
    
    if not result or result.returncode != 0:
        print_test_result(7, "Configuration Validation", False,
                         "Failed to get deployment")
        return False
    
    try:
        data = json.loads(result.stdout)
        
        # Check image version
        containers = data['spec']['template']['spec'].get('containers', [])
        if not containers:
            print_test_result(7, "Configuration Validation", False,
                             "No containers found in deployment")
            return False
        
        container = containers[0]
        image = container['image']
        
        # Extract version
        version_match = re.search(r':v?(\d+\.\d+\.?\d*)', image)
        version = version_match.group(1) if version_match else "unknown"
        
        # Check replicas
        replicas = data['spec'].get('replicas', 0)
        available_replicas = data['status'].get('availableReplicas', 0)
        
        # Check common args
        args = container.get('args', [])
        important_args = []
        for arg in args:
            if any(key in arg for key in ['--kubelet-preferred-address-types', '--kubelet-insecure-tls', '--cert-dir', '--metric-resolution']):
                important_args.append(f"    - {arg}")
        
        details_list = [
            f"  • Image: {image}",
            f"  • Version: v{version}",
            f"  • Replicas: {available_replicas}/{replicas} available",
        ]
        
        if important_args:
            details_list.append(f"  • Key Configuration Args:")
            details_list.extend(important_args)
        
        details = "\n".join(details_list)
        
        # Validation: replicas should be available
        replicas_ok = available_replicas >= replicas and replicas > 0
        
        if replicas_ok:
            print_test_result(7, "Configuration Validation", True, details)
            return True
        else:
            print_test_result(7, "Configuration Validation", False,
                             f"{details}\n\nCRITICAL: Replica issue - {available_replicas}/{replicas} available")
            return False
        
    except (json.JSONDecodeError, KeyError) as e:
        print_test_result(7, "Configuration Validation", False,
                         f"Failed to parse configuration: {e}")
        return False


def main():
    """Main execution function."""
    print_header("Metrics-Server Health Check")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Namespace: kube-system")
    print(f"Component: metrics-server")
    
    results = {}
    
    # Run tests
    results['test1'], pod_name = test_pod_status()
    results['test2'] = test_service_availability()
    results['test3'] = test_apiservice_registration()
    results['test4'] = test_metrics_api()
    results['test5'] = test_node_metrics()
    results['test6'] = test_pod_metrics()
    results['test7'] = test_configuration()
    
    # Summary
    print_header("Test Summary")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    print(f"Tests Passed: {passed}/{total}")
    print(f"Tests Failed: {total - passed}/{total}")
    
    if passed == total:
        print(f"\n{Colors.GREEN}{Colors.BOLD}✓ All tests PASSED!{Colors.END}")
        print(f"{Colors.GREEN}Metrics-server is healthy and functioning properly.{Colors.END}\n")
        return 0
    elif passed >= total * 0.85:  # 85% threshold (allow test 6 to have lower coverage)
        print(f"\n{Colors.YELLOW}{Colors.BOLD}⚠ Most tests PASSED with some warnings{Colors.END}")
        print(f"{Colors.YELLOW}Metrics-server is functional but review warnings above.{Colors.END}\n")
        return 0
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}✗ Multiple tests FAILED!{Colors.END}")
        print(f"{Colors.RED}Please review the failed tests above.{Colors.END}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())

