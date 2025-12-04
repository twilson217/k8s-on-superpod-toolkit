#!/usr/bin/env python3
"""
Kubernetes Overview Script
Collects version information for Kubernetes components, Helm charts, and applications.
Supports --pre, --post, and --diff modes.
"""

import subprocess
import json
import re
import os
import argparse
from collections import defaultdict
from typing import Dict, List, Set, Tuple, Optional
from datetime import datetime


def run_command(cmd: str, shell: bool = True, check: bool = False) -> Tuple[str, str, int]:
    """
    Run a shell command and return stdout, stderr, and return code.
    """
    try:
        result = subprocess.run(
            cmd,
            shell=shell,
            capture_output=True,
            text=True,
            check=check
        )
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except subprocess.CalledProcessError as e:
        return e.stdout.strip() if e.stdout else "", e.stderr.strip() if e.stderr else "", e.returncode
    except Exception as e:
        return "", str(e), 1


def get_helm_releases() -> Dict[str, Dict[str, str]]:
    """
    Get all Helm releases with their chart version and app version.
    Returns: {release_name: {namespace, chart_version, app_version}}
    """
    helm_releases = {}
    
    # Get list of all Helm releases across all namespaces
    stdout, stderr, rc = run_command("helm list --all-namespaces -o json")
    
    if rc != 0 or not stdout:
        print(f"Warning: Could not get Helm releases: {stderr}")
        return helm_releases
    
    try:
        releases = json.loads(stdout)
        for release in releases:
            name = release.get('name', '')
            namespace = release.get('namespace', '')
            chart = release.get('chart', '')
            app_version = release.get('app_version', 'N/A')
            
            # Extract chart name and version from chart field (format: "chart-name-version")
            chart_version = 'N/A'
            if chart:
                # Try to extract version from the end of the chart string
                parts = chart.rsplit('-', 1)
                if len(parts) == 2:
                    chart_version = parts[1]
            
            helm_releases[f"{namespace}/{name}"] = {
                'namespace': namespace,
                'name': name,
                'chart': chart,
                'chart_version': chart_version,
                'app_version': app_version
            }
    except json.JSONDecodeError as e:
        print(f"Warning: Could not parse Helm output: {e}")
    
    return helm_releases


def get_k8s_workloads() -> Dict[str, Dict[str, any]]:
    """
    Get all Kubernetes workloads (Deployments, StatefulSets, DaemonSets) with their images.
    Returns: {namespace/name: {type, namespace, name, images}}
    """
    workloads = {}
    
    # Resource types to check
    resource_types = ['deployments', 'statefulsets', 'daemonsets']
    
    for resource_type in resource_types:
        stdout, stderr, rc = run_command(
            f"kubectl get {resource_type} --all-namespaces -o json"
        )
        
        if rc != 0:
            print(f"Warning: Could not get {resource_type}: {stderr}")
            continue
        
        try:
            data = json.loads(stdout)
            items = data.get('items', [])
            
            for item in items:
                metadata = item.get('metadata', {})
                name = metadata.get('name', '')
                namespace = metadata.get('namespace', '')
                labels = metadata.get('labels', {})
                
                # Extract images from containers
                spec = item.get('spec', {})
                template = spec.get('template', {})
                pod_spec = template.get('spec', {})
                containers = pod_spec.get('containers', [])
                
                images = []
                for container in containers:
                    image = container.get('image', '')
                    if image:
                        images.append(image)
                
                if images:
                    key = f"{namespace}/{name}"
                    workloads[key] = {
                        'type': resource_type.rstrip('s').capitalize(),
                        'namespace': namespace,
                        'name': name,
                        'images': images,
                        'labels': labels
                    }
        except json.JSONDecodeError as e:
            print(f"Warning: Could not parse {resource_type} output: {e}")
    
    return workloads


def extract_version_from_image(image: str) -> str:
    """
    Extract version from a container image string.
    Example: "nginx:1.21.0" -> "1.21.0"
    """
    # Handle image format: [registry/]repository[:tag][@digest]
    if '@' in image:
        # Remove digest part
        image = image.split('@')[0]
    
    if ':' in image:
        version = image.split(':')[-1]
        # Filter out 'latest' as it's not informative
        if version.lower() != 'latest':
            return version
    
    return 'latest'


def is_helm_managed(workload_key: str, workload_data: Dict, helm_releases: Dict) -> Optional[str]:
    """
    Check if a workload is managed by Helm.
    Returns the Helm release key if managed, None otherwise.
    """
    namespace = workload_data['namespace']
    labels = workload_data.get('labels', {})
    
    # Check for Helm labels
    helm_release_name = labels.get('app.kubernetes.io/managed-by')
    if helm_release_name and helm_release_name.lower() == 'helm':
        # Try to find the release name
        release_name = labels.get('app.kubernetes.io/instance') or labels.get('release')
        if release_name:
            helm_key = f"{namespace}/{release_name}"
            if helm_key in helm_releases:
                return helm_key
    
    # Fallback: check if workload name matches any Helm release name
    for helm_key, helm_data in helm_releases.items():
        if helm_data['namespace'] == namespace:
            # Check if workload name starts with release name
            if workload_data['name'].startswith(helm_data['name']):
                return helm_key
    
    return None


def get_kubernetes_component_versions() -> Dict[str, str]:
    """
    Get versions of Kubernetes components.
    """
    versions = {}
    
    # Get kubectl version
    stdout, stderr, rc = run_command("kubectl version --client=true -o json")
    if rc == 0 and stdout:
        try:
            data = json.loads(stdout)
            client_version = data.get('clientVersion', {})
            git_version = client_version.get('gitVersion', 'N/A')
            versions['kubectl'] = git_version
        except:
            pass
    
    # Get Kubernetes server version
    stdout, stderr, rc = run_command("kubectl version -o json")
    if rc == 0 and stdout:
        try:
            data = json.loads(stdout)
            server_version = data.get('serverVersion', {})
            git_version = server_version.get('gitVersion', 'N/A')
            versions['kubernetes-server'] = git_version
        except:
            pass
    
    # Get kubeadm version
    stdout, stderr, rc = run_command("kubeadm version -o short")
    if rc == 0 and stdout:
        versions['kubeadm'] = stdout
    
    # Get kubelet version
    stdout, stderr, rc = run_command("kubelet --version")
    if rc == 0 and stdout:
        # Output format: "Kubernetes v1.x.x"
        match = re.search(r'v[\d.]+', stdout)
        if match:
            versions['kubelet'] = match.group(0)
    
    # Get containerd version
    stdout, stderr, rc = run_command("containerd --version")
    if rc == 0 and stdout:
        # Output format: "containerd containerd.io 1.x.x ..."
        parts = stdout.split()
        if len(parts) >= 3:
            versions['containerd'] = parts[2]
    
    # Try to get docker version if available
    stdout, stderr, rc = run_command("docker --version")
    if rc == 0 and stdout:
        match = re.search(r'[\d.]+', stdout)
        if match:
            versions['docker'] = match.group(0)
    
    # Get CNI version if possible
    stdout, stderr, rc = run_command("kubectl get pods -n kube-system -o json")
    if rc == 0 and stdout:
        try:
            data = json.loads(stdout)
            items = data.get('items', [])
            for item in items:
                name = item.get('metadata', {}).get('name', '')
                if 'calico' in name.lower():
                    containers = item.get('spec', {}).get('containers', [])
                    for container in containers:
                        image = container.get('image', '')
                        if 'calico' in image:
                            version = extract_version_from_image(image)
                            versions['calico-cni'] = version
                            break
                elif 'flannel' in name.lower():
                    containers = item.get('spec', {}).get('containers', [])
                    for container in containers:
                        image = container.get('image', '')
                        if 'flannel' in image:
                            version = extract_version_from_image(image)
                            versions['flannel-cni'] = version
                            break
        except:
            pass
    
    return versions


def get_etcd_nodes() -> List[str]:
    """
    Find etcd nodes using cmsh commands.
    """
    etcd_nodes = []
    
    # Get configuration overlay list
    stdout, stderr, rc = run_command('cmsh -c "configurationoverlay;list"')
    
    if rc != 0:
        print(f"Warning: Could not get configuration overlay list: {stderr}")
        return etcd_nodes
    
    # Parse the output to find the Etcd::Host role
    lines = stdout.split('\n')
    etcd_line = None
    
    for line in lines:
        if 'Etcd::Host' in line:
            etcd_line = line
            break
    
    if not etcd_line:
        print("Warning: Could not find Etcd::Host role in configuration overlay")
        return etcd_nodes
    
    # Parse the line to extract nodes
    # The format is space-separated: Name Priority AllHeadNodes Nodes Categories Roles
    # Example: kube-runai-etcd    500        no             node001                            Etcd::Host
    parts = etcd_line.split()
    
    # Find the index where "Etcd::Host" appears
    try:
        etcd_index = parts.index('Etcd::Host')
    except ValueError:
        print("Warning: Could not parse Etcd::Host line")
        return etcd_nodes
    
    # The nodes should be before the roles section
    # Format: Name(0) Priority(1) AllHeadNodes(2) Nodes(3) [Categories...] Roles
    # We need to extract the nodes field which is typically at index 3
    if len(parts) >= 4:
        # The nodes field is at index 3
        nodes_field = parts[3]
        
        # Handle node ranges like "node001..node007" or single nodes like "node001"
        if '..' in nodes_field:
            # Parse node range
            match = re.match(r'(\w+?)(\d+)\.\.(\w+?)(\d+)', nodes_field)
            if match:
                prefix1, start, prefix2, end = match.groups()
                if prefix1 == prefix2:
                    start_num = int(start)
                    end_num = int(end)
                    for i in range(start_num, end_num + 1):
                        node_name = f"{prefix1}{i:0{len(start)}d}"
                        etcd_nodes.append(node_name)
            else:
                # Couldn't parse range, add as-is
                etcd_nodes.append(nodes_field)
        elif ',' in nodes_field:
            # Comma-separated nodes
            static_nodes = [n.strip() for n in nodes_field.split(',') if n.strip()]
            etcd_nodes.extend(static_nodes)
        else:
            # Single node
            etcd_nodes.append(nodes_field)
    
    # Also check for categories if present (between nodes and roles)
    # Categories would be at index 4 onwards until we hit the roles
    if len(parts) > 4 and etcd_index > 4:
        # There might be categories between nodes and roles
        categories_part = parts[4:etcd_index]
        if categories_part:
            categories_str = ' '.join(categories_part)
            # Split by comma if there are multiple categories
            categories = [c.strip() for c in categories_str.split(',') if c.strip()]
            
            for category in categories:
                stdout, stderr, rc = run_command(f'cmsh -c "device list" | grep {category}')
                if rc == 0 and stdout:
                    # Parse device list output
                    for line in stdout.split('\n'):
                        if line.strip():
                            # Extract node name (typically first field)
                            node_name = line.split()[0]
                            if node_name and node_name not in etcd_nodes:
                                etcd_nodes.append(node_name)
    
    return etcd_nodes


def get_etcd_version() -> str:
    """
    Get etcd version by SSHing to an etcd node.
    """
    etcd_nodes = get_etcd_nodes()
    
    if not etcd_nodes:
        print("Warning: No etcd nodes found")
        return "N/A"
    
    # Try the first etcd node
    node = etcd_nodes[0]
    print(f"Checking etcd version on node: {node}")
    
    stdout, stderr, rc = run_command(
        f'ssh -o StrictHostKeyChecking=no {node} "/cm/local/apps/etcd/current/bin/etcd --version"'
    )
    
    if rc != 0:
        print(f"Warning: Could not get etcd version from {node}: {stderr}")
        # Try alternative path
        stdout, stderr, rc = run_command(
            f'ssh -o StrictHostKeyChecking=no {node} "etcd --version"'
        )
    
    if rc == 0 and stdout:
        # Parse etcd version output
        # Format: "etcd Version: 3.x.x" or similar
        match = re.search(r'[\d.]+', stdout)
        if match:
            return match.group(0)
    
    return "N/A"


def collect_data() -> Dict:
    """
    Collect all version data.
    """
    print("\n1. Collecting Helm releases...")
    helm_releases = get_helm_releases()
    print(f"   Found {len(helm_releases)} Helm releases")
    
    print("\n2. Collecting Kubernetes workloads...")
    workloads = get_k8s_workloads()
    print(f"   Found {len(workloads)} workloads")
    
    print("\n3. Collecting Kubernetes component versions...")
    k8s_versions = get_kubernetes_component_versions()
    print(f"   Found {len(k8s_versions)} component versions")
    
    print("\n4. Collecting etcd version...")
    etcd_version = get_etcd_version()
    print(f"   etcd version: {etcd_version}")
    
    return {
        'helm_releases': helm_releases,
        'workloads': workloads,
        'k8s_versions': k8s_versions,
        'etcd_version': etcd_version,
        'timestamp': datetime.now().isoformat()
    }


def generate_markdown_report(data: Dict, output_file: str, title: str):
    """
    Generate a markdown report with all version information.
    """
    helm_releases = data['helm_releases']
    workloads = data['workloads']
    k8s_versions = data['k8s_versions']
    etcd_version = data['etcd_version']
    
    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    with open(output_file, 'w') as f:
        f.write(f"# {title}\n\n")
        f.write("This document contains version information for Kubernetes components and applications.\n\n")
        f.write(f"**Generated:** {data.get('timestamp', 'N/A')}\n\n")
        
        # Kubernetes Components Section
        f.write("## Kubernetes Components\n\n")
        f.write("| Component | Version |\n")
        f.write("|-----------|----------|\n")
        
        # Add etcd first
        f.write(f"| etcd | {etcd_version} |\n")
        
        # Add other components
        for component, version in sorted(k8s_versions.items()):
            f.write(f"| {component} | {version} |\n")
        
        f.write("\n")
        
        # Applications Section
        f.write("## Applications\n\n")
        
        # Combine Helm releases and non-Helm workloads
        all_apps = {}
        helm_managed_workloads = set()
        
        # Add Helm releases
        for helm_key, helm_data in helm_releases.items():
            app_name = f"{helm_data['namespace']}/{helm_data['name']}"
            all_apps[app_name] = {
                'namespace': helm_data['namespace'],
                'name': helm_data['name'],
                'source': 'Helm',
                'chart_version': helm_data['chart_version'],
                'app_version': helm_data['app_version'],
                'images': []
            }
        
        # Add non-Helm workloads
        for workload_key, workload_data in workloads.items():
            helm_key = is_helm_managed(workload_key, workload_data, helm_releases)
            
            if helm_key:
                # This workload is managed by Helm, skip it
                helm_managed_workloads.add(workload_key)
            else:
                # This is a standalone workload
                app_name = workload_key
                images = workload_data.get('images', [])
                image_versions = [extract_version_from_image(img) for img in images]
                
                all_apps[app_name] = {
                    'namespace': workload_data['namespace'],
                    'name': workload_data['name'],
                    'source': 'Kubernetes',
                    'type': workload_data['type'],
                    'images': images,
                    'image_versions': image_versions
                }
        
        # Write applications table
        f.write("| Namespace | Application | Source | Chart Version | App Version | Image Version(s) |\n")
        f.write("|-----------|-------------|--------|---------------|-------------|------------------|\n")
        
        for app_key in sorted(all_apps.keys()):
            app = all_apps[app_key]
            namespace = app['namespace']
            name = app['name']
            source = app['source']
            
            if source == 'Helm':
                chart_version = app['chart_version']
                app_version = app['app_version']
                image_versions = '-'
            else:
                chart_version = '-'
                app_version = '-'
                image_versions = ', '.join(app.get('image_versions', []))
                if not image_versions:
                    image_versions = '-'
            
            f.write(f"| {namespace} | {name} | {source} | {chart_version} | {app_version} | {image_versions} |\n")
        
        f.write("\n")
        
        # Summary
        f.write("## Summary\n\n")
        f.write(f"- **Total Kubernetes Components**: {len(k8s_versions) + 1}\n")  # +1 for etcd
        f.write(f"- **Total Helm Releases**: {len(helm_releases)}\n")
        f.write(f"- **Total Kubernetes Workloads (non-Helm)**: {len(all_apps) - len(helm_releases)}\n")
        f.write(f"- **Total Applications**: {len(all_apps)}\n")
    
    print(f"\nReport generated: {output_file}")


def load_data_from_file(filename: str) -> Optional[Dict]:
    """
    Load previously collected data from a JSON file.
    """
    if not os.path.exists(filename):
        return None
    
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading data from {filename}: {e}")
        return None


def save_data_to_file(data: Dict, filename: str):
    """
    Save collected data to a JSON file.
    """
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"Data saved to: {filename}")


def generate_simplified_summary(pre_data: Dict, post_data: Dict, output_file: str):
    """
    Generate a simplified summary report for easy copy-paste to emails.
    Consolidates multiple components into single application rows.
    """
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    # Helper function to consolidate apps by namespace/helm release
    def consolidate_apps(data):
        """Consolidate workloads into main applications (Helm releases or namespace groups)"""
        helm_releases = data['helm_releases']
        workloads = data['workloads']
        
        consolidated = {}
        
        # Add all Helm releases as primary applications
        for helm_key, helm_data in helm_releases.items():
            key = f"{helm_data['namespace']}/{helm_data['name']}"
            consolidated[key] = {
                'namespace': helm_data['namespace'],
                'name': helm_data['name'],
                'source': 'Helm',
                'chart_version': helm_data['chart_version'],
                'app_version': helm_data['app_version'],
                'is_helm': True
            }
        
        # Add standalone workloads (not managed by Helm)
        for workload_key, workload_data in workloads.items():
            helm_key = is_helm_managed(workload_key, workload_data, helm_releases)
            if not helm_key:
                namespace = workload_data['namespace']
                name = workload_data['name']
                
                # Check if this is part of a known multi-component system
                # Group by namespace for certain known systems
                parent_key = None
                
                # Don't create duplicate entries for workloads that are clearly sub-components
                # These namespaces typically have ONE main component, skip individual workloads
                skip_namespaces = {'runai', 'runai-backend', 'gpu-operator', 'network-operator', 'prometheus'}
                
                if namespace in skip_namespaces:
                    # Skip individual workloads, we'll only show the main Helm release
                    continue
                
                # For user workload namespaces or standalone apps, add them
                images = workload_data.get('images', [])
                image_versions = [extract_version_from_image(img) for img in images]
                
                key = f"{namespace}/{name}"
                consolidated[key] = {
                    'namespace': namespace,
                    'name': name,
                    'source': 'Kubernetes',
                    'image_versions': ', '.join(image_versions) if image_versions else 'N/A',
                    'is_helm': False
                }
        
        return consolidated
    
    pre_apps = consolidate_apps(pre_data)
    post_apps = consolidate_apps(post_data)
    all_apps = set(pre_apps.keys()) | set(post_apps.keys())
    
    with open(output_file, 'w') as f:
        f.write("# Upgrade Summary (Simplified)\n\n")
        f.write("This summary consolidates components for easy copy-paste to emails.\n\n")
        f.write(f"**Pre-upgrade:** {pre_data.get('timestamp', 'N/A')}\n\n")
        f.write(f"**Post-upgrade:** {post_data.get('timestamp', 'N/A')}\n\n")
        
        # Kubernetes Components
        f.write("## Kubernetes Components\n\n")
        f.write("| Component | Pre-Upgrade | Post-Upgrade | Status |\n")
        f.write("|-----------|-------------|--------------|--------|\n")
        
        pre_k8s = pre_data['k8s_versions']
        post_k8s = post_data['k8s_versions']
        pre_etcd = pre_data['etcd_version']
        post_etcd = post_data['etcd_version']
        
        # etcd
        if pre_etcd != post_etcd:
            f.write(f"| etcd | {pre_etcd} | {post_etcd} | ✅ Upgraded |\n")
        else:
            f.write(f"| etcd | {pre_etcd} | {post_etcd} | No change |\n")
        
        # Other K8s components
        all_components = set(pre_k8s.keys()) | set(post_k8s.keys())
        for component in sorted(all_components):
            pre_ver = pre_k8s.get(component, 'N/A')
            post_ver = post_k8s.get(component, 'N/A')
            
            if pre_ver == 'N/A' and post_ver != 'N/A':
                status = "🆕 Added"
            elif pre_ver != 'N/A' and post_ver == 'N/A':
                status = "❌ Removed"
            elif pre_ver != post_ver:
                status = "✅ Upgraded"
            else:
                status = "No change"
            
            f.write(f"| {component} | {pre_ver} | {post_ver} | {status} |\n")
        
        f.write("\n")
        
        # Applications (consolidated)
        f.write("## Applications\n\n")
        f.write("| Namespace | Application | Pre-Upgrade | Post-Upgrade | Status |\n")
        f.write("|-----------|-------------|-------------|--------------|--------|\n")
        
        # Count changes for summary
        k8s_changed = 0
        apps_upgraded = 0
        apps_added = 0
        apps_removed = 0
        apps_unchanged = 0
        
        # K8s component changes
        components_changed = sum(1 for c in all_components if pre_k8s.get(c) != post_k8s.get(c))
        if pre_etcd != post_etcd:
            components_changed += 1
        k8s_changed = components_changed
        
        # Process apps
        for app_key in sorted(all_apps):
            pre_app = pre_apps.get(app_key)
            post_app = post_apps.get(app_key)
            
            if pre_app and post_app:
                namespace = pre_app['namespace']
                name = pre_app['name']
                
                if pre_app.get('is_helm'):
                    pre_ver = pre_app['chart_version']
                    post_ver = post_app['chart_version']
                    
                    if pre_app['chart_version'] != post_app['chart_version']:
                        status = "✅ Upgraded"
                        apps_upgraded += 1
                    else:
                        status = "No change"
                        apps_unchanged += 1
                else:
                    pre_ver = pre_app.get('image_versions', 'N/A')
                    post_ver = post_app.get('image_versions', 'N/A')
                    
                    if pre_ver != post_ver:
                        status = "✅ Upgraded"
                        apps_upgraded += 1
                    else:
                        status = "No change"
                        apps_unchanged += 1
                
                f.write(f"| {namespace} | {name} | {pre_ver} | {post_ver} | {status} |\n")
            
            elif pre_app and not post_app:
                namespace = pre_app['namespace']
                name = pre_app['name']
                
                if pre_app.get('is_helm'):
                    pre_ver = pre_app['chart_version']
                else:
                    pre_ver = pre_app.get('image_versions', 'N/A')
                
                f.write(f"| {namespace} | {name} | {pre_ver} | - | ❌ Removed |\n")
                apps_removed += 1
            
            elif not pre_app and post_app:
                namespace = post_app['namespace']
                name = post_app['name']
                
                if post_app.get('is_helm'):
                    post_ver = post_app['chart_version']
                else:
                    post_ver = post_app.get('image_versions', 'N/A')
                
                f.write(f"| {namespace} | {name} | - | {post_ver} | 🆕 Added |\n")
                apps_added += 1
        
        f.write("\n")
        
        # Summary
        f.write("## Summary\n\n")
        f.write(f"- **Kubernetes Components Changed:** {k8s_changed}\n")
        f.write(f"- **Applications Upgraded:** {apps_upgraded}\n")
        f.write(f"- **Applications Added:** {apps_added}\n")
        f.write(f"- **Applications Removed:** {apps_removed}\n")
        f.write(f"- **Applications Unchanged:** {apps_unchanged}\n")
    
    print(f"\nSimplified summary generated: {output_file}")


def generate_diff_report(pre_data: Dict, post_data: Dict, output_file: str):
    """
    Generate a diff report comparing pre and post upgrade data.
    """
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    with open(output_file, 'w') as f:
        f.write("# Upgrade Diff Overview\n\n")
        f.write("This document shows the differences between pre-upgrade and post-upgrade states.\n\n")
        f.write(f"**Pre-upgrade timestamp:** {pre_data.get('timestamp', 'N/A')}\n\n")
        f.write(f"**Post-upgrade timestamp:** {post_data.get('timestamp', 'N/A')}\n\n")
        
        # Kubernetes Components Diff
        f.write("## Kubernetes Components Changes\n\n")
        f.write("| Component | Pre-Upgrade | Post-Upgrade | Status |\n")
        f.write("|-----------|-------------|--------------|--------|\n")
        
        pre_k8s = pre_data['k8s_versions']
        post_k8s = post_data['k8s_versions']
        pre_etcd = pre_data['etcd_version']
        post_etcd = post_data['etcd_version']
        
        # etcd
        if pre_etcd != post_etcd:
            f.write(f"| etcd | {pre_etcd} | {post_etcd} | ✅ **UPGRADED** |\n")
        else:
            f.write(f"| etcd | {pre_etcd} | {post_etcd} | ➖ No change |\n")
        
        # Other components
        all_components = set(pre_k8s.keys()) | set(post_k8s.keys())
        for component in sorted(all_components):
            pre_ver = pre_k8s.get(component, 'N/A')
            post_ver = post_k8s.get(component, 'N/A')
            
            if pre_ver == 'N/A' and post_ver != 'N/A':
                status = "🆕 **ADDED**"
            elif pre_ver != 'N/A' and post_ver == 'N/A':
                status = "❌ **REMOVED**"
            elif pre_ver != post_ver:
                status = "✅ **UPGRADED**"
            else:
                status = "➖ No change"
            
            f.write(f"| {component} | {pre_ver} | {post_ver} | {status} |\n")
        
        f.write("\n")
        
        # Applications Diff
        f.write("## Application Changes\n\n")
        
        # Build app dictionaries for both pre and post
        def build_app_dict(data):
            apps = {}
            helm_releases = data['helm_releases']
            workloads = data['workloads']
            
            # Add Helm releases
            for helm_key, helm_data in helm_releases.items():
                app_name = f"{helm_data['namespace']}/{helm_data['name']}"
                apps[app_name] = {
                    'namespace': helm_data['namespace'],
                    'name': helm_data['name'],
                    'source': 'Helm',
                    'chart_version': helm_data['chart_version'],
                    'app_version': helm_data['app_version']
                }
            
            # Add non-Helm workloads
            for workload_key, workload_data in workloads.items():
                helm_key = is_helm_managed(workload_key, workload_data, helm_releases)
                if not helm_key:
                    images = workload_data.get('images', [])
                    image_versions = [extract_version_from_image(img) for img in images]
                    apps[workload_key] = {
                        'namespace': workload_data['namespace'],
                        'name': workload_data['name'],
                        'source': 'Kubernetes',
                        'image_versions': ', '.join(image_versions) if image_versions else 'N/A'
                    }
            
            return apps
        
        pre_apps = build_app_dict(pre_data)
        post_apps = build_app_dict(post_data)
        
        all_apps = set(pre_apps.keys()) | set(post_apps.keys())
        
        f.write("| Namespace | Application | Source | Pre-Upgrade Version | Post-Upgrade Version | Status |\n")
        f.write("|-----------|-------------|--------|---------------------|----------------------|--------|\n")
        
        for app_key in sorted(all_apps):
            pre_app = pre_apps.get(app_key)
            post_app = post_apps.get(app_key)
            
            if pre_app and post_app:
                namespace = pre_app['namespace']
                name = pre_app['name']
                source = pre_app['source']
                
                if source == 'Helm':
                    pre_ver = f"Chart: {pre_app['chart_version']}, App: {pre_app['app_version']}"
                    post_ver = f"Chart: {post_app['chart_version']}, App: {post_app['app_version']}"
                    
                    if pre_app['chart_version'] != post_app['chart_version'] or pre_app['app_version'] != post_app['app_version']:
                        status = "✅ **UPGRADED**"
                    else:
                        status = "➖ No change"
                else:
                    pre_ver = pre_app.get('image_versions', 'N/A')
                    post_ver = post_app.get('image_versions', 'N/A')
                    
                    if pre_ver != post_ver:
                        status = "✅ **UPGRADED**"
                    else:
                        status = "➖ No change"
                
                f.write(f"| {namespace} | {name} | {source} | {pre_ver} | {post_ver} | {status} |\n")
            
            elif pre_app and not post_app:
                namespace = pre_app['namespace']
                name = pre_app['name']
                source = pre_app['source']
                
                if source == 'Helm':
                    pre_ver = f"Chart: {pre_app['chart_version']}, App: {pre_app['app_version']}"
                else:
                    pre_ver = pre_app.get('image_versions', 'N/A')
                
                f.write(f"| {namespace} | {name} | {source} | {pre_ver} | - | ❌ **REMOVED** |\n")
            
            elif not pre_app and post_app:
                namespace = post_app['namespace']
                name = post_app['name']
                source = post_app['source']
                
                if source == 'Helm':
                    post_ver = f"Chart: {post_app['chart_version']}, App: {post_app['app_version']}"
                else:
                    post_ver = post_app.get('image_versions', 'N/A')
                
                f.write(f"| {namespace} | {name} | {source} | - | {post_ver} | 🆕 **ADDED** |\n")
        
        f.write("\n")
        
        # Summary
        f.write("## Summary\n\n")
        
        # Count changes
        components_changed = sum(1 for c in all_components if pre_k8s.get(c) != post_k8s.get(c))
        if pre_etcd != post_etcd:
            components_changed += 1
        
        apps_changed = 0
        apps_added = 0
        apps_removed = 0
        
        for app_key in all_apps:
            pre_app = pre_apps.get(app_key)
            post_app = post_apps.get(app_key)
            
            if pre_app and post_app:
                if pre_app.get('chart_version') != post_app.get('chart_version') or \
                   pre_app.get('app_version') != post_app.get('app_version') or \
                   pre_app.get('image_versions') != post_app.get('image_versions'):
                    apps_changed += 1
            elif not pre_app:
                apps_added += 1
            elif not post_app:
                apps_removed += 1
        
        f.write(f"- **Kubernetes Components Changed**: {components_changed}\n")
        f.write(f"- **Applications Upgraded**: {apps_changed}\n")
        f.write(f"- **Applications Added**: {apps_added}\n")
        f.write(f"- **Applications Removed**: {apps_removed}\n")
    
    print(f"\nDiff report generated: {output_file}")


def main():
    """
    Main function to orchestrate the version collection and report generation.
    """
    parser = argparse.ArgumentParser(
        description='Kubernetes Overview Script - Collect version information for K8s components and applications'
    )
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--pre', action='store_true', help='Collect pre-upgrade snapshot')
    group.add_argument('--post', action='store_true', help='Collect post-upgrade snapshot')
    group.add_argument('--diff', action='store_true', help='Generate diff report comparing pre and post snapshots')
    group.add_argument('--summary', action='store_true', help='Generate simplified summary (consolidates multi-component apps)')
    
    args = parser.parse_args()
    
    logs_dir = ".logs"
    
    if args.pre:
        print("Kubernetes Overview Script - Pre-Upgrade Mode")
        print("=" * 50)
        
        data = collect_data()
        
        print("\n5. Saving data...")
        save_data_to_file(data, f"{logs_dir}/pre-upgrade-overview.json")
        
        print("\n6. Generating report...")
        generate_markdown_report(data, f"{logs_dir}/pre-upgrade-overview.md", "Pre-Upgrade Overview")
        
        print("\n" + "=" * 50)
        print("Done!")
    
    elif args.post:
        print("Kubernetes Overview Script - Post-Upgrade Mode")
        print("=" * 50)
        
        data = collect_data()
        
        print("\n5. Saving data...")
        save_data_to_file(data, f"{logs_dir}/post-upgrade-overview.json")
        
        print("\n6. Generating report...")
        generate_markdown_report(data, f"{logs_dir}/post-upgrade-overview.md", "Post-Upgrade Overview")
        
        print("\n" + "=" * 50)
        print("Done!")
    
    elif args.diff:
        print("Kubernetes Overview Script - Diff Mode")
        print("=" * 50)
        
        print("\nLoading pre-upgrade data...")
        pre_data = load_data_from_file(f"{logs_dir}/pre-upgrade-overview.json")
        
        if not pre_data:
            print("Error: Pre-upgrade data not found. Please run with --pre first.")
            return 1
        
        print("Loading post-upgrade data...")
        post_data = load_data_from_file(f"{logs_dir}/post-upgrade-overview.json")
        
        if not post_data:
            print("Error: Post-upgrade data not found. Please run with --post first.")
            return 1
        
        print("\nGenerating diff report...")
        generate_diff_report(pre_data, post_data, f"{logs_dir}/diff-overview.md")
        
        print("\n" + "=" * 50)
        print("Done!")
    
    elif args.summary:
        print("Kubernetes Overview Script - Summary Mode (Simplified)")
        print("=" * 50)
        
        print("\nLoading pre-upgrade data...")
        pre_data = load_data_from_file(f"{logs_dir}/pre-upgrade-overview.json")
        
        if not pre_data:
            print("Error: Pre-upgrade data not found. Please run with --pre first.")
            return 1
        
        print("Loading post-upgrade data...")
        post_data = load_data_from_file(f"{logs_dir}/post-upgrade-overview.json")
        
        if not post_data:
            print("Error: Post-upgrade data not found. Please run with --post first.")
            return 1
        
        print("\nGenerating simplified summary...")
        generate_simplified_summary(pre_data, post_data, f"{logs_dir}/summary-overview.md")
        
        print("\n" + "=" * 50)
        print("Done!")
    
    return 0


if __name__ == "__main__":
    exit(main())
