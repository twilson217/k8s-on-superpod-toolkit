#!/usr/bin/env python3
"""
Storage Health Check Script - Run:AI Environment

This script validates storage functionality using Run:AI REST API to create
and delete data sources (PVCs) and verifies proper cleanup of both PVCs and PVs.

PREREQUISITES:
    1. Run the script - it will create a runai.env template if not found
    2. Edit runai.env and provide:
       - RUNAI_URL (e.g., https://runai.example.com)
       - RUNAI_CLIENT_ID (your API client ID)
       - RUNAI_CLIENT_SECRET (your API client secret)
    3. Run the script again - it will auto-discover RUNAI_CLUSTER_ID

    Note: runai.env is gitignored for security

Tests:
1. Environment Configuration Check
2. Run:AI API Authentication
3. Project Validation
4. Data Source Creation (1GiB PVC via API)
5. PVC Status Verification (Bound)
6. PV Association Verification
7. Data Source Deletion (via API)
8. PVC Cleanup Verification
9. PV Cleanup Verification

Usage:
    python3 healthcheck_storage.py --project <PROJECT_NAME>

Example:
    python3 healthcheck_storage.py --project test
"""

import subprocess
import sys
import argparse
import time
import os
import json
import requests
from datetime import datetime
from pathlib import Path


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
    if passed is None:
        # In-progress status
        status = f"{Colors.YELLOW}⏳ {message}{Colors.END}" if message else f"{Colors.YELLOW}⏳ RUNNING{Colors.END}"
        print(f"{Colors.BOLD}Test {test_num}: {test_name}{Colors.END}")
        print(f"Status: {status}")
        print()
    else:
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


def create_env_template(env_file='runai.env'):
    """Create a template runai.env file."""
    template = """# RunAI API Configuration
# This file contains sensitive credentials - DO NOT commit to version control

# RunAI Instance Configuration
RUNAI_URL=

# RunAI API Credentials
RUNAI_CLIENT_ID=
RUNAI_CLIENT_SECRET=

# RunAI Cluster ID (auto-populated by script)
RUNAI_CLUSTER_ID=
"""
    with open(env_file, 'w') as f:
        f.write(template)


def load_env_file(env_file='runai.env'):
    """Load environment variables from .env file."""
    env_path = Path(env_file)
    if not env_path.exists():
        return False, {}
    
    env_vars = {}
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                os.environ[key] = value
                env_vars[key] = value
    return True, env_vars


def update_env_file(env_file='runai.env', updates=None):
    """Update specific values in the .env file."""
    if updates is None:
        return
    
    lines = []
    env_path = Path(env_file)
    
    if env_path.exists():
        with open(env_path) as f:
            lines = f.readlines()
    
    # Update existing keys or keep lines as-is
    updated_keys = set()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped and not stripped.startswith('#') and '=' in stripped:
            key = stripped.split('=', 1)[0].strip()
            if key in updates:
                lines[i] = f"{key}={updates[key]}\n"
                updated_keys.add(key)
    
    # Write back to file
    with open(env_path, 'w') as f:
        f.writelines(lines)


def fetch_cluster_id(runai_url, client_id, client_secret):
    """Fetch cluster ID from Run:AI API."""
    print_info("Fetching cluster information from Run:AI API...")
    
    # First, authenticate
    token_url = f"{runai_url}/api/v1/token"
    payload = {
        "grantType": "client_credentials",
        "clientId": client_id,
        "clientSecret": client_secret
    }
    
    try:
        response = requests.post(token_url, json=payload, timeout=30, verify=True)
        if response.status_code != 200:
            print_warning(f"Authentication failed: {response.status_code}")
            return None
        
        token = response.json().get('accessToken')
        if not token:
            print_warning("No access token in response")
            return None
        
        # Now get clusters
        clusters_url = f"{runai_url}/api/v1/clusters"
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        
        response = requests.get(clusters_url, headers=headers, timeout=30, verify=True)
        if response.status_code != 200:
            print_warning(f"Failed to fetch clusters: {response.status_code}")
            return None
        
        clusters = response.json()
        if not clusters or len(clusters) == 0:
            print_warning("No clusters found")
            return None
        
        if len(clusters) == 1:
            cluster = clusters[0]
            cluster_id = cluster.get('uuid')
            cluster_name = cluster.get('name')
            print_info(f"Found cluster: {cluster_name} (ID: {cluster_id})")
            return cluster_id
        else:
            # Multiple clusters - use the first one and inform user
            cluster = clusters[0]
            cluster_id = cluster.get('uuid')
            cluster_name = cluster.get('name')
            print_info(f"Found {len(clusters)} clusters, using: {cluster_name} (ID: {cluster_id})")
            return cluster_id
            
    except requests.exceptions.RequestException as e:
        print_warning(f"API request failed: {e}")
        return None


def test_environment_config():
    """Test 1: Check environment configuration."""
    print_test_result(1, "Environment Configuration Check", None, "Checking...")
    
    # Check if runai.env exists
    env_path = Path('runai.env')
    if not env_path.exists():
        print_info("runai.env not found, creating template...")
        create_env_template()
        print_test_result(1, "Environment Configuration Check", False,
                         f"Created {Colors.BOLD}runai.env{Colors.END} template file.\n"
                         f"Please edit this file and add:\n"
                         f"  • RUNAI_URL (e.g., https://runai.example.com)\n"
                         f"  • RUNAI_CLIENT_ID (your API client ID)\n"
                         f"  • RUNAI_CLIENT_SECRET (your API client secret)\n\n"
                         f"Then run this script again.\n"
                         f"Note: RUNAI_CLUSTER_ID will be auto-populated.")
        return False, {}
    
    # Load runai.env
    exists, env_vars = load_env_file()
    if not exists:
        print_test_result(1, "Environment Configuration Check", False,
                         "Failed to load runai.env")
        return False, {}
    
    # Check user-provided required variables
    user_required_vars = ['RUNAI_URL', 'RUNAI_CLIENT_ID', 'RUNAI_CLIENT_SECRET']
    missing = []
    config = {}
    
    for var in user_required_vars:
        value = env_vars.get(var, '').strip()
        if not value:
            missing.append(var)
        else:
            config[var] = value
    
    if missing:
        print_test_result(1, "Environment Configuration Check", False,
                         f"Please edit {Colors.BOLD}runai.env{Colors.END} and provide values for:\n"
                         f"  • {', '.join(missing)}\n\n"
                         f"Then run this script again.")
        return False, {}
    
    # Check if cluster ID is missing and auto-fetch it
    cluster_id = env_vars.get('RUNAI_CLUSTER_ID', '').strip()
    if not cluster_id:
        print_info("RUNAI_CLUSTER_ID not set, attempting to auto-discover...")
        cluster_id = fetch_cluster_id(config['RUNAI_URL'], config['RUNAI_CLIENT_ID'], config['RUNAI_CLIENT_SECRET'])
        
        if cluster_id:
            # Save it to the file
            update_env_file(updates={'RUNAI_CLUSTER_ID': cluster_id})
            config['RUNAI_CLUSTER_ID'] = cluster_id
            print_info(f"Saved RUNAI_CLUSTER_ID to runai.env")
        else:
            print_test_result(1, "Environment Configuration Check", False,
                             "Could not auto-discover RUNAI_CLUSTER_ID.\n"
                             "Please add it manually to runai.env and try again.")
            return False, {}
    else:
        config['RUNAI_CLUSTER_ID'] = cluster_id
    
    details = f"Environment loaded successfully:\n"
    details += f"  • RUNAI_URL: {config['RUNAI_URL']}\n"
    details += f"  • RUNAI_CLIENT_ID: {config['RUNAI_CLIENT_ID']}\n"
    details += f"  • RUNAI_CLUSTER_ID: {config['RUNAI_CLUSTER_ID'][:8]}..."
    
    print_test_result(1, "Environment Configuration Check", True, details)
    return True, config


def test_api_authentication(config):
    """Test 2: Authenticate with Run:AI API."""
    print_test_result(2, "Run:AI API Authentication", None, "Authenticating...")
    
    url = f"{config['RUNAI_URL']}/api/v1/token"
    
    payload = {
        "grantType": "client_credentials",
        "clientId": config['RUNAI_CLIENT_ID'],
        "clientSecret": config['RUNAI_CLIENT_SECRET']
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30, verify=True)
        
        if response.status_code == 200:
            data = response.json()
            token = data.get('accessToken')
            
            if token:
                print_test_result(2, "Run:AI API Authentication", True,
                                 "Successfully obtained API access token")
                return True, token
            else:
                print_test_result(2, "Run:AI API Authentication", False,
                                 "No access token in response")
                return False, None
        else:
            print_test_result(2, "Run:AI API Authentication", False,
                             f"Authentication failed: {response.status_code}\n{response.text}")
            return False, None
            
    except requests.exceptions.RequestException as e:
        print_test_result(2, "Run:AI API Authentication", False,
                         f"API request failed: {e}")
        return False, None


def get_project_id(config, token, project_name):
    """Get project ID from project name."""
    url = f"{config['RUNAI_URL']}/api/v1/org-unit/projects"
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30, verify=True)
        
        if response.status_code == 200:
            data = response.json()
            projects = data.get('projects', [])
            for project in projects:
                if project.get('name') == project_name:
                    return project.get('id')
        
        return None
        
    except requests.exceptions.RequestException:
        return None


def test_project_validation(config, token, project_name):
    """Test 3: Validate project exists."""
    print_test_result(3, "Project Validation", None, "Checking...")
    
    project_id = get_project_id(config, token, project_name)
    
    if project_id:
        print_test_result(3, "Project Validation", True,
                         f"Project '{project_name}' found with ID: {project_id}")
        return True, project_id
    else:
        print_test_result(3, "Project Validation", False,
                         f"Project '{project_name}' not found")
        return False, None


def generate_datasource_name():
    """Generate a unique data source name."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"storage-test-{timestamp}"


def test_create_datasource(config, token, project_id, datasource_name):
    """Test 4: Create data source (PVC via API)."""
    print_test_result(4, "Data Source Creation (1GiB PVC via API)", None, "Creating...")
    
    url = f"{config['RUNAI_URL']}/api/v1/asset/datasource/pvc"
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        "meta": {
            "name": datasource_name,
            "scope": "project",
            "projectId": int(project_id),  # API expects integer, not string
            "clusterId": config['RUNAI_CLUSTER_ID']
        },
        "spec": {
            "path": "/mnt/storage-test",
            "existingPvc": False,
            "claimInfo": {
                "size": "1Gi",
                "storageClass": "vast-nfs-ib",
                "accessModes": {
                    "readWriteMany": True
                },
                "volumeMode": "Filesystem"
            }
        }
    }
    
    print_info(f"Creating data source: {datasource_name}")
    print_info(f"API: POST {url}")
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60, verify=True)
        
        if response.status_code == 202:
            data = response.json()
            
            # Debug: show what we got back
            print_info(f"Response data: {json.dumps(data, indent=2)}")
            
            asset_id = data.get('id')
            
            if asset_id:
                details = f"Data source created successfully\n"
                details += f"  • Name: {datasource_name}\n"
                details += f"  • Asset ID: {asset_id}\n"
                details += f"  • Size: 1Gi\n"
                details += f"  • Storage Class: vast-nfs-ib"
                
                print_test_result(4, "Data Source Creation (1GiB PVC via API)", True, details)
                return True, asset_id
            else:
                print_test_result(4, "Data Source Creation (1GiB PVC via API)", False,
                                 f"No asset ID in response. Got keys: {list(data.keys())}")
                return False, None
        else:
            print_test_result(4, "Data Source Creation (1GiB PVC via API)", False,
                             f"API returned {response.status_code}: {response.text}")
            return False, None
            
    except requests.exceptions.RequestException as e:
        print_test_result(4, "Data Source Creation (1GiB PVC via API)", False,
                         f"API request failed: {e}")
        return False, None


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
    """Test 5: Verify PVC is bound."""
    print_test_result(5, "PVC Status Verification (Bound)", None, "Checking...")
    
    if not pvc_name:
        print_test_result(5, "PVC Status Verification (Bound)", False,
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
                    print_test_result(5, "PVC Status Verification (Bound)", True,
                                    f"PVC '{pvc_name}' is Bound to PV '{volume_name}'")
                    return True, volume_name
                else:
                    if attempt < max_retries - 1:
                        print_info(f"PVC status: {phase}, waiting for Bound... (attempt {attempt+1}/{max_retries})")
                        time.sleep(retry_delay)
                    else:
                        print_test_result(5, "PVC Status Verification (Bound)", False,
                                        f"PVC is in '{phase}' state, not Bound")
                        return False, None
        
        if attempt < max_retries - 1:
            time.sleep(retry_delay)
    
    print_test_result(5, "PVC Status Verification (Bound)", False,
                     f"Failed to get PVC status after {max_retries} attempts")
    return False, None


def test_pv_association(pv_name):
    """Test 6: Verify PV exists and is bound."""
    print_test_result(6, "PV Association Verification", None, "Checking...")
    
    if not pv_name:
        print_test_result(6, "PV Association Verification", False,
                         "PV name not available")
        return False
    
    cmd = [
        "kubectl", "get", "pv", pv_name,
        "-o", "jsonpath={.status.phase}|{.spec.storageClassName}|{.spec.capacity.storage}"
    ]
    
    result = run_command(cmd)
    
    if not result or result.returncode != 0:
        print_test_result(6, "PV Association Verification", False,
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
            print_test_result(6, "PV Association Verification", True, details)
            return True
        else:
            print_test_result(6, "PV Association Verification", False,
                             f"{details}\n  • PV is in '{phase}' state, expected 'Bound'")
            return False
    else:
        print_test_result(6, "PV Association Verification", False,
                         f"Failed to parse PV information: {output}")
        return False


def test_delete_datasource(config, token, asset_id, datasource_name):
    """Test 7: Delete data source via API."""
    print_test_result(7, "Data Source Deletion (via API)", None, "Deleting...")
    
    url = f"{config['RUNAI_URL']}/api/v1/asset/datasource/pvc/{asset_id}"
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    print_info(f"Deleting data source: {datasource_name}")
    print_info(f"API: DELETE {url}")
    
    try:
        response = requests.delete(url, headers=headers, timeout=60, verify=True)
        
        if response.status_code in [200, 202, 204]:
            print_test_result(7, "Data Source Deletion (via API)", True,
                             f"Data source '{datasource_name}' deleted successfully (Asset ID: {asset_id})")
            return True
        else:
            print_test_result(7, "Data Source Deletion (via API)", False,
                             f"API returned {response.status_code}: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print_test_result(7, "Data Source Deletion (via API)", False,
                         f"API request failed: {e}")
        return False


def test_pvc_cleanup(project_name, pvc_name, max_retries=10, retry_delay=3):
    """Test 8: Verify PVC is removed."""
    print_test_result(8, "PVC Cleanup Verification", None, "Checking...")
    
    if not pvc_name:
        print_test_result(8, "PVC Cleanup Verification", False,
                         "PVC name not available")
        return False
    
    print_info(f"Waiting for PVC cleanup (max {max_retries * retry_delay}s)...")
    
    for attempt in range(max_retries):
        cmd = ["kubectl", "get", "pvc", pvc_name, "-n", f"runai-{project_name}"]
        result = run_command(cmd)
        
        if result and result.returncode != 0:
            # PVC not found - this is what we want
            print_test_result(8, "PVC Cleanup Verification", True,
                             f"PVC '{pvc_name}' successfully removed from cluster")
            return True
        
        if attempt < max_retries - 1:
            print_info(f"PVC still exists, waiting {retry_delay}s... (attempt {attempt+1}/{max_retries})")
            time.sleep(retry_delay)
    
    print_test_result(8, "PVC Cleanup Verification", False,
                     f"PVC '{pvc_name}' still exists after {max_retries * retry_delay}s")
    return False


def test_pv_cleanup(pv_name, max_retries=10, retry_delay=3):
    """Test 9: Verify PV is removed."""
    print_test_result(9, "PV Cleanup Verification", None, "Checking...")
    
    if not pv_name:
        print_test_result(9, "PV Cleanup Verification", False,
                         "PV name not available")
        return False
    
    print_info(f"Waiting for PV cleanup (max {max_retries * retry_delay}s)...")
    
    for attempt in range(max_retries):
        cmd = ["kubectl", "get", "pv", pv_name]
        result = run_command(cmd)
        
        if result and result.returncode != 0:
            # PV not found - this is what we want
            print_test_result(9, "PV Cleanup Verification", True,
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
    
    print_test_result(9, "PV Cleanup Verification", False,
                     f"PV '{pv_name}' still exists after {max_retries * retry_delay}s")
    return False


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description='Storage Health Check for Run:AI Environment',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Prerequisites:
    On first run, the script will create runai.env template.
    Edit it and provide:
        RUNAI_URL=https://your-runai-url
        RUNAI_CLIENT_ID=your-client-id
        RUNAI_CLIENT_SECRET=your-client-secret
    
    RUNAI_CLUSTER_ID will be auto-discovered from the API.

Example:
    python3 healthcheck_storage.py --project test
        """
    )
    parser.add_argument('--project', required=True, help='Run:AI project name')
    
    args = parser.parse_args()
    
    print_header("Storage Health Check - Run:AI Environment (API)")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Project: {args.project}")
    print()
    
    # Generate unique data source name
    datasource_name = generate_datasource_name()
    print_info(f"Test data source name: {datasource_name}")
    print()
    
    results = {}
    config = {}
    token = None
    project_id = None
    asset_id = None
    pvc_name = None
    pv_name = None
    
    # Run tests
    results['test1'], config = test_environment_config()
    if not results['test1']:
        print(f"\n{Colors.RED}Cannot proceed without proper environment configuration.{Colors.END}\n")
        return 1
    
    results['test2'], token = test_api_authentication(config)
    if not results['test2']:
        print(f"\n{Colors.RED}Cannot proceed without API authentication.{Colors.END}\n")
        return 1
    
    results['test3'], project_id = test_project_validation(config, token, args.project)
    if not results['test3']:
        print(f"\n{Colors.RED}Cannot proceed with invalid project.{Colors.END}\n")
        return 1
    
    results['test4'], asset_id = test_create_datasource(config, token, project_id, datasource_name)
    
    if results['test4'] and asset_id:
        # Give it a moment for PVC to be created
        time.sleep(2)
        pvc_name = get_pvc_name(args.project, datasource_name)
        
        if pvc_name:
            results['test5'], pv_name = test_pvc_status(args.project, pvc_name)
            results['test6'] = test_pv_association(pv_name)
        else:
            print_test_result(5, "PVC Status Verification (Bound)", False,
                             "Could not discover PVC name")
            results['test5'] = False
            results['test6'] = False
        
        # Always try to delete the data source
        results['test7'] = test_delete_datasource(config, token, asset_id, datasource_name)
        
        if results['test7']:
            # Give it a moment for cleanup to start
            time.sleep(2)
            results['test8'] = test_pvc_cleanup(args.project, pvc_name)
            results['test9'] = test_pv_cleanup(pv_name)
        else:
            print_warning(f"Deletion failed. Manual cleanup required:")
            print_warning(f"  DELETE {config['RUNAI_URL']}/api/v1/asset/datasource/pvc/{asset_id}")
            results['test8'] = False
            results['test9'] = False
    else:
        results['test5'] = False
        results['test6'] = False
        results['test7'] = False
        results['test8'] = False
        results['test9'] = False
    
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
        if not results.get('test7') and asset_id:
            print_warning("Manual cleanup may be required:")
            print_warning(f"  Asset ID: {asset_id}")
            print_warning(f"  Use Run:AI UI or API to delete the datasource")
            print()
        
        return 1


if __name__ == "__main__":
    sys.exit(main())
