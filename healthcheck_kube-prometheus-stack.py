#!/usr/bin/env python3
"""
Kube-Prometheus-Stack Health Check Script

This script validates the health and functionality of kube-prometheus-stack,
which provides a comprehensive monitoring solution including Prometheus,
Alertmanager, Grafana, and various exporters.

Tests:
1. Prometheus Operator Pod Status
2. Prometheus StatefulSet Status
3. Alertmanager StatefulSet Status
4. Grafana Deployment Status
5. Node Exporter DaemonSet Status
6. ServiceMonitor Resources
7. PrometheusRule Resources
8. Prometheus Targets Health
9. Prometheus Query Functionality
10. CRD Installation Check

Usage:
    python3 healthcheck_kube-prometheus-stack.py [--namespace NAMESPACE]
    
Arguments:
    --namespace NAMESPACE    Namespace where kube-prometheus-stack is deployed (default: prometheus)
"""

import subprocess
import json
import sys
import re
import argparse
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


def test_prometheus_operator(namespace):
    """Test 1: Check Prometheus Operator pod status."""
    print_test_result(1, "Prometheus Operator Pod Status", None, "Checking...")
    
    cmd = f"kubectl get pods -n {namespace} -l app.kubernetes.io/name=kube-prometheus-stack-prometheus-operator -o json"
    result = run_command(cmd)
    
    if not result or result.returncode != 0:
        print_test_result(1, "Prometheus Operator Pod Status", False,
                         "Failed to get Prometheus Operator pods")
        return False
    
    try:
        data = json.loads(result.stdout)
        pods = data.get('items', [])
        
        if not pods:
            print_test_result(1, "Prometheus Operator Pod Status", False,
                             "No Prometheus Operator pods found")
            return False
        
        running_pods = 0
        ready_pods = 0
        pod_details = []
        
        for pod in pods:
            name = pod['metadata']['name']
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
            print_test_result(1, "Prometheus Operator Pod Status", True, details)
            return True
        else:
            print_test_result(1, "Prometheus Operator Pod Status", False, details)
            return False
            
    except (json.JSONDecodeError, KeyError) as e:
        print_test_result(1, "Prometheus Operator Pod Status", False,
                         f"Failed to parse kubectl output: {e}")
        return False


def test_prometheus_statefulset(namespace):
    """Test 2: Check Prometheus StatefulSet status."""
    print_test_result(2, "Prometheus StatefulSet Status", None, "Checking...")
    
    # Find Prometheus StatefulSets
    cmd = f"kubectl get statefulsets -n {namespace} -l app.kubernetes.io/name=prometheus -o json"
    result = run_command(cmd)
    
    if not result or result.returncode != 0:
        print_test_result(2, "Prometheus StatefulSet Status", False,
                         "Failed to get Prometheus StatefulSets")
        return False, []
    
    try:
        data = json.loads(result.stdout)
        statefulsets = data.get('items', [])
        
        if not statefulsets:
            print_test_result(2, "Prometheus StatefulSet Status", False,
                             "No Prometheus StatefulSets found")
            return False, []
        
        all_healthy = True
        sts_details = []
        prometheus_pods = []
        
        for sts in statefulsets:
            name = sts['metadata']['name']
            replicas = sts['spec'].get('replicas', 0)
            ready_replicas = sts['status'].get('readyReplicas', 0)
            
            # Get pod names
            pod_cmd = f"kubectl get pods -n {namespace} -l app.kubernetes.io/name=prometheus,statefulset.kubernetes.io/pod-name -o json"
            pod_result = run_command(pod_cmd)
            if pod_result and pod_result.returncode == 0:
                pod_data = json.loads(pod_result.stdout)
                for pod in pod_data.get('items', []):
                    prometheus_pods.append(pod['metadata']['name'])
            
            if ready_replicas >= replicas:
                sts_details.append(f"  • {name}: {ready_replicas}/{replicas} ready ✓")
            else:
                sts_details.append(f"  • {name}: {ready_replicas}/{replicas} ready ✗")
                all_healthy = False
        
        details = f"Found {len(statefulsets)} Prometheus StatefulSet(s)\n" + "\n".join(sts_details)
        
        if all_healthy:
            print_test_result(2, "Prometheus StatefulSet Status", True, details)
            return True, prometheus_pods
        else:
            print_test_result(2, "Prometheus StatefulSet Status", False, details)
            return False, []
            
    except (json.JSONDecodeError, KeyError) as e:
        print_test_result(2, "Prometheus StatefulSet Status", False,
                         f"Failed to parse kubectl output: {e}")
        return False, []


def test_alertmanager_statefulset(namespace):
    """Test 3: Check Alertmanager StatefulSet status."""
    print_test_result(3, "Alertmanager StatefulSet Status", None, "Checking...")
    
    cmd = f"kubectl get statefulsets -n {namespace} -l app.kubernetes.io/name=alertmanager -o json"
    result = run_command(cmd)
    
    if not result or result.returncode != 0:
        print_test_result(3, "Alertmanager StatefulSet Status", False,
                         "Failed to get Alertmanager StatefulSets")
        return False
    
    try:
        data = json.loads(result.stdout)
        statefulsets = data.get('items', [])
        
        if not statefulsets:
            print_test_result(3, "Alertmanager StatefulSet Status", False,
                             "No Alertmanager StatefulSets found")
            return False
        
        all_healthy = True
        sts_details = []
        
        for sts in statefulsets:
            name = sts['metadata']['name']
            replicas = sts['spec'].get('replicas', 0)
            ready_replicas = sts['status'].get('readyReplicas', 0)
            
            if ready_replicas >= replicas:
                sts_details.append(f"  • {name}: {ready_replicas}/{replicas} ready ✓")
            else:
                sts_details.append(f"  • {name}: {ready_replicas}/{replicas} ready ✗")
                all_healthy = False
        
        details = f"Found {len(statefulsets)} Alertmanager StatefulSet(s)\n" + "\n".join(sts_details)
        
        if all_healthy:
            print_test_result(3, "Alertmanager StatefulSet Status", True, details)
            return True
        else:
            print_test_result(3, "Alertmanager StatefulSet Status", False, details)
            return False
            
    except (json.JSONDecodeError, KeyError) as e:
        print_test_result(3, "Alertmanager StatefulSet Status", False,
                         f"Failed to parse kubectl output: {e}")
        return False


def test_grafana_deployment(namespace):
    """Test 4: Check Grafana deployment status."""
    print_test_result(4, "Grafana Deployment Status", None, "Checking...")
    
    cmd = f"kubectl get deployments -n {namespace} -l app.kubernetes.io/name=grafana -o json"
    result = run_command(cmd)
    
    if not result or result.returncode != 0:
        print_test_result(4, "Grafana Deployment Status", False,
                         "Failed to get Grafana deployments")
        return False
    
    try:
        data = json.loads(result.stdout)
        deployments = data.get('items', [])
        
        if not deployments:
            print_test_result(4, "Grafana Deployment Status", False,
                             "No Grafana deployments found")
            return False
        
        all_healthy = True
        deploy_details = []
        
        for deploy in deployments:
            name = deploy['metadata']['name']
            replicas = deploy['spec'].get('replicas', 0)
            available_replicas = deploy['status'].get('availableReplicas', 0)
            
            if available_replicas >= replicas:
                deploy_details.append(f"  • {name}: {available_replicas}/{replicas} available ✓")
            else:
                deploy_details.append(f"  • {name}: {available_replicas}/{replicas} available ✗")
                all_healthy = False
        
        details = f"Found {len(deployments)} Grafana deployment(s)\n" + "\n".join(deploy_details)
        
        if all_healthy:
            print_test_result(4, "Grafana Deployment Status", True, details)
            return True
        else:
            print_test_result(4, "Grafana Deployment Status", False, details)
            return False
            
    except (json.JSONDecodeError, KeyError) as e:
        print_test_result(4, "Grafana Deployment Status", False,
                         f"Failed to parse kubectl output: {e}")
        return False


def test_node_exporter_daemonset(namespace):
    """Test 5: Check Node Exporter DaemonSet status."""
    print_test_result(5, "Node Exporter DaemonSet Status", None, "Checking...")
    
    cmd = f"kubectl get daemonsets -n {namespace} -l app.kubernetes.io/name=prometheus-node-exporter -o json"
    result = run_command(cmd)
    
    if not result or result.returncode != 0:
        print_test_result(5, "Node Exporter DaemonSet Status", False,
                         "Failed to get Node Exporter DaemonSets")
        return False
    
    try:
        data = json.loads(result.stdout)
        daemonsets = data.get('items', [])
        
        if not daemonsets:
            print_test_result(5, "Node Exporter DaemonSet Status", False,
                             "No Node Exporter DaemonSets found")
            return False
        
        all_healthy = True
        ds_details = []
        
        for ds in daemonsets:
            name = ds['metadata']['name']
            desired = ds['status'].get('desiredNumberScheduled', 0)
            ready = ds['status'].get('numberReady', 0)
            available = ds['status'].get('numberAvailable', 0)
            
            if ready >= desired and available >= desired:
                ds_details.append(f"  • {name}: {ready}/{desired} ready, {available}/{desired} available ✓")
            else:
                ds_details.append(f"  • {name}: {ready}/{desired} ready, {available}/{desired} available ✗")
                all_healthy = False
        
        details = f"Found {len(daemonsets)} Node Exporter DaemonSet(s)\n" + "\n".join(ds_details)
        
        if all_healthy:
            print_test_result(5, "Node Exporter DaemonSet Status", True, details)
            return True
        else:
            print_test_result(5, "Node Exporter DaemonSet Status", False, details)
            return False
            
    except (json.JSONDecodeError, KeyError) as e:
        print_test_result(5, "Node Exporter DaemonSet Status", False,
                         f"Failed to parse kubectl output: {e}")
        return False


def test_servicemonitors(namespace):
    """Test 6: Check ServiceMonitor resources."""
    print_test_result(6, "ServiceMonitor Resources", None, "Checking...")
    
    cmd = f"kubectl get servicemonitors -n {namespace} -o json"
    result = run_command(cmd)
    
    if not result or result.returncode != 0:
        print_test_result(6, "ServiceMonitor Resources", False,
                         "Failed to get ServiceMonitors (CRD may not be installed)")
        return False
    
    try:
        data = json.loads(result.stdout)
        servicemonitors = data.get('items', [])
        
        if not servicemonitors:
            print_test_result(6, "ServiceMonitor Resources", False,
                             "No ServiceMonitors found")
            return False
        
        # Show key ServiceMonitors
        key_monitors = []
        for sm in servicemonitors[:10]:  # Show first 10
            name = sm['metadata']['name']
            endpoints = len(sm['spec'].get('endpoints', []))
            key_monitors.append(f"  • {name}: {endpoints} endpoint(s)")
        
        if len(servicemonitors) > 10:
            key_monitors.append(f"  ... and {len(servicemonitors) - 10} more")
        
        details = f"Found {len(servicemonitors)} ServiceMonitor(s)\nKey ServiceMonitors:\n" + "\n".join(key_monitors)
        
        print_test_result(6, "ServiceMonitor Resources", True, details)
        return True
            
    except (json.JSONDecodeError, KeyError) as e:
        print_test_result(6, "ServiceMonitor Resources", False,
                         f"Failed to parse kubectl output: {e}")
        return False


def test_prometheusrules(namespace):
    """Test 7: Check PrometheusRule resources."""
    print_test_result(7, "PrometheusRule Resources", None, "Checking...")
    
    cmd = f"kubectl get prometheusrules -n {namespace} -o json"
    result = run_command(cmd)
    
    if not result or result.returncode != 0:
        print_test_result(7, "PrometheusRule Resources", False,
                         "Failed to get PrometheusRules (CRD may not be installed)")
        return False
    
    try:
        data = json.loads(result.stdout)
        rules = data.get('items', [])
        
        if not rules:
            print_test_result(7, "PrometheusRule Resources", False,
                             "No PrometheusRules found")
            return False
        
        # Count total rule groups and individual rules
        total_groups = 0
        total_rules = 0
        rule_details = []
        
        for rule in rules[:10]:  # Show first 10
            name = rule['metadata']['name']
            groups = rule['spec'].get('groups', [])
            group_count = len(groups)
            rule_count = sum(len(g.get('rules', [])) for g in groups)
            total_groups += group_count
            total_rules += rule_count
            rule_details.append(f"  • {name}: {group_count} group(s), {rule_count} rule(s)")
        
        # Add counts from remaining rules
        for rule in rules[10:]:
            groups = rule['spec'].get('groups', [])
            total_groups += len(groups)
            total_rules += sum(len(g.get('rules', [])) for g in groups)
        
        if len(rules) > 10:
            rule_details.append(f"  ... and {len(rules) - 10} more PrometheusRules")
        
        details = f"Found {len(rules)} PrometheusRule(s) with {total_groups} group(s) and {total_rules} individual rule(s)\n"
        details += "Sample PrometheusRules:\n" + "\n".join(rule_details)
        
        print_test_result(7, "PrometheusRule Resources", True, details)
        return True
            
    except (json.JSONDecodeError, KeyError) as e:
        print_test_result(7, "PrometheusRule Resources", False,
                         f"Failed to parse kubectl output: {e}")
        return False


def test_prometheus_targets(namespace, prometheus_pods):
    """Test 8: Check Prometheus targets health."""
    print_test_result(8, "Prometheus Targets Health", None, "Checking...")
    
    if not prometheus_pods:
        print_test_result(8, "Prometheus Targets Health", False,
                         "No Prometheus pods available for testing")
        return False
    
    # Use the first Prometheus pod
    prometheus_pod = prometheus_pods[0]
    
    import subprocess
    import time
    import signal
    
    port_forward_proc = None
    try:
        # Port forward to Prometheus
        port_forward_proc = subprocess.Popen(
            f"kubectl port-forward -n {namespace} {prometheus_pod} 19090:9090 >/dev/null 2>&1",
            shell=True,
            preexec_fn=lambda: signal.signal(signal.SIGTERM, signal.SIG_DFL)
        )
        
        time.sleep(3)  # Wait for port-forward to establish
        
        # Query Prometheus targets API
        result = run_command("curl -s http://localhost:19090/api/v1/targets 2>&1", timeout=10)
        
        port_forward_proc.terminate()
        port_forward_proc.wait(timeout=2)
        
        if result and result.returncode == 0 and result.stdout:
            try:
                data = json.loads(result.stdout)
                if data.get('status') == 'success':
                    targets = data.get('data', {}).get('activeTargets', [])
                    
                    total_targets = len(targets)
                    up_targets = sum(1 for t in targets if t.get('health') == 'up')
                    down_targets = total_targets - up_targets
                    
                    # Sample some targets
                    sample_targets = []
                    for target in targets[:5]:
                        job = target.get('labels', {}).get('job', 'unknown')
                        health = target.get('health', 'unknown')
                        health_symbol = '✓' if health == 'up' else '✗'
                        sample_targets.append(f"    - {job}: {health} {health_symbol}")
                    
                    if total_targets > 5:
                        sample_targets.append(f"    ... and {total_targets - 5} more targets")
                    
                    details = f"Target Status: {up_targets}/{total_targets} up\n"
                    details += f"  • Up: {up_targets}\n"
                    details += f"  • Down: {down_targets}\n"
                    details += f"Sample Targets:\n" + "\n".join(sample_targets)
                    
                    # Pass if at least 90% of targets are up
                    health_percent = (up_targets / total_targets * 100) if total_targets > 0 else 0
                    if health_percent >= 90:
                        print_test_result(8, "Prometheus Targets Health", True, details)
                        return True
                    else:
                        print_test_result(8, "Prometheus Targets Health", False,
                                       f"{details}\n\nWARNING: {health_percent:.1f}% targets healthy (threshold: 90%)")
                        return False
                else:
                    print_test_result(8, "Prometheus Targets Health", False,
                                   f"Prometheus API returned status: {data.get('status')}")
                    return False
            except json.JSONDecodeError:
                print_test_result(8, "Prometheus Targets Health", False,
                               "Failed to parse Prometheus API response")
                return False
        else:
            print_test_result(8, "Prometheus Targets Health", False,
                           "Cannot access Prometheus targets API via port-forward")
            return False
    
    except Exception as e:
        if port_forward_proc:
            try:
                port_forward_proc.terminate()
                port_forward_proc.wait(timeout=2)
            except:
                pass
        print_test_result(8, "Prometheus Targets Health", False,
                       f"Error accessing Prometheus targets: {e}")
        return False


def test_prometheus_query(namespace, prometheus_pods):
    """Test 9: Check Prometheus query functionality."""
    print_test_result(9, "Prometheus Query Functionality", None, "Checking...")
    
    if not prometheus_pods:
        print_test_result(9, "Prometheus Query Functionality", False,
                         "No Prometheus pods available for testing")
        return False
    
    # Use the first Prometheus pod
    prometheus_pod = prometheus_pods[0]
    
    import subprocess
    import time
    import signal
    
    port_forward_proc = None
    try:
        # Port forward to Prometheus (use different local port if previous one is still bound)
        port_forward_proc = subprocess.Popen(
            f"kubectl port-forward -n {namespace} {prometheus_pod} 19091:9090 >/dev/null 2>&1",
            shell=True,
            preexec_fn=lambda: signal.signal(signal.SIGTERM, signal.SIG_DFL)
        )
        
        time.sleep(3)  # Wait for port-forward to establish
        
        # Test query: simple metric existence check
        query = "up"
        result = run_command(f"curl -s 'http://localhost:19091/api/v1/query?query={query}' 2>&1", timeout=10)
        
        port_forward_proc.terminate()
        port_forward_proc.wait(timeout=2)
        
        if result and result.returncode == 0 and result.stdout:
            try:
                data = json.loads(result.stdout)
                if data.get('status') == 'success':
                    result_data = data.get('data', {}).get('result', [])
                    
                    if result_data:
                        sample_count = len(result_data)
                        details = f"Query successful: '{query}' returned {sample_count} time series\n"
                        details += f"  • Prometheus is able to execute queries\n"
                        details += f"  • Data is being collected and queryable"
                        
                        print_test_result(9, "Prometheus Query Functionality", True, details)
                        return True
                    else:
                        print_test_result(9, "Prometheus Query Functionality", False,
                                       "Query succeeded but returned no data (no metrics collected yet?)")
                        return False
                else:
                    print_test_result(9, "Prometheus Query Functionality", False,
                                   f"Prometheus API returned status: {data.get('status')}")
                    return False
            except json.JSONDecodeError:
                print_test_result(9, "Prometheus Query Functionality", False,
                               "Failed to parse Prometheus API response")
                return False
        else:
            print_test_result(9, "Prometheus Query Functionality", False,
                           "Cannot access Prometheus query API via port-forward")
            return False
    
    except Exception as e:
        if port_forward_proc:
            try:
                port_forward_proc.terminate()
                port_forward_proc.wait(timeout=2)
            except:
                pass
        print_test_result(9, "Prometheus Query Functionality", False,
                       f"Error querying Prometheus: {e}")
        return False


def test_crd_installation():
    """Test 10: Check Prometheus Operator CRD installation."""
    print_test_result(10, "CRD Installation Check", None, "Checking...")
    
    required_crds = [
        'prometheuses.monitoring.coreos.com',
        'prometheusrules.monitoring.coreos.com',
        'servicemonitors.monitoring.coreos.com',
        'alertmanagers.monitoring.coreos.com',
        'podmonitors.monitoring.coreos.com'
    ]
    
    crd_details = []
    missing_crds = []
    
    for crd in required_crds:
        cmd = f"kubectl get crd {crd} -o json 2>&1"
        result = run_command(cmd)
        
        if result and result.returncode == 0:
            try:
                data = json.loads(result.stdout)
                version = data['metadata'].get('resourceVersion', 'unknown')
                crd_details.append(f"  ✓ {crd}")
            except:
                crd_details.append(f"  ? {crd} (found but unable to parse)")
        else:
            crd_details.append(f"  ✗ {crd}")
            missing_crds.append(crd)
    
    details = f"CRD Status:\n" + "\n".join(crd_details)
    
    if not missing_crds:
        print_test_result(10, "CRD Installation Check", True,
                         f"{details}\n\nAll required CRDs are installed")
        return True
    else:
        print_test_result(10, "CRD Installation Check", False,
                         f"{details}\n\nMissing CRDs: {', '.join(missing_crds)}")
        return False


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description='Kube-Prometheus-Stack Health Check')
    parser.add_argument('--namespace', '-n', default='prometheus',
                       help='Namespace where kube-prometheus-stack is deployed (default: prometheus)')
    args = parser.parse_args()
    
    namespace = args.namespace
    
    print_header("Kube-Prometheus-Stack Health Check")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Namespace: {namespace}")
    print(f"Component: kube-prometheus-stack")
    
    results = {}
    
    # Run tests
    results['test1'] = test_prometheus_operator(namespace)
    results['test2'], prometheus_pods = test_prometheus_statefulset(namespace)
    results['test3'] = test_alertmanager_statefulset(namespace)
    results['test4'] = test_grafana_deployment(namespace)
    results['test5'] = test_node_exporter_daemonset(namespace)
    results['test6'] = test_servicemonitors(namespace)
    results['test7'] = test_prometheusrules(namespace)
    results['test8'] = test_prometheus_targets(namespace, prometheus_pods)
    results['test9'] = test_prometheus_query(namespace, prometheus_pods)
    results['test10'] = test_crd_installation()
    
    # Summary
    print_header("Test Summary")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    print(f"Tests Passed: {passed}/{total}")
    print(f"Tests Failed: {total - passed}/{total}")
    
    if passed == total:
        print(f"\n{Colors.GREEN}{Colors.BOLD}✓ All tests PASSED!{Colors.END}")
        print(f"{Colors.GREEN}Kube-prometheus-stack is healthy and functioning properly.{Colors.END}\n")
        return 0
    elif passed >= total * 0.8:  # 80% threshold (allow some optional components)
        print(f"\n{Colors.YELLOW}{Colors.BOLD}⚠ Most tests PASSED with some warnings{Colors.END}")
        print(f"{Colors.YELLOW}Kube-prometheus-stack is functional but review warnings above.{Colors.END}\n")
        return 0
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}✗ Multiple tests FAILED!{Colors.END}")
        print(f"{Colors.RED}Please review the failed tests above.{Colors.END}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())

