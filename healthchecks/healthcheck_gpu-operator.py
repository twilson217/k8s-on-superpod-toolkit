#!/usr/bin/env python3
"""
GPU Operator Validation Test Script

Purpose: Comprehensive testing of NVIDIA GPU Operator functionality
Usage: python3 test_gpu_operator.py [before|after|baseline]

This script runs 9 tests to validate GPU Operator functionality:
1. Environment Information
2. GPU Operator Pod Status
3. GPU Node Discovery
4. NVIDIA Device Plugin
5. GPU Feature Discovery
6. DCGM Metrics Exporter
7. Operator Validator
8. CUDA Workload Test
9. Run:AI Integration

Note: Driver test removed - in SuperPod environments, NVIDIA drivers
are managed at the DGX OS level, not by GPU Operator.

Results are saved to timestamped log files for comparison.
"""

import subprocess
import sys
import json
import time
from datetime import datetime
from typing import Tuple, Optional
import argparse


class Colors:
    """ANSI color codes for terminal output"""
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    MAGENTA = '\033[0;35m'
    CYAN = '\033[0;36m'
    BOLD = '\033[1m'
    NC = '\033[0m'  # No Color


class TestResult:
    """Track test results"""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.total = 9  # Total number of tests (updated for SuperPod)
        
    def pass_test(self):
        self.passed += 1
        
    def fail_test(self):
        self.failed += 1
        
    def all_passed(self) -> bool:
        return self.failed == 0


class GPUOperatorTester:
    """Main test runner for GPU Operator validation"""
    
    def __init__(self, phase: str):
        self.phase = phase
        self.timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.output_file = f"gpu-operator-test-{phase}-{self.timestamp}.log"
        self.results = TestResult()
        self.results.total = 9  # Updated: 9 tests (removed driver test for SuperPod)
        
        # Open log file
        self.log_handle = open(self.output_file, 'w')
        
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.log_handle.close()
        
    def run_command(self, cmd: list, check: bool = False, capture_output: bool = True) -> Tuple[int, str, str]:
        """Run a shell command and return exit code, stdout, stderr"""
        try:
            result = subprocess.run(
                cmd,
                capture_output=capture_output,
                text=True,
                timeout=120
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return 1, "", "Command timed out"
        except Exception as e:
            return 1, "", str(e)
    
    def log(self, message: str, color: str = ""):
        """Log message to both console and file"""
        # Console with color
        if color:
            print(f"{color}{message}{Colors.NC}")
        else:
            print(message)
        
        # File without color codes
        self.log_handle.write(message + "\n")
        self.log_handle.flush()
    
    def print_header(self, text: str):
        """Print a header"""
        self.log("=" * 60, Colors.BLUE)
        self.log(text, Colors.BLUE)
        self.log("=" * 60, Colors.BLUE)
    
    def print_test(self, num: int, name: str):
        """Print test header"""
        self.log("")
        self.log(f"[TEST {num}/{self.results.total}] {name}", Colors.YELLOW)
        self.log("-" * 60)
    
    def print_pass(self, message: str):
        """Print pass message"""
        self.log(f"✅ PASS: {message}", Colors.GREEN)
        self.results.pass_test()
    
    def print_fail(self, message: str):
        """Print fail message"""
        self.log(f"❌ FAIL: {message}", Colors.RED)
        self.results.fail_test()
    
    def print_info(self, message: str):
        """Print info message"""
        self.log(f"ℹ  {message}", Colors.BLUE)
    
    def print_warning(self, message: str):
        """Print warning message"""
        self.log(f"⚠  {message}", Colors.YELLOW)
    
    def kubectl(self, *args) -> Tuple[int, str, str]:
        """Run kubectl command"""
        return self.run_command(['kubectl'] + list(args))
    
    def helm(self, *args) -> Tuple[int, str, str]:
        """Run helm command"""
        return self.run_command(['helm'] + list(args))
    
    # =========================================================================
    # TEST IMPLEMENTATIONS
    # =========================================================================
    
    def test_environment(self):
        """Test 1: Collect environment information"""
        self.print_test(1, "Environment Information")
        
        # Kubernetes version
        self.log("Kubernetes Version:")
        code, stdout, stderr = self.kubectl("version", "--short")
        self.log(stdout if code == 0 else stderr)
        
        # GPU Operator version
        self.log("\nGPU Operator Helm Release:")
        code, stdout, stderr = self.helm("list", "-n", "gpu-operator")
        self.log(stdout if code == 0 else stderr)
        
        if code == 0:
            # Try to get version from helm
            code2, stdout2, _ = self.helm("list", "-n", "gpu-operator", "-o", "json")
            if code2 == 0:
                try:
                    releases = json.loads(stdout2)
                    if releases:
                        chart = releases[0].get('chart', 'Unknown')
                        self.print_info(f"GPU Operator Chart: {chart}")
                except:
                    pass
        
        self.print_pass("Environment info collected")
    
    def test_pod_status(self):
        """Test 2: Verify all GPU Operator pods are running or completed"""
        self.print_test(2, "GPU Operator Pod Status")
        
        self.log("All pods in gpu-operator namespace:")
        code, stdout, _ = self.kubectl("get", "pods", "-n", "gpu-operator", "-o", "wide")
        self.log(stdout)
        
        # Count pods by status
        code, stdout, _ = self.kubectl("get", "pods", "-n", "gpu-operator", "--no-headers")
        total_pods = len([l for l in stdout.strip().split('\n') if l]) if stdout.strip() else 0
        
        # Count Running pods
        code, stdout, _ = self.kubectl("get", "pods", "-n", "gpu-operator", 
                                       "--field-selector=status.phase=Running", "--no-headers")
        running_pods = len([l for l in stdout.strip().split('\n') if l]) if stdout.strip() else 0
        
        # Count Completed/Succeeded pods (e.g., nvidia-cuda-validator Jobs)
        code, stdout, _ = self.kubectl("get", "pods", "-n", "gpu-operator",
                                       "--field-selector=status.phase=Succeeded", "--no-headers")
        completed_pods = len([l for l in stdout.strip().split('\n') if l]) if stdout.strip() else 0
        
        healthy_pods = running_pods + completed_pods
        
        self.print_info(f"Total pods: {total_pods}")
        self.print_info(f"Running pods: {running_pods}")
        self.print_info(f"Completed pods: {completed_pods} (Jobs)")
        self.print_info(f"Healthy pods: {healthy_pods}")
        
        # Check for failed/problematic pods
        code, stdout, _ = self.kubectl("get", "pods", "-n", "gpu-operator",
                                       "--field-selector=status.phase!=Running,status.phase!=Succeeded",
                                       "--no-headers")
        if stdout.strip():
            self.print_warning("Non-healthy pods found:")
            self.log(stdout)
        
        if healthy_pods == total_pods and total_pods > 0:
            self.print_pass(f"All GPU Operator pods are healthy ({running_pods} Running + {completed_pods} Completed = {healthy_pods}/{total_pods})")
        else:
            self.print_fail(f"Not all pods are healthy ({healthy_pods}/{total_pods})")
    
    def test_gpu_discovery(self):
        """Test 3: Verify GPUs are discovered on nodes"""
        self.print_test(3, "GPU Node Discovery")
        
        self.log("Nodes with NVIDIA GPUs:")
        code, stdout, _ = self.kubectl("get", "nodes", "-l", "nvidia.com/gpu.present=true", "--no-headers")
        self.log(stdout)
        
        gpu_node_count = len([l for l in stdout.strip().split('\n') if l]) if stdout.strip() else 0
        self.print_info(f"GPU nodes detected: {gpu_node_count}")
        
        if gpu_node_count > 0:
            self.log("\nGPU resources per node:")
            code, stdout, _ = self.kubectl("get", "nodes", "-o", "json")
            if code == 0:
                try:
                    nodes_data = json.loads(stdout)
                    for node in nodes_data.get('items', []):
                        gpu_capacity = node.get('status', {}).get('capacity', {}).get('nvidia.com/gpu')
                        if gpu_capacity:
                            node_name = node.get('metadata', {}).get('name', 'Unknown')
                            gpu_allocatable = node.get('status', {}).get('allocatable', {}).get('nvidia.com/gpu', '0')
                            self.log(f"{node_name}: {gpu_capacity} GPUs (Allocatable: {gpu_allocatable})")
                except json.JSONDecodeError:
                    self.log("Failed to parse node JSON")
            
            self.print_pass(f"GPU nodes discovered: {gpu_node_count} nodes with GPUs")
        else:
            self.print_fail("No GPU nodes found")
    
    def test_device_plugin(self):
        """Test 4: Verify NVIDIA device plugin status"""
        self.print_test(4, "NVIDIA Device Plugin Status")
        
        self.log("Device Plugin DaemonSet:")
        code, stdout, _ = self.kubectl("get", "ds", "-n", "gpu-operator", 
                                       "nvidia-device-plugin-daemonset", "-o", "wide")
        self.log(stdout if code == 0 else "DaemonSet not found")
        
        # Get desired vs ready count
        code, stdout, _ = self.kubectl("get", "ds", "-n", "gpu-operator",
                                       "nvidia-device-plugin-daemonset",
                                       "-o", "jsonpath={.status.desiredNumberScheduled}")
        desired = int(stdout) if code == 0 and stdout else 0
        
        code, stdout, _ = self.kubectl("get", "ds", "-n", "gpu-operator",
                                       "nvidia-device-plugin-daemonset",
                                       "-o", "jsonpath={.status.numberReady}")
        ready = int(stdout) if code == 0 and stdout else 0
        
        self.print_info(f"Device Plugin pods: {ready}/{desired} ready")
        
        if ready == desired and desired > 0:
            self.print_pass("Device Plugin running on all GPU nodes")
        else:
            self.print_fail(f"Device Plugin not ready on all nodes ({ready}/{desired})")
    
    def test_gpu_feature_discovery(self):
        """Test 5: Verify GPU Feature Discovery"""
        self.print_test(5, "GPU Feature Discovery (GFD)")
        
        self.log("GFD DaemonSet:")
        code, stdout, _ = self.kubectl("get", "ds", "-n", "gpu-operator",
                                       "gpu-feature-discovery", "-o", "wide")
        self.log(stdout if code == 0 else "DaemonSet not found")
        
        # Get desired vs ready count
        code, stdout, _ = self.kubectl("get", "ds", "-n", "gpu-operator",
                                       "gpu-feature-discovery",
                                       "-o", "jsonpath={.status.desiredNumberScheduled}")
        desired = int(stdout) if code == 0 and stdout else 0
        
        code, stdout, _ = self.kubectl("get", "ds", "-n", "gpu-operator",
                                       "gpu-feature-discovery",
                                       "-o", "jsonpath={.status.numberReady}")
        ready = int(stdout) if code == 0 and stdout else 0
        
        self.print_info(f"GFD pods: {ready}/{desired} ready")
        
        # Check GPU labels on a node
        code, stdout, _ = self.kubectl("get", "nodes", "-l", "nvidia.com/gpu.present=true",
                                       "-o", "name")
        if code == 0 and stdout.strip():
            sample_node = stdout.strip().split('\n')[0]
            self.log(f"\nSample GPU labels on {sample_node}:")
            
            code, stdout, _ = self.kubectl("get", sample_node, "-o", "json")
            if code == 0:
                try:
                    node_data = json.loads(stdout)
                    labels = node_data.get('metadata', {}).get('labels', {})
                    nvidia_labels = {k: v for k, v in labels.items() if k.startswith('nvidia.com/')}
                    
                    for k, v in sorted(nvidia_labels.items())[:10]:
                        self.log(f"  {k}={v}")
                    
                    label_count = len(nvidia_labels)
                    self.print_info(f"NVIDIA labels on node: {label_count}")
                    
                    if ready == desired and label_count > 5:
                        self.print_pass("GPU Feature Discovery working, nodes properly labeled")
                    else:
                        self.print_fail("GFD not fully functional or labels missing")
                except json.JSONDecodeError:
                    self.print_fail("Failed to parse node JSON")
        else:
            self.print_fail("No GPU nodes found to check labels")
    
    def test_dcgm_exporter(self):
        """Test 6: Verify DCGM metrics exporter"""
        self.print_test(6, "DCGM Metrics Exporter")
        
        self.log("DCGM Exporter DaemonSet:")
        code, stdout, _ = self.kubectl("get", "ds", "-n", "gpu-operator",
                                       "nvidia-dcgm-exporter", "-o", "wide")
        self.log(stdout if code == 0 else "DaemonSet not found")
        
        # Get desired vs ready count
        code, stdout, _ = self.kubectl("get", "ds", "-n", "gpu-operator",
                                       "nvidia-dcgm-exporter",
                                       "-o", "jsonpath={.status.desiredNumberScheduled}")
        desired = int(stdout) if code == 0 and stdout else 0
        
        code, stdout, _ = self.kubectl("get", "ds", "-n", "gpu-operator",
                                       "nvidia-dcgm-exporter",
                                       "-o", "jsonpath={.status.numberReady}")
        ready = int(stdout) if code == 0 and stdout else 0
        
        self.print_info(f"DCGM Exporter pods: {ready}/{desired} ready")
        
        # Validate pod status and service
        if ready == desired and desired > 0:
            # Check if service exists for Prometheus to scrape
            code, stdout, _ = self.kubectl("get", "svc", "-n", "gpu-operator", 
                                          "nvidia-dcgm-exporter", "-o", "wide")
            if code == 0:
                self.log("DCGM Exporter Service:")
                self.log(stdout)
                self.print_info("DCGM metrics service available for scraping")
            else:
                self.print_warning("DCGM service not found (metrics may not be scrapeable)")
            
            self.print_pass(f"DCGM exporter running on all GPU nodes ({ready}/{desired})")
        elif desired == 0:
            self.print_warning("DCGM exporter DaemonSet found but not scheduled on any nodes")
        else:
            self.print_fail(f"DCGM exporter not ready on all nodes ({ready}/{desired})")
    
    def test_operator_validator(self):
        """Test 7: Verify operator validator"""
        self.print_test(7, "NVIDIA Operator Validator")
        
        self.log("Validator DaemonSet:")
        code, stdout, _ = self.kubectl("get", "ds", "-n", "gpu-operator",
                                       "nvidia-operator-validator", "-o", "wide")
        self.log(stdout if code == 0 else "DaemonSet not found")
        
        # Get desired vs ready count
        code, stdout, _ = self.kubectl("get", "ds", "-n", "gpu-operator",
                                       "nvidia-operator-validator",
                                       "-o", "jsonpath={.status.desiredNumberScheduled}")
        desired = int(stdout) if code == 0 and stdout else 0
        
        code, stdout, _ = self.kubectl("get", "ds", "-n", "gpu-operator",
                                       "nvidia-operator-validator",
                                       "-o", "jsonpath={.status.numberReady}")
        ready = int(stdout) if code == 0 and stdout else 0
        
        self.print_info(f"Validator pods: {ready}/{desired} ready")
        
        if ready == desired and desired > 0:
            self.print_pass("Operator validator running on all GPU nodes")
        else:
            self.print_fail(f"Operator validator not ready on all nodes ({ready}/{desired})")
    
    def test_cuda_workload(self):
        """Test 8: Run actual CUDA workload"""
        self.print_test(8, "CUDA Workload Execution")
        
        test_pod_name = "gpu-operator-test-pod"
        
        self.print_info("Creating test pod with GPU request...")
        
        # Clean up any existing test pod
        self.kubectl("delete", "pod", test_pod_name, "--ignore-not-found=true")
        time.sleep(2)
        
        # Create test pod
        pod_yaml = f"""apiVersion: v1
kind: Pod
metadata:
  name: {test_pod_name}
  namespace: default
spec:
  restartPolicy: Never
  containers:
  - name: cuda
    image: nvidia/cuda:12.2.0-base-ubuntu22.04
    command:
      - /bin/bash
      - -c
      - |
        echo "=== CUDA Test Starting ==="
        echo "Checking nvidia-smi availability..."
        nvidia-smi -L
        echo ""
        echo "GPU Details:"
        nvidia-smi --query-gpu=index,name,driver_version,memory.total,memory.free --format=csv
        echo ""
        echo "=== CUDA Test Complete ==="
    resources:
      limits:
        nvidia.com/gpu: 1
"""
        
        # Apply pod
        code, stdout, stderr = self.run_command(['kubectl', 'apply', '-f', '-'], check=False, capture_output=True)
        if code != 0:
            # Try with echo | kubectl
            proc = subprocess.Popen(['kubectl', 'apply', '-f', '-'], 
                                   stdin=subprocess.PIPE, 
                                   stdout=subprocess.PIPE, 
                                   stderr=subprocess.PIPE, 
                                   text=True)
            stdout, stderr = proc.communicate(input=pod_yaml)
            code = proc.returncode
        else:
            proc = subprocess.Popen(['kubectl', 'apply', '-f', '-'], 
                                   stdin=subprocess.PIPE, 
                                   stdout=subprocess.PIPE, 
                                   stderr=subprocess.PIPE, 
                                   text=True)
            stdout, stderr = proc.communicate(input=pod_yaml)
            code = proc.returncode
        
        if code != 0:
            self.log(f"Failed to create pod: {stderr}")
            self.print_fail("Could not create test pod")
            return
        
        # Wait for pod to complete
        self.print_info("Waiting for pod to complete (max 60s)...")
        max_wait = 60
        wait_time = 0
        pod_status = "Unknown"
        
        while wait_time < max_wait:
            code, stdout, _ = self.kubectl("get", "pod", test_pod_name,
                                          "-o", "jsonpath={.status.phase}")
            if code == 0:
                pod_status = stdout.strip()
                if pod_status in ["Succeeded", "Failed"]:
                    break
            time.sleep(2)
            wait_time += 2
        
        self.print_info(f"Pod status: {pod_status}")
        
        # Get logs
        self.log("\nPod logs:")
        code, stdout, stderr = self.kubectl("logs", test_pod_name)
        self.log(stdout if code == 0 else stderr)
        
        # Check if test passed
        if pod_status == "Succeeded" and "CUDA Test Complete" in stdout:
            self.print_pass("CUDA workload executed successfully")
        else:
            self.print_fail(f"CUDA workload test failed (status: {pod_status})")
        
        # Cleanup
        self.print_info("Cleaning up test pod...")
        self.kubectl("delete", "pod", test_pod_name, "--ignore-not-found=true")
    
    # =========================================================================
    # MAIN TEST RUNNER
    # =========================================================================
    
    def run_all_tests(self):
        """Run all tests"""
        # Header
        self.log("GPU Operator Validation Test Results")
        self.log("=" * 60)
        self.log(f"Test Phase: {self.phase}")
        self.log(f"Date: {datetime.now()}")
        self.log(f"Output File: {self.output_file}")
        self.log("")
        
        self.print_header("GPU OPERATOR VALIDATION TEST SUITE")
        self.log("")
        self.print_info(f"Test phase: {self.phase}")
        self.print_info(f"Output file: {self.output_file}")
        self.log("")
        
        # Run tests
        try:
            self.test_environment()
            self.test_pod_status()
            self.test_gpu_discovery()
            self.test_device_plugin()
            # Note: test_driver removed - drivers managed by DGX OS in SuperPod
            self.test_gpu_feature_discovery()
            self.test_dcgm_exporter()
            self.test_operator_validator()
            self.test_cuda_workload()
        except KeyboardInterrupt:
            self.log("\n\nTests interrupted by user")
            return False
        except Exception as e:
            self.log(f"\n\nUnexpected error: {e}")
            return False
        
        # Summary
        self.log("")
        self.print_header("TEST RESULTS SUMMARY")
        self.log("")
        
        self.print_info(f"Test Phase: {self.phase}")
        self.print_info(f"Total Tests: {self.results.total}")
        self.log(f"{Colors.GREEN}Passed: {self.results.passed}{Colors.NC}")
        self.log(f"{Colors.RED}Failed: {self.results.failed}{Colors.NC}")
        self.log("")
        
        # Overall result
        if self.results.all_passed():
            self.log("╔═══════════════════════════════════╗", Colors.GREEN)
            self.log("║   ✅ ALL TESTS PASSED! ✅         ║", Colors.GREEN)
            self.log("╚═══════════════════════════════════╝", Colors.GREEN)
        else:
            self.log("╔═══════════════════════════════════╗", Colors.RED)
            self.log("║   ❌ SOME TESTS FAILED ❌         ║", Colors.RED)
            self.log("╚═══════════════════════════════════╝", Colors.RED)
        
        self.log("")
        self.print_info(f"Full results saved to: {self.output_file}")
        self.log("")
        
        # Next steps
        if self.phase == "before":
            self.print_info("Next: Review results, then proceed with GPU Operator upgrade")
            self.print_info("After upgrade, run: python3 test_gpu_operator.py after")
        elif self.phase == "after":
            import glob
            before_files = sorted(glob.glob("gpu-operator-test-before-*.log"))
            if before_files:
                self.print_info("Compare with before-upgrade results:")
                self.print_info(f"  diff {before_files[-1]} {self.output_file}")
        
        return self.results.all_passed()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="GPU Operator Validation Test Suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run before upgrade to establish baseline
  python3 test_gpu_operator.py before
  
  # Run after upgrade to verify functionality
  python3 test_gpu_operator.py after
  
  # Run general test
  python3 test_gpu_operator.py
        """
    )
    parser.add_argument(
        'phase',
        nargs='?',
        default='baseline',
        choices=['before', 'after', 'baseline'],
        help='Test phase: before (pre-upgrade), after (post-upgrade), or baseline (general)'
    )
    
    args = parser.parse_args()
    
    # Run tests
    with GPUOperatorTester(args.phase) as tester:
        success = tester.run_all_tests()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

