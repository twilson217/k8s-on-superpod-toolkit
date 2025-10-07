#!/usr/bin/env python3

"""
Kubernetes & RunAI Environment Discovery Script
Purpose: Complete pre-upgrade snapshot of the environment
Output: pre-upgrade-snapshot.md (Markdown format with TOC)
"""

import subprocess
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Optional

# Configuration
LOGS_DIR = ".logs"
OUTPUT_FILE = f"{LOGS_DIR}/pre-upgrade-snapshot.md"


class EnvironmentDiscovery:
    def __init__(self):
        self.output_lines = []
        self.toc_entries = []
        self.section_counter = 0
        
    def run_command(self, cmd: List[str], description: str = "") -> Tuple[bool, str, str]:
        """Run a command and return success status, stdout, and stderr."""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )
            return result.returncode == 0, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return False, "", "Command timed out"
        except Exception as e:
            return False, "", str(e)
    
    def add_toc_entry(self, title: str, level: int = 1):
        """Add an entry to the table of contents."""
        self.section_counter += 1
        anchor = title.lower().replace(" ", "-").replace("(", "").replace(")", "").replace("/", "-")
        self.toc_entries.append((level, title, anchor, self.section_counter))
        return anchor
    
    def add_section(self, title: str, level: int = 1):
        """Add a section header to the output."""
        anchor = self.add_toc_entry(title, level)
        self.output_lines.append("")
        if level == 1:
            self.output_lines.append(f"# {title}")
        elif level == 2:
            self.output_lines.append(f"## {title}")
        elif level == 3:
            self.output_lines.append(f"### {title}")
        else:
            self.output_lines.append(f"{'#' * level} {title}")
        self.output_lines.append("")
    
    def add_text(self, text: str):
        """Add plain text to the output."""
        self.output_lines.append(text)
    
    def add_code_block(self, content: str, language: str = ""):
        """Add a code block to the output."""
        self.output_lines.append(f"```{language}")
        self.output_lines.append(content.rstrip())
        self.output_lines.append("```")
        self.output_lines.append("")
    
    def capture_output(self, description: str, cmd: List[str], language: str = ""):
        """Run a command and capture its output in a code block."""
        print(f"Collecting: {description}")
        self.add_section(description, level=3)
        
        success, stdout, stderr = self.run_command(cmd)
        
        if success and stdout.strip():
            self.add_code_block(stdout, language)
        elif stderr.strip():
            self.add_text(f"⚠️ **Error:** {stderr.strip()}")
            self.add_text("")
        else:
            self.add_text("_No output or resource not found_")
            self.add_text("")
    
    def generate_toc(self) -> List[str]:
        """Generate the table of contents."""
        toc = ["# Table of Contents", ""]
        
        for level, title, anchor, section_num in self.toc_entries:
            indent = "  " * (level - 1)
            toc.append(f"{indent}- [{title}](#{anchor})")
        
        toc.append("")
        toc.append("---")
        toc.append("")
        return toc
    
    def save_output(self):
        """Save the output to a file."""
        # Create logs directory
        Path(LOGS_DIR).mkdir(exist_ok=True)
        
        # Generate TOC and prepend to output
        toc = self.generate_toc()
        full_output = toc + self.output_lines
        
        with open(OUTPUT_FILE, 'w') as f:
            f.write('\n'.join(full_output))
        
        print(f"\n{'='*80}")
        print("Discovery Complete!")
        print(f"{'='*80}\n")
        print(f"Output file: {OUTPUT_FILE}")
        
        # Get file size
        file_size = os.path.getsize(OUTPUT_FILE)
        if file_size < 1024:
            size_str = f"{file_size} bytes"
        elif file_size < 1024 * 1024:
            size_str = f"{file_size / 1024:.2f} KB"
        else:
            size_str = f"{file_size / (1024 * 1024):.2f} MB"
        
        print(f"File size: {size_str}")
        print(f"\nSummary:")
        print(f"  - Kubernetes cluster information captured")
        print(f"  - Helm releases documented")
        print(f"  - All resources across all namespaces recorded")
        print(f"  - RunAI specific configurations extracted")
        print(f"  - System and hardware information included")
        print(f"\nThis snapshot can be used for:")
        print(f"  - Pre-upgrade documentation")
        print(f"  - Disaster recovery planning")
        print(f"  - Configuration auditing")
        print(f"  - Troubleshooting reference")
        print(f"\n{'='*80}\n")
    
    def discover(self):
        """Main discovery process."""
        print("Starting environment discovery...")
        print(f"Output will be written to: {OUTPUT_FILE}\n")
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')
        hostname = subprocess.run(['hostname'], capture_output=True, text=True).stdout.strip()
        username = subprocess.run(['whoami'], capture_output=True, text=True).stdout.strip()
        
        # Header
        self.add_section("Environment Discovery Report", level=1)
        self.add_text(f"**Generated:** {timestamp}")
        self.add_text(f"**Hostname:** {hostname}")
        self.add_text(f"**User:** {username}")
        self.add_text("")
        
        # System Information
        self.add_section("System Information", level=2)
        self.collect_system_info()
        
        # Kubernetes Cluster Information
        self.add_section("Kubernetes Cluster Information", level=2)
        self.collect_kubernetes_info()
        
        # Kubernetes Nodes
        self.add_section("Kubernetes Nodes", level=2)
        self.collect_node_info()
        
        # Namespaces
        self.add_section("Kubernetes Namespaces", level=2)
        self.collect_namespace_info()
        
        # Helm Releases
        self.add_section("Helm Releases", level=2)
        self.collect_helm_info()
        
        # RunAI Configuration
        self.add_section("RunAI Configuration", level=2)
        self.collect_runai_info()
        
        # Pods
        self.add_section("Pods (All Namespaces)", level=2)
        self.collect_pod_info()
        
        # Deployments
        self.add_section("Deployments (All Namespaces)", level=2)
        self.collect_deployment_info()
        
        # StatefulSets
        self.add_section("StatefulSets (All Namespaces)", level=2)
        self.collect_statefulset_info()
        
        # DaemonSets
        self.add_section("DaemonSets (All Namespaces)", level=2)
        self.collect_daemonset_info()
        
        # Services
        self.add_section("Services (All Namespaces)", level=2)
        self.collect_service_info()
        
        # Ingresses
        self.add_section("Ingresses (All Namespaces)", level=2)
        self.collect_ingress_info()
        
        # ConfigMaps
        self.add_section("ConfigMaps (All Namespaces)", level=2)
        self.collect_configmap_info()
        
        # Secrets
        self.add_section("Secrets (All Namespaces)", level=2)
        self.collect_secret_info()
        
        # Storage
        self.add_section("Storage", level=2)
        self.collect_storage_info()
        
        # Network Policies
        self.add_section("Network Policies", level=2)
        self.collect_network_policy_info()
        
        # RBAC Configuration
        self.add_section("RBAC Configuration", level=2)
        self.collect_rbac_info()
        
        # Custom Resource Definitions
        self.add_section("Custom Resource Definitions", level=2)
        self.collect_crd_info()
        
        # Jobs and CronJobs
        self.add_section("Jobs and CronJobs", level=2)
        self.collect_job_info()
        
        # Resource Quotas and Limits
        self.add_section("Resource Quotas and Limits", level=2)
        self.collect_quota_info()
        
        # Priority Classes
        self.add_section("Priority Classes", level=2)
        self.collect_priority_class_info()
        
        # Pod Disruption Budgets
        self.add_section("Pod Disruption Budgets", level=2)
        self.collect_pdb_info()
        
        # Horizontal Pod Autoscalers
        self.add_section("Horizontal Pod Autoscalers", level=2)
        self.collect_hpa_info()
        
        # Vertical Pod Autoscalers
        self.add_section("Vertical Pod Autoscalers", level=2)
        self.collect_vpa_info()
        
        # Events
        self.add_section("Recent Events (All Namespaces)", level=2)
        self.collect_events()
        
        # Component Status
        self.add_section("Component Status", level=2)
        self.collect_component_status()
        
        # Metrics
        self.add_section("Metrics", level=2)
        self.collect_metrics()
        
        # GPU Information
        self.add_section("GPU Information", level=2)
        self.collect_gpu_info()
        
        # Container Runtime
        self.add_section("Container Runtime", level=2)
        self.collect_container_runtime_info()
        
        # Kubernetes Configuration
        self.add_section("Kubernetes Configuration", level=2)
        self.collect_k8s_config()
        
        # Network Plugin
        self.add_section("Network Plugin", level=2)
        self.collect_network_plugin_info()
        
        # Operators
        self.add_section("Operators", level=2)
        self.collect_operator_info()
        
        # Save output
        self.save_output()
    
    def collect_system_info(self):
        """Collect system information."""
        self.capture_output("Operating System", ["cat", "/etc/os-release"], "bash")
        self.capture_output("Kernel Version", ["uname", "-a"], "bash")
        self.capture_output("CPU Information", ["lscpu"], "")
        self.capture_output("Memory Information", ["free", "-h"], "")
        self.capture_output("Disk Usage", ["df", "-h"], "")
    
    def collect_kubernetes_info(self):
        """Collect Kubernetes cluster information."""
        self.capture_output("Kubectl Version", ["kubectl", "version", "--short"], "")
        self.capture_output("Cluster Info", ["kubectl", "cluster-info"], "")
        self.capture_output("Cluster API Versions", ["kubectl", "api-versions"], "")
        self.capture_output("Cluster API Resources", ["kubectl", "api-resources"], "")
    
    def collect_node_info(self):
        """Collect node information."""
        self.capture_output("Node List", ["kubectl", "get", "nodes", "-o", "wide"], "")
        self.capture_output("Node Details (YAML)", ["kubectl", "get", "nodes", "-o", "yaml"], "yaml")
        self.capture_output("Node Capacity and Allocatable", ["kubectl", "describe", "nodes"], "")
    
    def collect_namespace_info(self):
        """Collect namespace information."""
        self.capture_output("Namespace List", ["kubectl", "get", "namespaces"], "")
        self.capture_output("Namespace Details (YAML)", ["kubectl", "get", "namespaces", "-o", "yaml"], "yaml")
    
    def collect_helm_info(self):
        """Collect Helm release information."""
        self.capture_output("Helm Version", ["helm", "version"], "")
        self.capture_output("Helm Releases (All Namespaces)", ["helm", "list", "--all-namespaces"], "")
        
        # Get detailed information for each Helm release
        self.add_section("Detailed Helm Release Information", level=3)
        
        success, stdout, _ = self.run_command(["helm", "list", "--all-namespaces", "--output", "json"])
        
        if success and stdout.strip():
            try:
                releases = json.loads(stdout)
                for release in releases:
                    namespace = release.get('namespace', '')
                    name = release.get('name', '')
                    
                    if namespace and name:
                        print(f"Collecting: Helm release details for {name} in namespace {namespace}")
                        self.add_section(f"Helm Release: {name} (Namespace: {namespace})", level=4)
                        
                        # Get values
                        success, values_out, _ = self.run_command(["helm", "get", "values", name, "-n", namespace])
                        if success and values_out.strip():
                            self.add_text("**Values:**")
                            self.add_code_block(values_out, "yaml")
                        
                        # Get manifest
                        success, manifest_out, _ = self.run_command(["helm", "get", "manifest", name, "-n", namespace])
                        if success and manifest_out.strip():
                            self.add_text("**Manifest:**")
                            self.add_code_block(manifest_out, "yaml")
            except json.JSONDecodeError:
                self.add_text("_Could not parse Helm releases JSON_")
                self.add_text("")
        else:
            self.add_text("_No Helm releases found_")
            self.add_text("")
    
    def collect_runai_info(self):
        """Collect RunAI specific information."""
        # Check for RunAI namespaces
        success, stdout, _ = self.run_command(["kubectl", "get", "namespaces", "-o", "json"])
        
        if success and stdout.strip():
            try:
                namespaces_data = json.loads(stdout)
                runai_namespaces = [
                    ns['metadata']['name'] 
                    for ns in namespaces_data.get('items', [])
                    if 'runai' in ns['metadata']['name'].lower()
                ]
                
                if runai_namespaces:
                    self.add_section("RunAI Namespaces Found", level=3)
                    for ns in runai_namespaces:
                        self.add_text(f"- `{ns}`")
                    self.add_text("")
                    
                    for ns in runai_namespaces:
                        self.capture_output(f"RunAI Resources in Namespace: {ns}", 
                                          ["kubectl", "get", "all", "-n", ns, "-o", "wide"], "")
                else:
                    self.add_text("_No RunAI-specific namespaces found_")
                    self.add_text("")
            except json.JSONDecodeError:
                self.add_text("_Could not parse namespaces JSON_")
                self.add_text("")
        
        # Check for RunAI CRDs
        self.capture_output("RunAI Custom Resource Definitions", 
                          ["bash", "-c", "kubectl get crd | grep -i runai || echo 'No RunAI CRDs found'"], "")
        
        # Get all RunAI-related CRDs details
        success, stdout, _ = self.run_command(["kubectl", "get", "crd", "-o", "json"])
        if success and stdout.strip():
            try:
                crds_data = json.loads(stdout)
                runai_crds = [
                    crd['metadata']['name']
                    for crd in crds_data.get('items', [])
                    if 'runai' in crd['metadata']['name'].lower()
                ]
                
                for crd in runai_crds:
                    self.capture_output(f"CRD Details: {crd}", ["kubectl", "get", "crd", crd, "-o", "yaml"], "yaml")
            except json.JSONDecodeError:
                pass
    
    def collect_pod_info(self):
        """Collect pod information."""
        self.capture_output("Pod List (All Namespaces)", ["kubectl", "get", "pods", "--all-namespaces", "-o", "wide"], "")
        self.capture_output("Pod Details (YAML)", ["kubectl", "get", "pods", "--all-namespaces", "-o", "yaml"], "yaml")
    
    def collect_deployment_info(self):
        """Collect deployment information."""
        self.capture_output("Deployment List", ["kubectl", "get", "deployments", "--all-namespaces", "-o", "wide"], "")
        self.capture_output("Deployment Details (YAML)", ["kubectl", "get", "deployments", "--all-namespaces", "-o", "yaml"], "yaml")
    
    def collect_statefulset_info(self):
        """Collect statefulset information."""
        self.capture_output("StatefulSet List", ["kubectl", "get", "statefulsets", "--all-namespaces", "-o", "wide"], "")
        self.capture_output("StatefulSet Details (YAML)", ["kubectl", "get", "statefulsets", "--all-namespaces", "-o", "yaml"], "yaml")
    
    def collect_daemonset_info(self):
        """Collect daemonset information."""
        self.capture_output("DaemonSet List", ["kubectl", "get", "daemonsets", "--all-namespaces", "-o", "wide"], "")
        self.capture_output("DaemonSet Details (YAML)", ["kubectl", "get", "daemonsets", "--all-namespaces", "-o", "yaml"], "yaml")
    
    def collect_service_info(self):
        """Collect service information."""
        self.capture_output("Service List", ["kubectl", "get", "services", "--all-namespaces", "-o", "wide"], "")
        self.capture_output("Service Details (YAML)", ["kubectl", "get", "services", "--all-namespaces", "-o", "yaml"], "yaml")
    
    def collect_ingress_info(self):
        """Collect ingress information."""
        self.capture_output("Ingress List", ["kubectl", "get", "ingresses", "--all-namespaces", "-o", "wide"], "")
        self.capture_output("Ingress Details (YAML)", ["kubectl", "get", "ingresses", "--all-namespaces", "-o", "yaml"], "yaml")
    
    def collect_configmap_info(self):
        """Collect configmap information."""
        self.capture_output("ConfigMap List", ["kubectl", "get", "configmaps", "--all-namespaces"], "")
        self.capture_output("ConfigMap Details (YAML)", ["kubectl", "get", "configmaps", "--all-namespaces", "-o", "yaml"], "yaml")
    
    def collect_secret_info(self):
        """Collect secret information (names only, not values)."""
        self.capture_output("Secret List", ["kubectl", "get", "secrets", "--all-namespaces"], "")
        
        self.add_section("Secret Names and Types (values redacted for security)", level=3)
        success, stdout, _ = self.run_command(["kubectl", "get", "secrets", "--all-namespaces", "-o", "json"])
        
        if success and stdout.strip():
            try:
                secrets_data = json.loads(stdout)
                secret_list = []
                for secret in secrets_data.get('items', []):
                    namespace = secret['metadata']['namespace']
                    name = secret['metadata']['name']
                    secret_type = secret.get('type', 'Unknown')
                    secret_list.append(f"- `{namespace}/{name}` ({secret_type})")
                
                if secret_list:
                    self.add_text('\n'.join(secret_list))
                    self.add_text("")
            except json.JSONDecodeError:
                self.add_text("_Could not parse secrets JSON_")
                self.add_text("")
    
    def collect_storage_info(self):
        """Collect storage information."""
        self.capture_output("Persistent Volumes", ["kubectl", "get", "pv", "-o", "wide"], "")
        self.capture_output("Persistent Volume Details (YAML)", ["kubectl", "get", "pv", "-o", "yaml"], "yaml")
        self.capture_output("Persistent Volume Claims (All Namespaces)", ["kubectl", "get", "pvc", "--all-namespaces", "-o", "wide"], "")
        self.capture_output("Persistent Volume Claim Details (YAML)", ["kubectl", "get", "pvc", "--all-namespaces", "-o", "yaml"], "yaml")
        self.capture_output("Storage Classes", ["kubectl", "get", "storageclasses", "-o", "wide"], "")
        self.capture_output("Storage Class Details (YAML)", ["kubectl", "get", "storageclasses", "-o", "yaml"], "yaml")
    
    def collect_network_policy_info(self):
        """Collect network policy information."""
        self.capture_output("Network Policy List", ["kubectl", "get", "networkpolicies", "--all-namespaces", "-o", "wide"], "")
        self.capture_output("Network Policy Details (YAML)", ["kubectl", "get", "networkpolicies", "--all-namespaces", "-o", "yaml"], "yaml")
    
    def collect_rbac_info(self):
        """Collect RBAC information."""
        self.capture_output("Cluster Roles", ["kubectl", "get", "clusterroles"], "")
        self.capture_output("Cluster Role Bindings", ["kubectl", "get", "clusterrolebindings"], "")
        self.capture_output("Roles (All Namespaces)", ["kubectl", "get", "roles", "--all-namespaces"], "")
        self.capture_output("Role Bindings (All Namespaces)", ["kubectl", "get", "rolebindings", "--all-namespaces"], "")
        self.capture_output("Service Accounts (All Namespaces)", ["kubectl", "get", "serviceaccounts", "--all-namespaces"], "")
    
    def collect_crd_info(self):
        """Collect CRD information."""
        self.capture_output("CRD List", ["kubectl", "get", "crds"], "")
        self.capture_output("CRD Details (YAML)", ["kubectl", "get", "crds", "-o", "yaml"], "yaml")
    
    def collect_job_info(self):
        """Collect job and cronjob information."""
        self.capture_output("Job List", ["kubectl", "get", "jobs", "--all-namespaces", "-o", "wide"], "")
        self.capture_output("Job Details (YAML)", ["kubectl", "get", "jobs", "--all-namespaces", "-o", "yaml"], "yaml")
        self.capture_output("CronJob List", ["kubectl", "get", "cronjobs", "--all-namespaces", "-o", "wide"], "")
        self.capture_output("CronJob Details (YAML)", ["kubectl", "get", "cronjobs", "--all-namespaces", "-o", "yaml"], "yaml")
    
    def collect_quota_info(self):
        """Collect resource quota and limit range information."""
        self.capture_output("Resource Quotas", ["kubectl", "get", "resourcequotas", "--all-namespaces"], "")
        self.capture_output("Resource Quota Details (YAML)", ["kubectl", "get", "resourcequotas", "--all-namespaces", "-o", "yaml"], "yaml")
        self.capture_output("Limit Ranges", ["kubectl", "get", "limitranges", "--all-namespaces"], "")
        self.capture_output("Limit Range Details (YAML)", ["kubectl", "get", "limitranges", "--all-namespaces", "-o", "yaml"], "yaml")
    
    def collect_priority_class_info(self):
        """Collect priority class information."""
        self.capture_output("Priority Class List", ["kubectl", "get", "priorityclasses"], "")
        self.capture_output("Priority Class Details (YAML)", ["kubectl", "get", "priorityclasses", "-o", "yaml"], "yaml")
    
    def collect_pdb_info(self):
        """Collect pod disruption budget information."""
        self.capture_output("PDB List", ["kubectl", "get", "poddisruptionbudgets", "--all-namespaces"], "")
        self.capture_output("PDB Details (YAML)", ["kubectl", "get", "poddisruptionbudgets", "--all-namespaces", "-o", "yaml"], "yaml")
    
    def collect_hpa_info(self):
        """Collect horizontal pod autoscaler information."""
        self.capture_output("HPA List", ["kubectl", "get", "hpa", "--all-namespaces"], "")
        self.capture_output("HPA Details (YAML)", ["kubectl", "get", "hpa", "--all-namespaces", "-o", "yaml"], "yaml")
    
    def collect_vpa_info(self):
        """Collect vertical pod autoscaler information."""
        success, _, _ = self.run_command(["kubectl", "get", "crd", "verticalpodautoscalers.autoscaling.k8s.io"])
        
        if success:
            self.capture_output("VPA List", ["kubectl", "get", "vpa", "--all-namespaces"], "")
            self.capture_output("VPA Details (YAML)", ["kubectl", "get", "vpa", "--all-namespaces", "-o", "yaml"], "yaml")
        else:
            self.add_text("_VPA CRD not found - skipping_")
            self.add_text("")
    
    def collect_events(self):
        """Collect recent events."""
        self.capture_output("Events", ["kubectl", "get", "events", "--all-namespaces", "--sort-by=.lastTimestamp"], "")
    
    def collect_component_status(self):
        """Collect component status."""
        self.capture_output("Component Status", 
                          ["bash", "-c", "kubectl get componentstatuses || echo 'Component status API may be deprecated in this Kubernetes version'"], "")
    
    def collect_metrics(self):
        """Collect metrics if available."""
        success, _, _ = self.run_command(["kubectl", "top", "nodes"])
        
        if success:
            self.capture_output("Node Metrics", ["kubectl", "top", "nodes"], "")
            self.capture_output("Pod Metrics (All Namespaces)", ["kubectl", "top", "pods", "--all-namespaces"], "")
        else:
            self.add_text("_Metrics server not available - skipping metrics collection_")
            self.add_text("")
    
    def collect_gpu_info(self):
        """Collect GPU information."""
        success, _, _ = self.run_command(["which", "nvidia-smi"])
        
        if success:
            self.capture_output("NVIDIA GPU Status", ["nvidia-smi"], "")
            self.capture_output("NVIDIA GPU Details", ["nvidia-smi", "-q"], "")
        else:
            self.add_text("_nvidia-smi not found - skipping GPU information_")
            self.add_text("")
        
        # Check for GPU operator or device plugin
        self.capture_output("GPU Device Plugin Pods", 
                          ["bash", "-c", "kubectl get pods --all-namespaces | grep -i 'gpu\\|nvidia' || echo 'No GPU-related pods found'"], "")
    
    def collect_container_runtime_info(self):
        """Collect container runtime information."""
        # Try to detect container runtime
        docker_exists = self.run_command(["which", "docker"])[0]
        crictl_exists = self.run_command(["which", "crictl"])[0]
        nerdctl_exists = self.run_command(["which", "nerdctl"])[0]
        
        if docker_exists:
            self.capture_output("Docker Version", ["docker", "version"], "")
            self.capture_output("Docker Info", ["docker", "info"], "")
        elif crictl_exists:
            self.capture_output("CRI-CTL Version", ["crictl", "version"], "")
            self.capture_output("CRI-CTL Info", ["crictl", "info"], "")
        elif nerdctl_exists:
            self.capture_output("Nerdctl Version", ["nerdctl", "version"], "")
        else:
            self.add_text("_No container runtime CLI found_")
            self.add_text("")
    
    def collect_k8s_config(self):
        """Collect Kubernetes configuration information."""
        if os.path.exists('/etc/kubernetes/admin.conf'):
            self.add_text("**Kubernetes admin.conf exists**")
            self.add_text("Path: `/etc/kubernetes/admin.conf`")
            self.add_text("")
        elif os.path.exists(os.path.expanduser('~/.kube/config')):
            self.add_text("**Kubeconfig location**")
            self.add_text(f"Path: `{os.path.expanduser('~/.kube/config')}`")
            self.add_text("")
            
            self.capture_output("Current Context", ["kubectl", "config", "current-context"], "")
            self.capture_output("Available Contexts", ["kubectl", "config", "get-contexts"], "")
    
    def collect_network_plugin_info(self):
        """Collect network plugin information."""
        self.capture_output("Calico Resources", 
                          ["bash", "-c", "kubectl get pods -n kube-system | grep -i calico || echo 'Calico not found'"], "")
        self.capture_output("Flannel Resources", 
                          ["bash", "-c", "kubectl get pods -n kube-system | grep -i flannel || echo 'Flannel not found'"], "")
        self.capture_output("Weave Resources", 
                          ["bash", "-c", "kubectl get pods -n kube-system | grep -i weave || echo 'Weave not found'"], "")
        self.capture_output("Cilium Resources", 
                          ["bash", "-c", "kubectl get pods -n kube-system | grep -i cilium || echo 'Cilium not found'"], "")
    
    def collect_operator_info(self):
        """Collect operator information."""
        success, _, _ = self.run_command(["kubectl", "get", "crd", "clusterserviceversions.operators.coreos.com"])
        
        if success:
            self.capture_output("Cluster Service Versions (OLM)", ["kubectl", "get", "csv", "--all-namespaces"], "")
            self.capture_output("Operator Subscriptions", ["kubectl", "get", "subscriptions", "--all-namespaces"], "")
            self.capture_output("Install Plans", ["kubectl", "get", "installplans", "--all-namespaces"], "")
        else:
            self.add_text("_OLM not detected_")
            self.add_text("")


def main():
    """Main entry point."""
    try:
        discovery = EnvironmentDiscovery()
        discovery.discover()
        return 0
    except KeyboardInterrupt:
        print("\n\nDiscovery interrupted by user.")
        return 1
    except Exception as e:
        print(f"\n\nError during discovery: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
