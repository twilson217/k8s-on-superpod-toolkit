#!/usr/bin/env python3
"""
Kube-State-Metrics Health Check Script

This script validates the health and functionality of kube-state-metrics,
which exposes Kubernetes object state metrics for Prometheus monitoring.

Tests:
1. Kube-State-Metrics Pod Status
2. Service Availability
3. Metrics Endpoint Accessibility
4. Core Metrics Availability
5. Prometheus Integration (ServiceMonitor)
6. Metric Freshness Validation
7. Resource Metrics Coverage
8. Configuration Validation

Usage:
    python3 healthcheck_kube-state-metrics.py
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
    """Test 1: Check kube-state-metrics pods are running."""
    print_test_result(1, "Kube-State-Metrics Pod Status", None, "Checking...")
    
    cmd = "kubectl get pods -n kube-system -l app.kubernetes.io/name=kube-state-metrics -o json"
    result = run_command(cmd)
    
    if not result or result.returncode != 0:
        print_test_result(1, "Kube-State-Metrics Pod Status", False, 
                         "Failed to get kube-state-metrics pods")
        return False, None
    
    try:
        data = json.loads(result.stdout)
        pods = data.get('items', [])
        
        if not pods:
            print_test_result(1, "Kube-State-Metrics Pod Status", False,
                             "No kube-state-metrics pods found")
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
            print_test_result(1, "Kube-State-Metrics Pod Status", True, details)
            return True, pod_names[0] if pod_names else None
        else:
            print_test_result(1, "Kube-State-Metrics Pod Status", False, details)
            return False, None
            
    except json.JSONDecodeError:
        print_test_result(1, "Kube-State-Metrics Pod Status", False,
                         "Failed to parse kubectl output")
        return False, None


def test_service_availability():
    """Test 2: Check kube-state-metrics service status."""
    print_test_result(2, "Service Availability", None, "Checking...")
    
    cmd = "kubectl get svc -n kube-system -l app.kubernetes.io/name=kube-state-metrics -o json"
    result = run_command(cmd)
    
    if not result or result.returncode != 0:
        print_test_result(2, "Service Availability", False,
                         "Failed to get kube-state-metrics service")
        return False, None
    
    try:
        data = json.loads(result.stdout)
        services = data.get('items', [])
        
        if not services:
            print_test_result(2, "Service Availability", False,
                             "No kube-state-metrics service found")
            return False, None
        
        service_details = []
        service_name = None
        
        for svc in services:
            name = svc['metadata']['name']
            service_name = name
            svc_type = svc['spec']['type']
            cluster_ip = svc['spec'].get('clusterIP', 'None')
            ports = svc['spec'].get('ports', [])
            
            port_info = []
            for p in ports:
                port_name = p.get('name', 'unnamed')
                port_num = p.get('port')
                target_port = p.get('targetPort')
                port_info.append(f"{port_name}={port_num}→{target_port}")
            
            service_details.append(f"  • {name}: {svc_type}")
            service_details.append(f"    - ClusterIP: {cluster_ip}")
            service_details.append(f"    - Ports: {', '.join(port_info)}")
        
        details = f"Found {len(services)} service(s):\n" + "\n".join(service_details)
        print_test_result(2, "Service Availability", True, details)
        return True, service_name
        
    except json.JSONDecodeError:
        print_test_result(2, "Service Availability", False,
                         "Failed to parse kubectl output")
        return False, None


def test_metrics_endpoint(pod_name):
    """Test 3: Check metrics endpoint accessibility."""
    print_test_result(3, "Metrics Endpoint Accessibility", None, "Checking...")
    
    if not pod_name:
        print_test_result(3, "Metrics Endpoint Accessibility", False,
                         "No pod name available for testing")
        return False
    
    # Use kubectl port-forward with timeout and curl from host
    # Start port-forward in background, wait briefly, then curl
    import subprocess
    import time
    import signal
    
    port_forward_proc = None
    try:
        # Start port-forward in background
        port_forward_proc = subprocess.Popen(
            f"kubectl port-forward -n kube-system {pod_name} 18080:8080 >/dev/null 2>&1",
            shell=True,
            preexec_fn=lambda: signal.signal(signal.SIGTERM, signal.SIG_DFL)
        )
        
        # Wait for port-forward to establish
        time.sleep(2)
        
        # Try to curl the metrics endpoint
        result = run_command("curl -s http://localhost:18080/metrics 2>&1 | head -n 20", timeout=5)
        
        # Kill port-forward
        port_forward_proc.terminate()
        port_forward_proc.wait(timeout=2)
        
        if result and result.returncode == 0 and result.stdout:
            if 'kube_' in result.stdout or 'HELP' in result.stdout:
                lines = result.stdout.strip().split('\n')
                sample_metrics = '\n  '.join(lines[:10])
                details = f"Metrics endpoint responding successfully\nSample output:\n  {sample_metrics}"
                print_test_result(3, "Metrics Endpoint Accessibility", True, details)
                return True
        
        print_test_result(3, "Metrics Endpoint Accessibility", False,
                         f"Cannot access metrics endpoint via port-forward")
        return False
        
    except Exception as e:
        if port_forward_proc:
            try:
                port_forward_proc.terminate()
                port_forward_proc.wait(timeout=2)
            except:
                pass
        print_test_result(3, "Metrics Endpoint Accessibility", False,
                         f"Error accessing metrics endpoint: {e}")
        return False


def test_core_metrics(pod_name):
    """Test 4: Verify core metrics are being exposed."""
    print_test_result(4, "Core Metrics Availability", None, "Checking...")
    
    if not pod_name:
        print_test_result(4, "Core Metrics Availability", False,
                         "No pod name available for testing")
        return False
    
    # List of core metrics that should always be present
    core_metrics = [
        'kube_pod_info',
        'kube_pod_status_phase',
        'kube_node_info',
        'kube_node_status_condition',
        'kube_deployment_status_replicas',
        'kube_daemonset_status_number_ready',
        'kube_namespace_status_phase'
    ]
    
    # Fetch metrics using port-forward
    import subprocess
    import time
    import signal
    
    port_forward_proc = None
    try:
        # Start port-forward in background
        port_forward_proc = subprocess.Popen(
            f"kubectl port-forward -n kube-system {pod_name} 18080:8080 >/dev/null 2>&1",
            shell=True,
            preexec_fn=lambda: signal.signal(signal.SIGTERM, signal.SIG_DFL)
        )
        
        # Wait for port-forward to establish
        time.sleep(2)
        
        # Fetch all metrics
        result = run_command("curl -s http://localhost:18080/metrics 2>&1", timeout=10)
        
        # Kill port-forward
        port_forward_proc.terminate()
        port_forward_proc.wait(timeout=2)
        
        if not result or result.returncode != 0 or not result.stdout:
            print_test_result(4, "Core Metrics Availability", False,
                             "Cannot fetch metrics for validation")
            return False
        
        metrics_output = result.stdout
        found_metrics = []
        missing_metrics = []
        
        for metric in core_metrics:
            if metric in metrics_output:
                found_metrics.append(metric)
            else:
                missing_metrics.append(metric)
        
        details_list = [f"Found {len(found_metrics)}/{len(core_metrics)} core metrics:"]
        for metric in found_metrics:
            details_list.append(f"  ✓ {metric}")
        
        if missing_metrics:
            details_list.append("\nMissing metrics:")
            for metric in missing_metrics:
                details_list.append(f"  ✗ {metric}")
        
        details = "\n".join(details_list)
        
        if len(found_metrics) >= len(core_metrics) * 0.8:  # Allow 80% threshold
            print_test_result(4, "Core Metrics Availability", True, details)
            return True
        else:
            print_test_result(4, "Core Metrics Availability", False, details)
            return False
            
    except Exception as e:
        if port_forward_proc:
            try:
                port_forward_proc.terminate()
                port_forward_proc.wait(timeout=2)
            except:
                pass
        print_test_result(4, "Core Metrics Availability", False,
                         f"Error fetching metrics: {e}")
        return False


def test_prometheus_integration():
    """Test 5: Check Prometheus ServiceMonitor configuration."""
    print_test_result(5, "Prometheus Integration (ServiceMonitor)", None, "Checking...")
    
    # Check if ServiceMonitor exists
    cmd = "kubectl get servicemonitor -n kube-system -l app.kubernetes.io/name=kube-state-metrics -o json 2>/dev/null"
    result = run_command(cmd)
    
    if not result or result.returncode != 0:
        # ServiceMonitor might not exist if Prometheus operator is not installed
        print_test_result(5, "Prometheus Integration (ServiceMonitor)", False,
                         "ServiceMonitor not found (may not be required if not using Prometheus Operator)")
        return False
    
    try:
        data = json.loads(result.stdout)
        servicemonitors = data.get('items', [])
        
        if not servicemonitors:
            print_test_result(5, "Prometheus Integration (ServiceMonitor)", False,
                             "No ServiceMonitor found for kube-state-metrics")
            return False
        
        details_list = []
        for sm in servicemonitors:
            name = sm['metadata']['name']
            namespace = sm['metadata']['namespace']
            endpoints = sm['spec'].get('endpoints', [])
            
            details_list.append(f"  • {name} (namespace: {namespace})")
            details_list.append(f"    - Endpoints: {len(endpoints)}")
            
            for i, ep in enumerate(endpoints):
                port = ep.get('port', 'unknown')
                path = ep.get('path', '/metrics')
                interval = ep.get('interval', 'default')
                details_list.append(f"      {i+1}. Port: {port}, Path: {path}, Interval: {interval}")
        
        details = f"Found {len(servicemonitors)} ServiceMonitor(s):\n" + "\n".join(details_list)
        print_test_result(5, "Prometheus Integration (ServiceMonitor)", True, details)
        return True
        
    except json.JSONDecodeError:
        print_test_result(5, "Prometheus Integration (ServiceMonitor)", False,
                         "Failed to parse ServiceMonitor output")
        return False


def test_metric_freshness(pod_name):
    """Test 6: Validate metrics are up-to-date."""
    print_test_result(6, "Metric Freshness Validation", None, "Checking...")
    
    if not pod_name:
        print_test_result(6, "Metric Freshness Validation", False,
                         "No pod name available for testing")
        return False
    
    # Get current node count from cluster
    cmd = "kubectl get nodes --no-headers | wc -l"
    result = run_command(cmd)
    
    if not result or result.returncode != 0:
        print_test_result(6, "Metric Freshness Validation", False,
                         "Cannot get node count from cluster")
        return False
    
    actual_node_count = int(result.stdout.strip())
    
    # Get current pod count
    cmd = "kubectl get pods -A --no-headers | wc -l"
    result = run_command(cmd)
    
    if result and result.returncode == 0:
        actual_pod_count = int(result.stdout.strip())
    else:
        actual_pod_count = 0
    
    # Fetch metrics using port-forward
    import subprocess
    import time
    import signal
    
    port_forward_proc = None
    try:
        # Start port-forward in background
        port_forward_proc = subprocess.Popen(
            f"kubectl port-forward -n kube-system {pod_name} 18080:8080 >/dev/null 2>&1",
            shell=True,
            preexec_fn=lambda: signal.signal(signal.SIGTERM, signal.SIG_DFL)
        )
        
        # Wait for port-forward to establish
        time.sleep(2)
        
        # Get node count from metrics
        result = run_command("curl -s http://localhost:18080/metrics 2>&1 | grep -c '^kube_node_info{'", timeout=10)
        
        try:
            metric_node_count = int(result.stdout.strip()) if result and result.returncode == 0 else 0
        except (ValueError, AttributeError):
            metric_node_count = 0
        
        # Get pod count from metrics
        result = run_command("curl -s http://localhost:18080/metrics 2>&1 | grep -c '^kube_pod_info{'", timeout=10)
        
        try:
            metric_pod_count = int(result.stdout.strip()) if result and result.returncode == 0 else 0
        except (ValueError, AttributeError):
            metric_pod_count = 0
        
        # Kill port-forward
        port_forward_proc.terminate()
        port_forward_proc.wait(timeout=2)
        
        details = f"Metrics vs. Actual:\n"
        details += f"  • Nodes: {metric_node_count} (metrics) vs {actual_node_count} (actual)\n"
        details += f"  • Pods: {metric_pod_count} (metrics) vs {actual_pod_count} (actual)"
        
        # Allow small discrepancy due to timing
        node_match = abs(metric_node_count - actual_node_count) <= 1
        pod_match = abs(metric_pod_count - actual_pod_count) <= 5  # Pods change frequently
        
        if node_match and pod_match:
            print_test_result(6, "Metric Freshness Validation", True, 
                             details + "\n\n  Metrics are fresh and accurate!")
            return True
        else:
            print_test_result(6, "Metric Freshness Validation", False,
                             details + "\n\n  WARNING: Metrics may be stale or inaccurate!")
            return False
            
    except Exception as e:
        if port_forward_proc:
            try:
                port_forward_proc.terminate()
                port_forward_proc.wait(timeout=2)
            except:
                pass
        print_test_result(6, "Metric Freshness Validation", False,
                         f"Error validating metrics: {e}")
        return False


def test_resource_coverage():
    """Test 7: Verify metrics cover key Kubernetes resources."""
    print_test_result(7, "Resource Metrics Coverage", None, "Checking...")
    
    # Get kube-state-metrics deployment to check what resources it's monitoring
    cmd = "kubectl get deployment -n kube-system -l app.kubernetes.io/name=kube-state-metrics -o json"
    result = run_command(cmd)
    
    if not result or result.returncode != 0:
        print_test_result(7, "Resource Metrics Coverage", False,
                         "Cannot get kube-state-metrics deployment")
        return False
    
    try:
        data = json.loads(result.stdout)
        deployments = data.get('items', [])
        
        if not deployments:
            print_test_result(7, "Resource Metrics Coverage", False,
                             "No deployment found")
            return False
        
        deployment = deployments[0]
        containers = deployment['spec']['template']['spec'].get('containers', [])
        
        # Look for --resources flag in container args
        resources_monitored = []
        default_resources = [
            'pods', 'nodes', 'deployments', 'daemonsets', 'statefulsets',
            'jobs', 'cronjobs', 'services', 'namespaces', 'persistentvolumes',
            'persistentvolumeclaims', 'configmaps', 'secrets'
        ]
        
        for container in containers:
            args = container.get('args', [])
            
            # Check if --resources flag is set
            resources_arg_found = False
            for arg in args:
                if arg.startswith('--resources='):
                    resources_arg_found = True
                    resources_str = arg.split('=', 1)[1]
                    resources_monitored = resources_str.split(',')
                    break
            
            if not resources_arg_found:
                # If no --resources flag, assume default set
                resources_monitored = default_resources
        
        if not resources_monitored:
            resources_monitored = default_resources
        
        # Check for important resource types
        critical_resources = ['pods', 'nodes', 'deployments']
        has_critical = all(r in resources_monitored for r in critical_resources)
        
        details = f"Monitoring {len(resources_monitored)} resource type(s):\n"
        details += "  " + ", ".join(sorted(resources_monitored))
        
        if has_critical:
            print_test_result(7, "Resource Metrics Coverage", True, details)
            return True
        else:
            missing = [r for r in critical_resources if r not in resources_monitored]
            details += f"\n\n  WARNING: Missing critical resources: {', '.join(missing)}"
            print_test_result(7, "Resource Metrics Coverage", False, details)
            return False
        
    except (json.JSONDecodeError, KeyError) as e:
        print_test_result(7, "Resource Metrics Coverage", False,
                         f"Failed to parse deployment configuration: {e}")
        return False


def test_configuration():
    """Test 8: Validate kube-state-metrics configuration."""
    print_test_result(8, "Configuration Validation", None, "Checking...")
    
    cmd = "kubectl get deployment -n kube-system -l app.kubernetes.io/name=kube-state-metrics -o json"
    result = run_command(cmd)
    
    if not result or result.returncode != 0:
        print_test_result(8, "Configuration Validation", False,
                         "Failed to get deployment")
        return False
    
    try:
        data = json.loads(result.stdout)
        deployments = data.get('items', [])
        
        if not deployments:
            print_test_result(8, "Configuration Validation", False,
                             "No deployment found")
            return False
        
        deployment = deployments[0]
        
        # Check image version
        containers = deployment['spec']['template']['spec'].get('containers', [])
        if not containers:
            print_test_result(8, "Configuration Validation", False,
                             "No containers found in deployment")
            return False
        
        container = containers[0]
        image = container['image']
        
        # Extract version
        version_match = re.search(r':v?(\d+\.\d+\.?\d*)', image)
        version = version_match.group(1) if version_match else "unknown"
        
        # Check replicas
        replicas = deployment['spec'].get('replicas', 0)
        available_replicas = deployment['status'].get('availableReplicas', 0)
        
        # Check resource limits
        resources = container.get('resources', {})
        limits = resources.get('limits', {})
        requests = resources.get('requests', {})
        
        # Check common configuration args
        args = container.get('args', [])
        config_flags = {
            '--port': False,
            '--telemetry-port': False
        }
        
        for arg in args:
            for flag in config_flags.keys():
                if arg.startswith(flag):
                    config_flags[flag] = True
        
        details_list = [
            f"  • Image: {image}",
            f"  • Version: v{version}",
            f"  • Replicas: {available_replicas}/{replicas} available",
            f"  • Resource Requests:",
            f"    - CPU: {requests.get('cpu', 'not set')}",
            f"    - Memory: {requests.get('memory', 'not set')}",
            f"  • Resource Limits:",
            f"    - CPU: {limits.get('cpu', 'not set')}",
            f"    - Memory: {limits.get('memory', 'not set')}",
        ]
        
        details = "\n".join(details_list)
        
        # Validation: replicas should be available (critical check)
        replicas_ok = available_replicas >= replicas and replicas > 0
        
        if replicas_ok:
            print_test_result(8, "Configuration Validation", True, details)
            return True
        else:
            print_test_result(8, "Configuration Validation", False,
                             f"{details}\n\nCRITICAL: Replica issue - {available_replicas}/{replicas} available")
            return False
        
    except (json.JSONDecodeError, KeyError) as e:
        print_test_result(8, "Configuration Validation", False,
                         f"Failed to parse configuration: {e}")
        return False


def main():
    """Main execution function."""
    print_header("Kube-State-Metrics Health Check")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Namespace: kube-system")
    print(f"Component: kube-state-metrics")
    
    results = {}
    
    # Run tests
    results['test1'], pod_name = test_pod_status()
    results['test2'], service_name = test_service_availability()
    results['test3'] = test_metrics_endpoint(pod_name)
    results['test4'] = test_core_metrics(pod_name)
    results['test5'] = test_prometheus_integration()
    results['test6'] = test_metric_freshness(pod_name)
    results['test7'] = test_resource_coverage()
    results['test8'] = test_configuration()
    
    # Summary
    print_header("Test Summary")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    print(f"Tests Passed: {passed}/{total}")
    print(f"Tests Failed: {total - passed}/{total}")
    
    if passed == total:
        print(f"\n{Colors.GREEN}{Colors.BOLD}✓ All tests PASSED!{Colors.END}")
        print(f"{Colors.GREEN}Kube-state-metrics is healthy and functioning properly.{Colors.END}\n")
        return 0
    elif passed >= total * 0.75:  # 75% threshold
        print(f"\n{Colors.YELLOW}{Colors.BOLD}⚠ Most tests PASSED with some warnings{Colors.END}")
        print(f"{Colors.YELLOW}Kube-state-metrics is functional but review warnings above.{Colors.END}\n")
        return 0
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}✗ Multiple tests FAILED!{Colors.END}")
        print(f"{Colors.RED}Please review the failed tests above.{Colors.END}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())

