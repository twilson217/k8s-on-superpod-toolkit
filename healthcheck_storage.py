#!/usr/bin/env python3
"""
Storage Health Check Script - Run:AI Environment

This script validates storage functionality using Run:AI CLI commands to create
and delete data sources (PVCs) and verifies proper cleanup of both PVCs and PVs.

PREREQUISITES:
    Before running this script, you must authenticate with Run:AI:
        runai login remote-browser

Tests:
1. Run:AI CLI Connectivity
2. Project Validation
3. Data Source Creation (1GiB PVC)
4. PVC Status Verification (Bound)
5. PV Association Verification
6. Data Source Deletion
7. PVC Cleanup Verification
8. PV Cleanup Verification

Usage:
    python3 healthcheck_storage.py --project <PROJECT_NAME>

Example:
    python3 healthcheck_storage.py --project test
"""

import subprocess
import sys
import argparse
import time
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
            capture_output=capture_output,
            text=text,
            timeout=timeout,
            check=False
        )
        return result
    except subprocess.TimeoutExpired:
        print(f"{Colors.RED}✗ Command timed out after {timeout}s{Colors.END}")
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


def print_info(message):
    """Print an informational message."""
    print(f"{Colors.BLUE}ℹ {message}{Colors.END}")


def print_warning(message):
    """Print a warning message."""
    print(f"{Colors.YELLOW}⚠ {message}{Colors.END}")


def test_runai_cli():
    """Test 1: Check Run:AI CLI connectivity."""
    print_test_result(1, "Run:AI CLI Connectivity", None, "Checking...")
    
    cmd = ["runai", "config", "get"]
    result = run_command(cmd)
    
    if not result or result.returncode != 0:
        print_test_result(1, "Run:AI CLI Connectivity", False,
                         "Run:AI CLI not available or not authenticated.\n"
                         "Run: runai login remote-browser")
        return False
    
    # Try to parse config to see if we're authenticated
    if "not logged in" in result.stdout.lower() or "authentication" in result.stderr.lower():
        print_test_result(1, "Run:AI CLI Connectivity", False,
                         "Run:AI CLI not authenticated.\n"
                         "Run: runai login remote-browser")
        return False
    
    print_test_result(1, "Run:AI CLI Connectivity", True,
                     "Run:AI CLI is available and authenticated")
    return True


def test_project_validation(project_name):
    """Test 2: Validate project exists."""
    print_test_result(2, "Project Validation", None, "Checking...")
    
    cmd = ["runai", "project", "list"]
    result = run_command(cmd)
    
    if not result or result.returncode != 0:
        print_test_result(2, "Project Validation", False,
                         f"Failed to list projects: {result.stderr if result else 'command failed'}")
        return False
    
    # Check if project exists in the output
    if project_name in result.stdout:
        print_test_result(2, "Project Validation", True,
                         f"Project '{project_name}' exists")
        return True
    else:
        print_test_result(2, "Project Validation", False,
                         f"Project '{project_name}' not found in available projects")
        return False


def generate_datasource_name():
    """Generate a unique data source name."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"storage-test-{timestamp}"


def test_create_datasource(project_name, datasource_name):
    """Test 3: Create data source (PVC)."""
    print_test_result(3, "Data Source Creation (1GiB PVC)", None, "Creating...")
    
    cmd = [
        "runai", "datasource", "create", "pvc",
        datasource_name,
        "--project", project_name,
        "--storage-class", "vast-nfs-ib",
        "--size", "1Gi",
        "--access-mode", "ReadWriteMany"
    ]
    
    print_info(f"Creating data source: {datasource_name}")
    print_info(f"Command: {' '.join(cmd)}")
    
    result = run_command(cmd, timeout=60)
    
    if not result or result.returncode != 0:
        error_msg = result.stderr if result else "command failed"
        print_test_result(3, "Data Source Creation (1GiB PVC)", False,
                         f"Failed to create data source:\n{error_msg}")
        return False
    
    print_test_result(3, "Data Source Creation (1GiB PVC)", True,
                     f"Data source '{datasource_name}' created successfully")
    return True


def get_pvc_name(project_name, datasource_name, max_retries=10, retry_delay=3):
    """Get the actual PVC name created by Run:AI."""
    print_info(f"Discovering PVC name (format: {datasource_name}-project-<random>)...")
    
    for attempt in range(max_retries):
        cmd = ["kubectl", "get", "pvc", "-n", f"runai-{project_name}", "-o", "name"]
        result = run_command(cmd)
        
        if result and result.returncode == 0:
            pvcs = result.stdout.strip().split('\n')
            # Look for PVC matching the pattern: datasource-name-project-*
            pattern = f"{datasource_name}-project-"
            for pvc in pvcs:
                if pattern in pvc:
                    # Extract just the name without "persistentvolumeclaim/" prefix
                    pvc_name = pvc.replace("persistentvolumeclaim/", "")
                    print_info(f"Found PVC: {pvc_name}")
                    return pvc_name
        
        if attempt < max_retries - 1:
            print_info(f"PVC not found yet, waiting {retry_delay}s... (attempt {attempt+1}/{max_retries})")
            time.sleep(retry_delay)
    
    return None


def test_pvc_status(project_name, pvc_name):
    """Test 4: Verify PVC is bound."""
    print_test_result(4, "PVC Status Verification (Bound)", None, "Checking...")
    
    if not pvc_name:
        print_test_result(4, "PVC Status Verification (Bound)", False,
                         "PVC name not available")
        return False, None
    
    cmd = [
        "kubectl", "get", "pvc", pvc_name,
        "-n", f"runai-{project_name}",
        "-o", "jsonpath={.status.phase}|{.spec.volumeName}"
    ]
    
    # Retry up to 30 seconds for PVC to become bound
    max_retries = 10
    retry_delay = 3
    
    for attempt in range(max_retries):
        result = run_command(cmd)
        
        if result and result.returncode == 0:
            output = result.stdout.strip()
            parts = output.split('|')
            
            if len(parts) == 2:
                phase, volume_name = parts
                
                if phase == "Bound":
                    print_test_result(4, "PVC Status Verification (Bound)", True,
                                    f"PVC '{pvc_name}' is Bound to PV '{volume_name}'")
                    return True, volume_name
                else:
                    if attempt < max_retries - 1:
                        print_info(f"PVC status: {phase}, waiting for Bound... (attempt {attempt+1}/{max_retries})")
                        time.sleep(retry_delay)
                    else:
                        print_test_result(4, "PVC Status Verification (Bound)", False,
                                        f"PVC is in '{phase}' state, not Bound")
                        return False, None
        
        if attempt < max_retries - 1:
            time.sleep(retry_delay)
    
    print_test_result(4, "PVC Status Verification (Bound)", False,
                     f"Failed to get PVC status after {max_retries} attempts")
    return False, None


def test_pv_association(pv_name):
    """Test 5: Verify PV exists and is bound."""
    print_test_result(5, "PV Association Verification", None, "Checking...")
    
    if not pv_name:
        print_test_result(5, "PV Association Verification", False,
                         "PV name not available")
        return False
    
    cmd = [
        "kubectl", "get", "pv", pv_name,
        "-o", "jsonpath={.status.phase}|{.spec.storageClassName}|{.spec.capacity.storage}"
    ]
    
    result = run_command(cmd)
    
    if not result or result.returncode != 0:
        print_test_result(5, "PV Association Verification", False,
                         f"PV '{pv_name}' not found")
        return False
    
    output = result.stdout.strip()
    parts = output.split('|')
    
    if len(parts) == 3:
        phase, storage_class, capacity = parts
        
        details = f"PV '{pv_name}' details:\n"
        details += f"  • Phase: {phase}\n"
        details += f"  • Storage Class: {storage_class}\n"
        details += f"  • Capacity: {capacity}"
        
        if phase == "Bound":
            print_test_result(5, "PV Association Verification", True, details)
            return True
        else:
            print_test_result(5, "PV Association Verification", False,
                             f"{details}\n  • PV is in '{phase}' state, expected 'Bound'")
            return False
    else:
        print_test_result(5, "PV Association Verification", False,
                         f"Failed to parse PV information: {output}")
        return False


def test_delete_datasource(project_name, datasource_name):
    """Test 6: Delete data source."""
    print_test_result(6, "Data Source Deletion", None, "Deleting...")
    
    cmd = [
        "runai", "datasource", "delete", "pvc",
        datasource_name,
        "--project", project_name
    ]
    
    print_info(f"Deleting data source: {datasource_name}")
    print_info(f"Command: {' '.join(cmd)}")
    
    result = run_command(cmd, timeout=60)
    
    if not result or result.returncode != 0:
        error_msg = result.stderr if result else "command failed"
        print_test_result(6, "Data Source Deletion", False,
                         f"Failed to delete data source:\n{error_msg}")
        return False
    
    print_test_result(6, "Data Source Deletion", True,
                     f"Data source '{datasource_name}' deleted successfully")
    return True


def test_pvc_cleanup(project_name, pvc_name, max_retries=10, retry_delay=3):
    """Test 7: Verify PVC is removed."""
    print_test_result(7, "PVC Cleanup Verification", None, "Checking...")
    
    if not pvc_name:
        print_test_result(7, "PVC Cleanup Verification", False,
                         "PVC name not available")
        return False
    
    print_info(f"Waiting for PVC cleanup (max {max_retries * retry_delay}s)...")
    
    for attempt in range(max_retries):
        cmd = ["kubectl", "get", "pvc", pvc_name, "-n", f"runai-{project_name}"]
        result = run_command(cmd)
        
        if result and result.returncode != 0:
            # PVC not found - this is what we want
            print_test_result(7, "PVC Cleanup Verification", True,
                             f"PVC '{pvc_name}' successfully removed from cluster")
            return True
        
        if attempt < max_retries - 1:
            print_info(f"PVC still exists, waiting {retry_delay}s... (attempt {attempt+1}/{max_retries})")
            time.sleep(retry_delay)
    
    print_test_result(7, "PVC Cleanup Verification", False,
                     f"PVC '{pvc_name}' still exists after {max_retries * retry_delay}s")
    return False


def test_pv_cleanup(pv_name, max_retries=10, retry_delay=3):
    """Test 8: Verify PV is removed."""
    print_test_result(8, "PV Cleanup Verification", None, "Checking...")
    
    if not pv_name:
        print_test_result(8, "PV Cleanup Verification", False,
                         "PV name not available")
        return False
    
    print_info(f"Waiting for PV cleanup (max {max_retries * retry_delay}s)...")
    
    for attempt in range(max_retries):
        cmd = ["kubectl", "get", "pv", pv_name]
        result = run_command(cmd)
        
        if result and result.returncode != 0:
            # PV not found - this is what we want
            print_test_result(8, "PV Cleanup Verification", True,
                             f"PV '{pv_name}' successfully removed from cluster")
            return True
        
        # Check PV phase - it might be Released or Terminating
        if result and result.returncode == 0:
            phase_cmd = ["kubectl", "get", "pv", pv_name, "-o", "jsonpath={.status.phase}"]
            phase_result = run_command(phase_cmd)
            if phase_result:
                phase = phase_result.stdout.strip()
                print_info(f"PV status: {phase}, waiting for deletion... (attempt {attempt+1}/{max_retries})")
        
        if attempt < max_retries - 1:
            time.sleep(retry_delay)
    
    print_test_result(8, "PV Cleanup Verification", False,
                     f"PV '{pv_name}' still exists after {max_retries * retry_delay}s")
    return False


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description='Storage Health Check for Run:AI Environment',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Prerequisites:
    Before running this script, authenticate with Run:AI:
        runai login remote-browser

Example:
    python3 healthcheck_storage.py --project test
        """
    )
    parser.add_argument('--project', required=True, help='Run:AI project name')
    
    args = parser.parse_args()
    
    print_header("Storage Health Check - Run:AI Environment")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Project: {args.project}")
    
    print_warning("PREREQUISITES: Ensure you have run 'runai login remote-browser' before running this script")
    print()
    
    # Generate unique data source name
    datasource_name = generate_datasource_name()
    print_info(f"Test data source name: {datasource_name}")
    print()
    
    results = {}
    pvc_name = None
    pv_name = None
    
    # Run tests
    results['test1'] = test_runai_cli()
    if not results['test1']:
        print(f"\n{Colors.RED}Cannot proceed without Run:AI CLI access.{Colors.END}\n")
        return 1
    
    results['test2'] = test_project_validation(args.project)
    if not results['test2']:
        print(f"\n{Colors.RED}Cannot proceed with invalid project.{Colors.END}\n")
        return 1
    
    results['test3'] = test_create_datasource(args.project, datasource_name)
    
    if results['test3']:
        # Give it a moment for PVC to be created
        time.sleep(2)
        pvc_name = get_pvc_name(args.project, datasource_name)
        
        if pvc_name:
            results['test4'], pv_name = test_pvc_status(args.project, pvc_name)
            results['test5'] = test_pv_association(pv_name)
        else:
            print_test_result(4, "PVC Status Verification (Bound)", False,
                             "Could not discover PVC name")
            results['test4'] = False
            results['test5'] = False
        
        # Always try to delete the data source
        results['test6'] = test_delete_datasource(args.project, datasource_name)
        
        if results['test6']:
            # Give it a moment for cleanup to start
            time.sleep(2)
            results['test7'] = test_pvc_cleanup(args.project, pvc_name)
            results['test8'] = test_pv_cleanup(pv_name)
        else:
            print_warning(f"Deletion failed. Manual cleanup required:")
            print_warning(f"  runai datasource delete pvc {datasource_name} --project {args.project}")
            results['test7'] = False
            results['test8'] = False
    else:
        results['test4'] = False
        results['test5'] = False
        results['test6'] = False
        results['test7'] = False
        results['test8'] = False
    
    # Summary
    print_header("Test Summary")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    print(f"Tests Passed: {passed}/{total}")
    print(f"Tests Failed: {total - passed}/{total}")
    
    if passed == total:
        print(f"\n{Colors.GREEN}{Colors.BOLD}✓ All tests PASSED!{Colors.END}")
        print(f"{Colors.GREEN}Storage system is healthy and properly cleaning up resources.{Colors.END}\n")
        return 0
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}✗ Some tests FAILED!{Colors.END}")
        print(f"{Colors.RED}Please review the failed tests above.{Colors.END}\n")
        
        # Check if we need manual cleanup
        if not results.get('test6') and datasource_name:
            print_warning("Manual cleanup may be required:")
            print_warning(f"  runai datasource delete pvc {datasource_name} --project {args.project}")
            print()
        
        return 1


if __name__ == "__main__":
    sys.exit(main())

