#!/usr/bin/env python3
"""
Ingress-NGINX Controller Health Check Script

This script validates the health and functionality of the ingress-nginx controller,
including TLS certificate configuration.

Tests:
1. Ingress-NGINX Controller Pods
2. Ingress-NGINX Service Status
3. Default TLS Certificate Configuration
4. Ingress Resources Discovery
5. Certificate Domain Validation
6. Ingress Endpoint Connectivity
7. TLS Certificate Verification (via Run:AI hostname)
8. Controller Configuration Validation

Usage:
    python3 healthcheck_ingress-nginx.py
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


def run_command(cmd, capture_output=True, text=True):
    """Execute a shell command and return the result."""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=capture_output,
            text=text,
            timeout=30
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
    status = f"{Colors.GREEN}✓ PASS{Colors.END}" if passed else f"{Colors.RED}✗ FAIL{Colors.END}"
    print(f"{Colors.BOLD}Test {test_num}: {test_name}{Colors.END}")
    print(f"Status: {status}")
    if message:
        print(f"Details: {message}")
    print()


def test_controller_pods():
    """Test 1: Check ingress-nginx controller pods are running."""
    print_test_result(1, "Ingress-NGINX Controller Pods", None, "Checking...")
    
    cmd = "kubectl get pods -n ingress-nginx -l app.kubernetes.io/component=controller -o json"
    result = run_command(cmd)
    
    if not result or result.returncode != 0:
        print_test_result(1, "Ingress-NGINX Controller Pods", False, 
                         "Failed to get controller pods")
        return False
    
    try:
        data = json.loads(result.stdout)
        pods = data.get('items', [])
        
        if not pods:
            print_test_result(1, "Ingress-NGINX Controller Pods", False,
                             "No ingress-nginx controller pods found")
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
            
            if phase == 'Running':
                running_pods += 1
            if is_ready:
                ready_pods += 1
            
            pod_details.append(f"  • {name}: {phase}, Ready: {is_ready}")
        
        total_pods = len(pods)
        details = f"Found {total_pods} controller pod(s): {running_pods} running, {ready_pods} ready\n" + "\n".join(pod_details)
        
        if running_pods == total_pods and ready_pods == total_pods:
            print_test_result(1, "Ingress-NGINX Controller Pods", True, details)
            return True
        else:
            print_test_result(1, "Ingress-NGINX Controller Pods", False, details)
            return False
            
    except json.JSONDecodeError:
        print_test_result(1, "Ingress-NGINX Controller Pods", False,
                         "Failed to parse kubectl output")
        return False


def test_service_status():
    """Test 2: Check ingress-nginx service status."""
    print_test_result(2, "Ingress-NGINX Service Status", None, "Checking...")
    
    cmd = "kubectl get svc -n ingress-nginx -o json"
    result = run_command(cmd)
    
    if not result or result.returncode != 0:
        print_test_result(2, "Ingress-NGINX Service Status", False,
                         "Failed to get ingress-nginx services")
        return False
    
    try:
        data = json.loads(result.stdout)
        services = data.get('items', [])
        
        required_services = ['ingress-nginx-controller', 'ingress-nginx-controller-admission']
        found_services = {}
        
        for svc in services:
            name = svc['metadata']['name']
            if name in required_services:
                svc_type = svc['spec']['type']
                cluster_ip = svc['spec'].get('clusterIP', 'None')
                ports = svc['spec'].get('ports', [])
                port_info = [f"{p.get('port')}/{p.get('protocol', 'TCP')}" for p in ports]
                
                found_services[name] = {
                    'type': svc_type,
                    'clusterIP': cluster_ip,
                    'ports': ', '.join(port_info)
                }
        
        # Check for LoadBalancer service (optional, for Run:AI)
        for svc in services:
            name = svc['metadata']['name']
            if svc['spec']['type'] == 'LoadBalancer':
                external_ips = svc['status'].get('loadBalancer', {}).get('ingress', [])
                if external_ips:
                    lb_ip = external_ips[0].get('ip', 'Pending')
                    found_services[name] = {
                        'type': 'LoadBalancer',
                        'externalIP': lb_ip,
                        'clusterIP': svc['spec'].get('clusterIP', 'None')
                    }
        
        details_list = []
        for svc_name, info in found_services.items():
            if 'externalIP' in info:
                details_list.append(f"  • {svc_name}: {info['type']}, External IP: {info['externalIP']}")
            else:
                details_list.append(f"  • {svc_name}: {info['type']}, ClusterIP: {info['clusterIP']}, Ports: {info['ports']}")
        
        details = f"Found {len(found_services)} service(s):\n" + "\n".join(details_list)
        
        if all(svc in found_services for svc in required_services):
            print_test_result(2, "Ingress-NGINX Service Status", True, details)
            return True
        else:
            missing = [svc for svc in required_services if svc not in found_services]
            print_test_result(2, "Ingress-NGINX Service Status", False,
                             f"Missing required services: {', '.join(missing)}\n{details}")
            return False
            
    except json.JSONDecodeError:
        print_test_result(2, "Ingress-NGINX Service Status", False,
                         "Failed to parse kubectl output")
        return False


def test_default_tls_certificate():
    """Test 3: Check default TLS certificate configuration."""
    print_test_result(3, "Default TLS Certificate Configuration", None, "Checking...")
    
    # Check if secret exists
    cmd = "kubectl get secret ingress-server-default-tls -n ingress-nginx -o json"
    result = run_command(cmd)
    
    if not result or result.returncode != 0:
        print_test_result(3, "Default TLS Certificate Configuration", False,
                         "Secret 'ingress-server-default-tls' not found in ingress-nginx namespace")
        return False
    
    try:
        data = json.loads(result.stdout)
        secret_type = data.get('type', '')
        
        if secret_type != 'kubernetes.io/tls':
            print_test_result(3, "Default TLS Certificate Configuration", False,
                             f"Secret has wrong type: {secret_type} (expected: kubernetes.io/tls)")
            return False
        
        # Check controller is configured to use it
        cmd = "kubectl get deployment ingress-nginx-controller -n ingress-nginx -o json"
        result = run_command(cmd)
        
        if not result or result.returncode != 0:
            print_test_result(3, "Default TLS Certificate Configuration", False,
                             "Failed to get controller deployment")
            return False
        
        deployment_data = json.loads(result.stdout)
        containers = deployment_data['spec']['template']['spec']['containers']
        
        cert_arg_found = False
        for container in containers:
            if container['name'] == 'controller':
                args = container.get('args', [])
                for arg in args:
                    if '--default-ssl-certificate=' in arg and 'ingress-server-default-tls' in arg:
                        cert_arg_found = True
                        break
        
        if cert_arg_found:
            print_test_result(3, "Default TLS Certificate Configuration", True,
                             "Secret exists and controller is configured to use it:\n"
                             "  • Secret: ingress-server-default-tls\n"
                             "  • Controller arg: --default-ssl-certificate=$(POD_NAMESPACE)/ingress-server-default-tls")
            return True
        else:
            print_test_result(3, "Default TLS Certificate Configuration", False,
                             "Secret exists but controller is not configured to use it")
            return False
            
    except (json.JSONDecodeError, KeyError) as e:
        print_test_result(3, "Default TLS Certificate Configuration", False,
                         f"Failed to parse configuration: {e}")
        return False


def test_ingress_resources():
    """Test 4: Check for ingress resources."""
    print_test_result(4, "Ingress Resources Discovery", None, "Checking...")
    
    cmd = "kubectl get ingress -A -o json"
    result = run_command(cmd)
    
    if not result or result.returncode != 0:
        print_test_result(4, "Ingress Resources Discovery", False,
                         "Failed to get ingress resources")
        return False, {}
    
    try:
        data = json.loads(result.stdout)
        ingresses = data.get('items', [])
        
        if not ingresses:
            print_test_result(4, "Ingress Resources Discovery", False,
                             "No ingress resources found in cluster")
            return False, {}
        
        ingress_info = {}
        details_list = []
        
        for ingress in ingresses:
            namespace = ingress['metadata']['namespace']
            name = ingress['metadata']['name']
            hosts = []
            tls_hosts = []
            
            # Get hosts from rules
            rules = ingress['spec'].get('rules', [])
            for rule in rules:
                if 'host' in rule:
                    hosts.append(rule['host'])
            
            # Get TLS hosts
            tls_configs = ingress['spec'].get('tls', [])
            for tls in tls_configs:
                tls_hosts.extend(tls.get('hosts', []))
                secret_name = tls.get('secretName', 'default')
            
            ingress_class = ingress['spec'].get('ingressClassName', 'not-set')
            
            key = f"{namespace}/{name}"
            ingress_info[key] = {
                'hosts': hosts,
                'tls_hosts': tls_hosts,
                'class': ingress_class
            }
            
            details_list.append(f"  • {namespace}/{name}:")
            details_list.append(f"    - Hosts: {', '.join(hosts) if hosts else 'none'}")
            details_list.append(f"    - TLS: {', '.join(tls_hosts) if tls_hosts else 'none'}")
            details_list.append(f"    - Class: {ingress_class}")
        
        details = f"Found {len(ingresses)} ingress resource(s):\n" + "\n".join(details_list)
        print_test_result(4, "Ingress Resources Discovery", True, details)
        return True, ingress_info
        
    except json.JSONDecodeError:
        print_test_result(4, "Ingress Resources Discovery", False,
                         "Failed to parse kubectl output")
        return False, {}


def test_certificate_domain():
    """Test 5: Validate certificate is for correct domain (not ingress.local)."""
    print_test_result(5, "Certificate Domain Validation", None, "Checking...")
    
    cmd = "kubectl get secret ingress-server-default-tls -n ingress-nginx -o json"
    result = run_command(cmd)
    
    if not result or result.returncode != 0:
        print_test_result(5, "Certificate Domain Validation", False,
                         "Cannot retrieve TLS certificate secret")
        return False, None
    
    try:
        data = json.loads(result.stdout)
        cert_data = data['data'].get('tls.crt', '')
        
        if not cert_data:
            print_test_result(5, "Certificate Domain Validation", False,
                             "No certificate data found in secret")
            return False, None
        
        # Decode and check certificate
        import base64
        import tempfile
        
        cert_decoded = base64.b64decode(cert_data)
        
        # Write to temp file and use openssl to extract subject
        with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.crt') as f:
            f.write(cert_decoded)
            cert_file = f.name
        
        cmd = f"openssl x509 -in {cert_file} -noout -subject -issuer -dates 2>/dev/null"
        result = run_command(cmd)
        
        # Clean up temp file
        import os
        os.unlink(cert_file)
        
        if not result or result.returncode != 0:
            print_test_result(5, "Certificate Domain Validation", False,
                             "Failed to parse certificate with openssl")
            return False, None
        
        cert_info = result.stdout
        
        # Check if it's the default ingress.local certificate
        if 'ingress.local' in cert_info.lower():
            print_test_result(5, "Certificate Domain Validation", False,
                             f"Certificate is for default 'ingress.local' domain!\n{cert_info}\n"
                             "ACTION REQUIRED: Run 'cm-kubernetes-setup' and select 'Configure Ingress'")
            return False, None
        
        # Extract CN or SANs
        cn_match = re.search(r'CN\s*=\s*([^,\n]+)', cert_info)
        domain = cn_match.group(1).strip() if cn_match else "unknown"
        
        print_test_result(5, "Certificate Domain Validation", True,
                         f"Certificate is properly configured:\n{cert_info}")
        return True, domain
        
    except Exception as e:
        print_test_result(5, "Certificate Domain Validation", False,
                         f"Error validating certificate: {e}")
        return False, None


def test_ingress_connectivity(ingress_info):
    """Test 6: Test connectivity to ingress endpoints."""
    print_test_result(6, "Ingress Endpoint Connectivity", None, "Checking...")
    
    if not ingress_info:
        print_test_result(6, "Ingress Endpoint Connectivity", False,
                         "No ingress resources to test (skipped)")
        return False, None
    
    # Find Run:AI ingress for testing
    runai_ingress = None
    runai_host = None
    
    for key, info in ingress_info.items():
        if 'runai-backend' in key and info['hosts']:
            runai_ingress = key
            runai_host = info['hosts'][0]
            break
    
    if not runai_host:
        print_test_result(6, "Ingress Endpoint Connectivity", False,
                         "Could not find Run:AI ingress hostname for testing")
        return False, None
    
    # Test HTTPS connectivity (just check if port is open)
    cmd = f"timeout 5 bash -c 'echo > /dev/tcp/{runai_host}/443' 2>/dev/null"
    result = run_command(cmd)
    
    if result and result.returncode == 0:
        print_test_result(6, "Ingress Endpoint Connectivity", True,
                         f"Successfully connected to {runai_host}:443")
        return True, runai_host
    else:
        print_test_result(6, "Ingress Endpoint Connectivity", False,
                         f"Cannot connect to {runai_host}:443")
        return False, runai_host


def test_tls_verification(hostname):
    """Test 7: Verify TLS certificate via hostname."""
    print_test_result(7, "TLS Certificate Verification", None, "Checking...")
    
    if not hostname:
        print_test_result(7, "TLS Certificate Verification", False,
                         "No hostname available for testing (skipped)")
        return False
    
    # Use openssl to check the certificate
    cmd = f"timeout 10 openssl s_client -connect {hostname}:443 -servername {hostname} < /dev/null 2>/dev/null | openssl x509 -noout -subject -issuer -dates 2>/dev/null"
    result = run_command(cmd)
    
    if not result or result.returncode != 0:
        print_test_result(7, "TLS Certificate Verification", False,
                         f"Failed to retrieve certificate from {hostname}:443")
        return False
    
    cert_info = result.stdout.strip()
    
    # Check if certificate matches the hostname
    if hostname.replace('https://', '').replace('http://', '') in cert_info:
        print_test_result(7, "TLS Certificate Verification", True,
                         f"Certificate verified for {hostname}:\n{cert_info}")
        return True
    else:
        print_test_result(7, "TLS Certificate Verification", False,
                         f"Certificate does not match {hostname}:\n{cert_info}")
        return False


def test_controller_configuration():
    """Test 8: Validate controller configuration."""
    print_test_result(8, "Controller Configuration Validation", None, "Checking...")
    
    cmd = "kubectl get deployment ingress-nginx-controller -n ingress-nginx -o json"
    result = run_command(cmd)
    
    if not result or result.returncode != 0:
        print_test_result(8, "Controller Configuration Validation", False,
                         "Failed to get controller deployment")
        return False
    
    try:
        data = json.loads(result.stdout)
        
        # Check image version
        containers = data['spec']['template']['spec']['containers']
        controller_container = None
        for container in containers:
            if container['name'] == 'controller':
                controller_container = container
                break
        
        if not controller_container:
            print_test_result(8, "Controller Configuration Validation", False,
                             "Controller container not found")
            return False
        
        image = controller_container['image']
        args = controller_container.get('args', [])
        
        # Extract version from image
        version_match = re.search(r':v?(\d+\.\d+\.\d+)', image)
        version = version_match.group(1) if version_match else "unknown"
        
        # Check for key configuration arguments
        key_args = {
            '--default-ssl-certificate': False,
            '--publish-service': False,
            '--ingress-class': False
        }
        
        for arg in args:
            for key in key_args.keys():
                if arg.startswith(key):
                    key_args[key] = True
        
        # Check replicas
        replicas = data['spec'].get('replicas', 0)
        available_replicas = data['status'].get('availableReplicas', 0)
        
        details_list = [
            f"  • Image: {image}",
            f"  • Version: v{version}",
            f"  • Replicas: {available_replicas}/{replicas} available",
            f"  • Configuration:"
        ]
        
        for arg_name, found in key_args.items():
            status = "✓" if found else "✗"
            details_list.append(f"    {status} {arg_name}")
        
        details = "\n".join(details_list)
        
        all_args_found = all(key_args.values())
        replicas_ok = available_replicas >= replicas and replicas > 0
        
        if all_args_found and replicas_ok:
            print_test_result(8, "Controller Configuration Validation", True, details)
            return True
        else:
            issues = []
            if not all_args_found:
                missing = [k for k, v in key_args.items() if not v]
                issues.append(f"Missing args: {', '.join(missing)}")
            if not replicas_ok:
                issues.append(f"Replica issue: {available_replicas}/{replicas}")
            
            print_test_result(8, "Controller Configuration Validation", False,
                             f"{details}\n\nIssues: {'; '.join(issues)}")
            return False
            
    except (json.JSONDecodeError, KeyError) as e:
        print_test_result(8, "Controller Configuration Validation", False,
                         f"Failed to parse configuration: {e}")
        return False


def main():
    """Main execution function."""
    print_header("Ingress-NGINX Controller Health Check")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Namespace: ingress-nginx")
    
    results = {}
    
    # Run tests
    results['test1'] = test_controller_pods()
    results['test2'] = test_service_status()
    results['test3'] = test_default_tls_certificate()
    results['test4'], ingress_info = test_ingress_resources()
    results['test5'], cert_domain = test_certificate_domain()
    results['test6'], hostname = test_ingress_connectivity(ingress_info)
    results['test7'] = test_tls_verification(hostname)
    results['test8'] = test_controller_configuration()
    
    # Summary
    print_header("Test Summary")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    print(f"Tests Passed: {passed}/{total}")
    print(f"Tests Failed: {total - passed}/{total}")
    
    if passed == total:
        print(f"\n{Colors.GREEN}{Colors.BOLD}✓ All tests PASSED!{Colors.END}")
        print(f"{Colors.GREEN}Ingress-NGINX controller is healthy and properly configured.{Colors.END}\n")
        return 0
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}✗ Some tests FAILED!{Colors.END}")
        print(f"{Colors.RED}Please review the failed tests above.{Colors.END}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())

